"""CR-0021 pre-registration (deliverable 1; CR-0021 section 4). Written
before approval (CLAUDE.md section 1 / CR-0011 A3). Read-only on the live
tree; reads the topped-up SCRATCH tree; writes only next to this file.

Independent of generate_negatives.py: the pipeline is CR-0013's replay
(acceptance_split.Replay, written by a separate agent from the CR text),
subclassed here only at the draw (Stratified) and, for reporting, to
capture the pool's dedup and thinning (Capture; behaviour unchanged).

Order (CR-0021 section 4; the strata are chosen BEFORE any AUC):
  0. live tree == the pinned CR-0019 acceptance record (artifacts and the
     three raw files); scratch tree: same inputs except the raw files, whose
     live bytes are an exact prefix and whose sha256 equals
     fetch_topup_result.json; rasters are the live files (by realpath).
  1. CONTROL: the unmodified replay on the live tree reproduces today's P,
     B, C and N (keys, split, block_id, year), else abort.
  2. pre-check: no 5 dp key under two states in the topped-up candidates
     (the pool's step 3 would raise).
  3. the topped-up pool (replay on SCRATCH): supply per (region, split,
     year), before and after; existing pool rows lost or relabelled, by
     mechanism; per-partition yield of the new rows; comparability of the
     new rows (tolerances: species TVD and coord_uncertainty_m; blocks and
     counties report-only, user decision 2026-10-03).
  4. strata: S1, S2, S3 in this order; the first with zero SHORT cells.
     If none: stop here (exit 2), no AUC is computed.
  5. the stratified draw (Stratified) on SCRATCH with the chosen strata;
     n_hab / habitat supply per stratum (> 0.8 named, report-only).
  6. only now: O11a (all rows) and O11w (within each merged stratum, with
     a within-cell label-permutation null and effect size), for today's N
     and for the predicted N.
  7. N keys kept / removed / added.

Run (repository root, on the EC2 host, after fetch_topup.py):
    PYTHONPATH=. nice -n 10 python docs/quality/evidence/CR-0021/preregister.py --scratch SCRATCH

Writes, next to this file:
    preregister.txt        the report (stdout copy)
    preregister_C.csv      predicted pool: region, split, year, is_nonveg,
                           longitude, latitude, gbif_id (canonical order)
    preregister_N.csv      predicted negatives: region, split, year,
                           is_nonveg, longitude, latitude
    preregister_draw.json  chosen strata and the per-stratum draw breakdown
Exit codes: 0 done; 1 a precondition or the control failed; 2 no strata
feasible; 3 a two-state key in the topped-up candidates.
"""
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, ROOT)
import acceptance_split as A  # noqa: E402

RECORD = os.path.join(HERE, "..", "CR-0019", "live", "acceptance_record.json")
RECORD_SHA = "ed27583beb8b9f95b23ce3c51d18817ee1d9a1a42043b0c773138b028da9c42a"
TOPUP_RESULT = os.path.join(HERE, "fetch_topup_result.json")
RAW = "data/negatives/gbif_negatives_{R}.csv"
TOPUP_YEARS = (2023, 2024)
STRATA_CANDIDATES = (
    ("S1", ((2020,), (2021,), (2022,), (2023,), (2024,))),
    ("S2", ((2020,), (2021,), (2022,), (2023, 2024))),
    ("S3", ((2020,), (2021,), (2022, 2023, 2024))),
)
SPECIES_TVD_MAX = 0.10      # CR-0021 section 4 tolerance
UNCERT_PP_MAX = 10.0        # CR-0021 section 4 tolerance (percentage points)
SUPPLY_RATIO_NAME = 0.8     # report-only (CR-0021 section 4)
N_PERM = 1000
PERM_SEED = 0
OUT_LINES = []


def out(s=""):
    print(s)
    OUT_LINES.append(str(s))


# ---------------------------------------------------------------------------
# Pure helpers (unit-tested in tests/test_cr0021.py)
# ---------------------------------------------------------------------------
def check_strata(strata, year_min):
    """Problems with a strata tuple: increasing, contiguous, disjoint, from year_min."""
    probs = []
    flat = [y for s in strata for y in s]
    if not strata or any(len(s) == 0 for s in strata):
        probs.append("empty stratum or no strata")
    elif flat != list(range(flat[0], flat[0] + len(flat))):
        probs.append(f"years not increasing, contiguous and disjoint: {flat}")
    elif flat[0] != year_min:
        probs.append(f"first year {flat[0]} != YEAR_MIN {year_min}")
    return probs


def stratum_of(years, strata):
    """Index of the stratum holding each year; ValueError for any other."""
    look = {y: i for i, s in enumerate(strata) for y in s}
    out_ = []
    for y in years:
        if pd.isna(y) or int(y) not in look:
            raise ValueError(f"year {y} lies in no stratum of {strata}")
        out_.append(look[int(y)])
    return np.array(out_, dtype=np.int64)


def auc(pos, neg):
    """Mann-Whitney AUC of the score for label 1 (ties count 1/2)."""
    p = np.asarray(pos, float)
    n = np.asarray(neg, float)
    if len(p) == 0 or len(n) == 0:
        return float("nan")
    ranks = pd.Series(np.concatenate([p, n])).rank().to_numpy()
    return (ranks[:len(p)].sum() - len(p) * (len(p) + 1) / 2) / (len(p) * len(n))


def tvd(a, b):
    """Total-variation distance between the value distributions of a and b."""
    pa = pd.Series(a).value_counts(normalize=True)
    pb = pd.Series(b).value_counts(normalize=True)
    idx = pa.index.union(pb.index)
    if len(pa) == 0 or len(pb) == 0:
        return float("nan")
    return 0.5 * float((pa.reindex(idx, fill_value=0) - pb.reindex(idx, fill_value=0)).abs().sum())


def cell_permutation_null(cells, n_perm=N_PERM, seed=PERM_SEED):
    """AUC null for `cells` = [(years, labels)], labels permuted within
    each cell (counts kept), AUC pooled over cells. Returns the array."""
    rng = np.random.default_rng(seed)
    years = np.concatenate([c[0] for c in cells]).astype(float)
    res = np.empty(n_perm)
    for i in range(n_perm):
        labs = np.concatenate([rng.permutation(np.asarray(c[1])) for c in cells])
        res[i] = auc(years[labs == 1], years[labs == 0])
    return res


def feasibility(pos, pool, strata, C, regions):
    """Per (region, split, stratum): n_pos, n, n_nv, n_hab, NonVeg supply,
    habitat supply, SHORT. Same arithmetic as Stratified.draw_select."""
    nv_all = A.bool_array(pool["is_nonveg"])
    pk = stratum_of(pool["year"], strata)
    rows = []
    for R in regions:
        for s in A.SPLITS:
            P = pos[R][pos[R]["split"] == s]
            ppk = stratum_of(P["year"], strata)
            cell = ((pool["region"] == R) & (pool["split"] == s)).to_numpy()
            for k, st in enumerate(strata):
                n_pos = int((ppk == k).sum())
                n = A.py_round(n_pos * C["NEG_RATIO"])
                m = cell & (pk == k)
                snv, shab = int((m & nv_all).sum()), int((m & ~nv_all).sum())
                n_nv = min(A.py_round(n * C["NONVEG_MAX_FRAC"]), snv)
                n_hab = n - n_nv
                rows.append(dict(region=R, split=s, stratum=st[0], n_pos=n_pos, n=n,
                                 n_nv=n_nv, n_hab=n_hab, nv_supply=snv, hab_supply=shab,
                                 short=max(0, n_hab - shab)))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Replay subclasses
# ---------------------------------------------------------------------------
class Capture(A.Replay):
    """The unmodified replay, keeping the pool's step-3 and step-5 frames."""

    def dedup(self, cand):
        d = super().dedup(cand)
        self.cap_dedup = d.copy()
        return d

    def thin(self, lons, lats, xs, ys, frame=None):
        keep = super().thin(lons, lats, xs, ys, frame=frame)
        if frame is not None and "nonveg_landcover" not in frame.columns:   # the pool, not P
            self.cap_thin_in = frame.copy()
            self.cap_thin_keep = np.asarray(keep, dtype=bool)
        return keep


class Stratified(Capture):
    """CR-0021 section 2 B: the draw per (region, split, stratum)."""

    def __init__(self, root, cfg, strata, **kw):
        super().__init__(root, cfg, **kw)
        self.strata = tuple(tuple(int(y) for y in s) for s in strata)

    def draw_select(self, seed=None, record=True):
        seed = self.seed() if seed is None else seed
        pool = self.pool_full
        nv_all = A.bool_array(pool["is_nonveg"])
        try:
            pk = stratum_of(pool["year"], self.strata)
        except ValueError as e:
            raise A.ReplayError(f"pool: {e}")
        picked = []
        for R in self.regions:
            for s in A.SPLITS:
                P = self.pos[R][self.pos[R]["split"] == s]
                try:
                    ppk = stratum_of(P["year"], self.strata)
                except ValueError as e:
                    raise A.ReplayError(f"[{R}/{s}] positives: {e}")
                cell = ((pool["region"] == R) & (pool["split"] == s)).to_numpy()
                tot = {"n": 0, "n_nv": 0, "n_hab": 0}
                per = {}
                for k, st in enumerate(self.strata):
                    n = A.py_round(int((ppk == k).sum()) * self.C["NEG_RATIO"])
                    m = cell & (pk == k)
                    nv, hab = pool[m & nv_all], pool[m & ~nv_all]
                    n_nv = min(A.py_round(n * self.C["NONVEG_MAX_FRAC"]), len(nv))
                    n_hab = n - n_nv
                    if len(hab) < n_hab:
                        raise A.ReplayError(f"[{R}/{s}/{st[0]}] habitat pool {len(hab)} "
                                            f"< habitat target {n_hab}")
                    picked.extend([self.es_take(hab, n_hab, seed),
                                   self.es_take(nv, n_nv, seed)])
                    per[str(st[0])] = {"n": int(n), "n_nv": int(n_nv), "n_hab": int(n_hab)}
                    for key, v in (("n", n), ("n_nv", n_nv), ("n_hab", n_hab)):
                        tot[key] += int(v)
                if record:
                    self.draw_counts.setdefault(R, {})[s] = {**tot, "strata": per}
        return pd.concat(picked, ignore_index=True)


# ---------------------------------------------------------------------------
# Reporting helpers (real data)
# ---------------------------------------------------------------------------
def keys5(df, d=5):
    lo, la = A.key_arrays(df, d)
    return list(zip(lo.tolist(), la.tolist()))


def block_of(df, cfg):
    x, y = A.to_5070(df["longitude"].to_numpy(dtype=float), df["latitude"].to_numpy(dtype=float))
    return A.block_ids(x, y, cfg)


def county_of(df, root, cfg):
    """County GEOID per row (TIGER polygons, undissolved); None if unavailable."""
    try:
        import geopandas as gpd
        cp = cfg["paths"]["county_polygons"]
        g = gpd.read_file(os.path.join(root, cp["path"]), where=cp["where"],
                          engine="pyogrio").to_crs(cp["target_crs"])
        col = "GEOID" if "GEOID" in g.columns else "COUNTYFP"
        pts = gpd.GeoDataFrame(geometry=gpd.points_from_xy(df["longitude"], df["latitude"]),
                               crs=cp["target_crs"])
        j = gpd.sjoin(pts, g[[col, "geometry"]], how="left", predicate="within")
        j = j[~j.index.duplicated(keep="first")]
        return j[col].astype(str).to_numpy()
    except Exception as e:      # report-only axis: never blocks
        out(f"  [county occupancy unavailable: {type(e).__name__}: {e}]")
        return None


def verify_trees(cfg, scratch):
    """Step 0. Returns a list of problems."""
    probs = []
    if A.sha256_file(RECORD) != RECORD_SHA:
        return [f"{RECORD}: sha256 differs from the pinned CR-0019 record"], None
    with open(RECORD) as f:
        rec = json.load(f)
    if os.path.realpath(scratch) == os.path.realpath(ROOT):
        return ["--scratch is the live tree"], None
    for rel, h in rec["artifacts"].items():
        if A.sha256_file(os.path.join(ROOT, rel)) != h:
            probs.append(f"live {rel}: differs from the record (stale pre-registration)")
    raw = {RAW.format(R=R) for R in cfg["constants"]["REGIONS"]}
    with open(TOPUP_RESULT) as f:
        topup = json.load(f)
    for rel, h in rec["inputs"].items():
        live, scr = os.path.join(ROOT, rel), os.path.join(scratch, rel)
        if rel in raw:
            if A.sha256_file(live) != h:
                probs.append(f"live {rel}: differs from the record")
            with open(live, "rb") as f1, open(scr, "rb") as f2:
                lb, sb = f1.read(), f2.read()
            if not sb.startswith(lb):
                probs.append(f"scratch {rel}: live bytes are not an exact prefix")
            if A.sha256_file(scr) != topup["files"][rel]["post_sha256"]:
                probs.append(f"scratch {rel}: sha256 != fetch_topup_result.json post_sha256")
        elif rel.lower().endswith((".tif", ".tiff")):
            if os.path.realpath(scr) != os.path.realpath(live):
                probs.append(f"scratch {rel}: not the live raster (realpath)")
        elif not os.path.exists(scr) or A.sha256_file(scr) != h:
            probs.append(f"scratch {rel}: missing or differs from the record")
    return probs, topup


def control(cfg):
    """Step 1. The unmodified replay reproduces today's files."""
    ctl = Capture(ROOT, cfg).run(stop_on_error=True)
    ok = True
    for R in ctl.regions:
        for kind, frame in (("thinned_positives", ctl.pos[R]), ("negatives", ctl.neg[R])):
            disk = A.read_csv(os.path.join(ROOT, A.rpath(cfg, kind, R)))
            same = (len(disk) == len(frame) and keys5(disk) == keys5(frame)
                    and disk["split"].astype(str).tolist() == frame["split"].astype(str).tolist()
                    and disk["year"].astype(int).tolist() == frame["year"].astype(int).tolist())
            if kind == "thinned_positives":
                same &= disk["block_id"].astype(str).tolist() == frame["block_id"].astype(str).tolist()
            ok &= same
            out(f"  control {kind:18s} {R}: replay == disk: {same}")
    Bd = A.read_csv(os.path.join(ROOT, A.rpath(cfg, "block_assignments")))
    sameB = Bd.astype(str).values.tolist() == ctl.B.astype(str).values.tolist()
    Cd = A.read_csv(os.path.join(ROOT, A.rpath(cfg, "candidate_pool")))
    sameC = (len(Cd) == len(ctl.pool) and keys5(Cd) == keys5(ctl.pool)
             and Cd["split"].astype(str).tolist() == ctl.pool["split"].astype(str).tolist()
             and Cd["year"].astype(int).tolist() == ctl.pool["year"].astype(int).tolist())
    out(f"  control block_assignments: {sameB}; candidate_pool (keys, split, year): {sameC}")
    return ctl, (ok and sameB and sameC)


def two_state_keys(scratch, cfg):
    """Step 2. 5 dp keys filed under two states after pool steps 1-2."""
    frames = []
    for R in cfg["constants"]["REGIONS"]:
        g = A.read_csv(os.path.join(scratch, RAW.format(R=R)))
        frames.append(g)
    c = pd.concat(frames, ignore_index=True)
    C = cfg["constants"]
    c = c[~(c["year"].notna() & (c["year"] < C["YEAR_MIN"]))]
    c = c[~(c["coord_uncertainty_m"] > C["MAX_COORD_UNCERTAINTY_M"]).fillna(False).astype(bool)]
    lo, la = A.key_arrays(c, C["KEY_DECIMALS"])
    ns = c.assign(_lo=lo, _la=la).groupby(["_lo", "_la"])["state"].nunique()
    return int((ns > 1).sum())


def supply_table(pool, label):
    nv = A.bool_array(pool["is_nonveg"])
    t = (pool.assign(_nv=nv).groupby(["region", "split", "year", "_nv"]).size()
         .unstack("_nv", fill_value=0))
    out(f"  pool supply {label} (region split year: habitat / NonVeg):")
    for (R, s, y), r in t.iterrows():
        out(f"    {R} {s} {int(y)}: {int(r.get(False, 0))} / {int(r.get(True, 0))}")


def losses(ctl, new, cfg, new_ids):
    """Existing pool rows lost or relabelled by the new rows, by mechanism."""
    d = cfg["constants"]["KEY_DECIMALS"]
    w0 = dict(zip(keys5(ctl.cap_dedup, d), ctl.cap_dedup["gbif_id"].astype(str)))
    w1 = dict(zip(keys5(new.cap_dedup, d), new.cap_dedup["gbif_id"].astype(str)))
    won = {k for k, g in w1.items() if k in w0 and g != w0[k] and g in new_ids}
    ny = dict(zip(keys5(new.cap_dedup, d), new.cap_dedup["year"]))
    p0 = ctl.pool_full
    k0 = keys5(p0, d)
    k1 = set(keys5(new.pool_full, d))
    y0 = dict(zip(k0, p0["year"].astype(int)))
    rel = {}
    lost = {"key_won": [], "thinning": [], "other": []}
    t_in, t_keep = new.cap_thin_in, new.cap_thin_keep
    thinned_out = set(k for k, kp in zip(keys5(t_in, d), t_keep) if not kp)
    for k, R, s in zip(k0, p0["region"], p0["split"]):
        if k in won:
            yn = int(ny[k]) if pd.notna(ny[k]) else -1
            rel.setdefault((R, s, y0[k], yn), 0)
            rel[(R, s, y0[k], yn)] += 1
            if k not in k1:
                lost["key_won"].append((R, s, y0[k]))
        elif k not in k1:
            lost["thinning" if k in thinned_out else "other"].append((R, s, y0[k]))
    out("  existing pool rows affected by the new rows:")
    out(f"    (1) key won by a new row (smaller gbif_id): {len(won)} keys; year relabels "
        f"(region split old->new: n): {dict(sorted(rel.items()))}")
    for mech in ("key_won", "thinning", "other"):
        cnt = pd.Series([f"{R} {s} {y}" for R, s, y in lost[mech]]).value_counts().sort_index()
        out(f"    lost from the pool via {mech}: {len(lost[mech])} {dict(cnt)}")
    if lost["other"]:
        out("    NOTE: 'other' should be 0 (a lost row neither key-won nor thinned)")


def comparability(live_raw, scr_raw, new_pool, cfg, root):
    """Section 4 comparability of the new rows; returns tolerance failures."""
    fails = []
    out("  comparability (a = new 2023-24, b = existing 2023-24, c = existing 2020-22):")
    for R in cfg["constants"]["REGIONS"]:
        old = live_raw[R]
        old_ids = set(old["gbif_id"].astype(str))
        sc = scr_raw[R]
        a = sc[~sc["gbif_id"].astype(str).isin(old_ids)]
        b = old[old["year"].isin(TOPUP_YEARS)]
        c = old[old["year"].between(cfg["constants"]["YEAR_MIN"], min(TOPUP_YEARS) - 1)]
        poolR = new_pool[new_pool["region"] == R]
        pid = set(poolR["gbif_id"].astype(str))
        for stage, (aa, bb, cc) in (("raw", (a, b, c)),
                                    ("pool", tuple(x[x["gbif_id"].astype(str).isin(pid)]
                                                   for x in (a, b, c)))):
            sp = tvd(aa["common_name"], bb["common_name"])
            un = [100 * x["coord_uncertainty_m"].notna().mean() if len(x) else float("nan")
                  for x in (aa, bb, cc)]
            blk = tvd(block_of(aa, cfg), block_of(bb, cfg)) if len(aa) and len(bb) else float("nan")
            ca, cb = county_of(aa, root, cfg), county_of(bb, root, cfg)
            cty = tvd(ca, cb) if ca is not None and cb is not None else float("nan")
            out(f"    {R} {stage}: n a/b/c {len(aa)}/{len(bb)}/{len(cc)}; species TVD(a,b) "
                f"{sp:.4f} (tol {SPECIES_TVD_MAX}); non-null coord_uncertainty_m % a/b/c "
                f"{un[0]:.1f}/{un[1]:.1f}/{un[2]:.1f} (tol +/-{UNCERT_PP_MAX} pp a vs b); "
                f"block TVD(a,b) {blk:.4f}, county TVD(a,b) {cty:.4f} (report-only); "
                f"species TVD(a,c) {tvd(aa['common_name'], cc['common_name']):.4f} (context)")
            if not (sp <= SPECIES_TVD_MAX):
                fails.append(f"{R} {stage}: species TVD {sp:.4f} > {SPECIES_TVD_MAX}")
            if not (abs(un[0] - un[1]) <= UNCERT_PP_MAX):
                fails.append(f"{R} {stage}: coord_uncertainty_m share differs by "
                             f"{abs(un[0] - un[1]):.1f} pp > {UNCERT_PP_MAX}")
    return fails


def yields(live_raw, scr_raw, new_pool, topup):
    out("  per-partition yield of the new rows (raw -> pool rows):")
    pid = set(new_pool["gbif_id"].astype(str))
    for R in live_raw:
        old_ids = set(live_raw[R]["gbif_id"].astype(str))
        a = scr_raw[R][~scr_raw[R]["gbif_id"].astype(str).isin(old_ids)]
        for (sp, y), g in a.groupby(["common_name", "year"]):
            n_pool = int(g["gbif_id"].astype(str).isin(pid).sum())
            out(f"    {R} {sp} {int(y)}: {len(g)} -> {n_pool}")
    zero = [t for t in topup["partitions"] if t["existing"] == 0]
    exh = [t for t in topup["partitions"] if t.get("exhausted")]
    out(f"  zero-e partitions (no top-up): {[(t['region'], t['species'], t['year']) for t in zero]}")
    out(f"  exhausted partitions: {[(t['region'], t['species'], t['year']) for t in exh]}")


def o11(P, N, strata, label):
    """O11a and O11w, per region and pooled, each split and pooled; returns
    the pooled O11w criterion results for merged strata."""
    crit = []
    for subset in ("train", "val", "pooled"):
        Ps = P if subset == "pooled" else P[P["split"] == subset]
        Ns = N if subset == "pooled" else N[N["split"] == subset]
        reg = {R: auc(Ps[Ps.region == R]["year"], Ns[Ns.region == R]["year"])
               for R in sorted(P["region"].unique())}
        out(f"  O11a {label} [{subset}]: pooled {auc(Ps['year'], Ns['year']):.4f}; "
            + ", ".join(f"{R} {v:.4f}" for R, v in reg.items()))
    for st in strata:
        if len(st) < 2:
            continue
        Pk, Nk = P[P["year"].isin(st)], N[N["year"].isin(st)]
        for scope in ["pooled"] + sorted(P["region"].unique()):
            Pc = Pk if scope == "pooled" else Pk[Pk.region == scope]
            Nc = Nk if scope == "pooled" else Nk[Nk.region == scope]
            obs = auc(Pc["year"], Nc["year"])
            cells = []
            for (R, s), g in pd.concat([Pc.assign(_l=1), Nc.assign(_l=0)]).groupby(["region", "split"]):
                cells.append((g["year"].to_numpy(), g["_l"].to_numpy()))
            null = cell_permutation_null(cells) if cells else np.array([np.nan])
            p99 = float(np.nanpercentile(null, 99))
            out(f"  O11w {label} stratum {st} [{scope}]: {obs:.4f} (effect {obs - 0.5:+.4f}); "
                f"null p50 {np.nanpercentile(null, 50):.4f}, p99 {p99:.4f}; "
                f"{'ABOVE' if obs > p99 else 'within'} p99")
            if scope == "pooled":
                crit.append((st, obs, p99))
    return crit


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--scratch", required=True, help="the tree fetch_topup.py topped up")
    a = ap.parse_args(argv)
    os.chdir(ROOT)
    cfg = A.load_config()
    C = cfg["constants"]
    regions = C["REGIONS"]
    out(f"CR-0021 pre-registration; config sha256 {cfg['_sha256']}; scratch "
        f"{os.path.realpath(a.scratch)}")

    out("0. trees")
    if not os.path.exists(TOPUP_RESULT):
        out(f"  {TOPUP_RESULT} missing: run fetch_topup.py first")
        return finish(1)
    probs, topup = verify_trees(cfg, a.scratch)
    for p in probs:
        out(f"  PROBLEM {p}")
    out(f"  trees ok: {not probs}")
    if probs:
        return finish(1)

    out("1. CONTROL (unmodified replay on the live tree)")
    ctl, ok = control(cfg)
    if not ok:
        out("  CONTROL FAILED: the replay does not reproduce today's files")
        return finish(1)

    out("2. two-state keys in the topped-up candidates")
    n2 = two_state_keys(a.scratch, cfg)
    out(f"  keys under two states: {n2}")
    if n2:
        return finish(3)

    out("3. topped-up pool (replay on SCRATCH, draw not run)")
    probe = Capture(a.scratch, cfg)
    probe.run_positives()
    probe.run_pool()
    sameP = all(probe.pos[R].astype(str).values.tolist() == ctl.pos[R].astype(str).values.tolist()
                for R in regions)
    sameB = probe.B.astype(str).values.tolist() == ctl.B.astype(str).values.tolist()
    out(f"  positives and blocks unchanged by the top-up: P {sameP}, B {sameB}")
    if not (sameP and sameB):
        out("  P or B changed: the top-up must not touch the positives")
        return finish(1)
    supply_table(ctl.pool_full, "before")
    supply_table(probe.pool_full, "after")
    live_raw = {R: A.read_csv(os.path.join(ROOT, RAW.format(R=R))) for R in regions}
    scr_raw = {R: A.read_csv(os.path.join(a.scratch, RAW.format(R=R))) for R in regions}
    new_ids = set(pd.concat([scr_raw[R] for R in regions])["gbif_id"].astype(str)) - \
        set(pd.concat([live_raw[R] for R in regions])["gbif_id"].astype(str))
    out(f"  new raw rows: {len(new_ids)}")
    losses(ctl, probe, cfg, new_ids)
    yields(live_raw, scr_raw, probe.pool_full, topup)
    tol_fails = comparability(live_raw, scr_raw, probe.pool_full, cfg, a.scratch)
    out(f"  comparability tolerances: {'met' if not tol_fails else 'EXCEEDED -> user decision'}")
    for f_ in tol_fails:
        out(f"    {f_}")

    out("4. strata selection (S1 -> S2 -> S3; first with zero SHORT; before any AUC)")
    chosen = None
    for name, strata in STRATA_CANDIDATES:
        bad = check_strata(strata, C["YEAR_MIN"])
        if bad:
            out(f"  {name}: invalid {bad}")
            continue
        try:
            t = feasibility(probe.pos, probe.pool_full, strata, C, regions)
        except ValueError as e:
            out(f"  {name}: a year lies outside the strata ({e})")
            continue
        n_short = int((t["short"] > 0).sum())
        out(f"  {name} {strata}: SHORT cells {n_short}, total shortfall {int(t['short'].sum())}")
        for r in t.itertuples():
            ratio = r.n_hab / r.hab_supply if r.hab_supply else float("inf")
            flag = (f"  SHORT {r.short}" if r.short else "") + \
                   (f"  [n_hab/supply {ratio:.2f} > {SUPPLY_RATIO_NAME}]" if ratio > SUPPLY_RATIO_NAME else "")
            out(f"    {r.region} {r.split} {r.stratum}: n_pos {r.n_pos} n {r.n} n_nv {r.n_nv} "
                f"n_hab {r.n_hab} | NonVeg {r.nv_supply} habitat {r.hab_supply} "
                f"ratio {ratio:.2f}{flag}")
        if n_short == 0 and chosen is None:
            chosen = (name, strata)
            break
    if chosen is None:
        out("  NO FEASIBLE STRATA among S1-S3: the CR returns to the user (no AUC computed)")
        return finish(2)
    out(f"  CHOSEN: {chosen[0]} {chosen[1]}")

    out("5. stratified draw on SCRATCH")
    new = Stratified(a.scratch, cfg, chosen[1]).run(stop_on_error=True)
    out(f"  draw: {json.dumps(new.draw_counts, sort_keys=True)}")

    out("6. O11 (after the strata are fixed)")
    P = pd.concat([ctl.pos[R] for R in regions], ignore_index=True)
    N0 = pd.concat([ctl.neg[R] for R in regions], ignore_index=True)
    N1 = pd.concat([new.neg[R] for R in regions], ignore_index=True)
    o11(P, N0, chosen[1], "today")
    crit = o11(P, N1, chosen[1], "predicted")
    above = [(st, obs, p99) for st, obs, p99 in crit if obs > p99]
    out(f"  O11w criterion (pooled O11w <= null p99 for every merged stratum): "
        f"{'n/a (no merged stratum)' if not crit else ('met' if not above else 'EXCEEDED -> user decision')}")

    out("7. N keys")
    k0, k1 = set(keys5(N0)), set(keys5(N1))
    out(f"  kept {len(k0 & k1)}, removed {len(k0 - k1)}, added {len(k1 - k0)}")
    for name, df in (("N today", N0), ("N predicted", N1), ("P", P)):
        out(f"  {name} years: {dict(df['year'].astype(int).value_counts().sort_index())}")

    out("")
    out(f"SUMMARY: strata {chosen[0]}; comparability tolerances "
        f"{'met' if not tol_fails else 'EXCEEDED'}; O11w criterion "
        f"{'n/a' if not crit else ('met' if not above else 'EXCEEDED')}")

    pool = new.pool_full
    pool[["region", "split", "year", "is_nonveg", "longitude", "latitude", "gbif_id"]].to_csv(
        os.path.join(HERE, "preregister_C.csv"), index=False)
    N1[["region", "split", "year", "is_nonveg", "longitude", "latitude"]].to_csv(
        os.path.join(HERE, "preregister_N.csv"), index=False)
    with open(os.path.join(HERE, "preregister_draw.json"), "w") as f:
        json.dump({"strata_id": chosen[0], "strata": [list(s) for s in chosen[1]],
                   "draw": new.draw_counts,
                   "post_topup_sha256": {rel: d["post_sha256"] for rel, d in topup["files"].items()}},
                  f, indent=2, sort_keys=True)
    return finish(0)


def finish(code):
    with open(os.path.join(HERE, "preregister.txt"), "w") as f:
        f.write("\n".join(OUT_LINES) + f"\nexit {code}\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
