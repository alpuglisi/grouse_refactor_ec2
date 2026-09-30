"""CR-0019 pre-registration (read-only; written before approval under
CLAUDE.md section 1 / CR-0011 A3). Computes, from today's accepted inputs,
what CR-0019's change must produce, and the numbers the CR quotes.

The change (CR-0019 section 2):
  positives step 2  keep habitat rows with year >= YEAR_MIN (2020); raise
                    on a null year;
  pool step 1       raise if any candidate year is null or < YEAR_MIN
                    (a guard; today's candidates are all 2020-2024, so it
                    changes no row - checked and printed below);
  draw              unchanged (1:1 per region and split against the new
                    positives).
Also reports, as evidence for a REJECTED option, the supply a year-matched
draw would need (year_match_feasibility).

Independent of prepare_training_data.py / generate_negatives.py: the
pipeline steps are CR-0013's replay (acceptance_split.Replay, written by a
separate agent from the CR text), subclassed here only at the one step the
change alters. CONTROL: the unmodified replay must reproduce today's
accepted P, B, C and N exactly (keys, split, block_id), or this script
aborts - so the prediction starts from the files the record accepts.

Run from the repository root (reads data/, writes only into this
directory):
    PYTHONPATH=. nice -n 10 python docs/quality/evidence/CR-0019/preregister.py

Writes, next to this file:
    preregister.txt           - the report (stdout copy)
    preregister_P.csv         - predicted positives: region, split,
                                longitude, latitude, year, block_id
    preregister_B.csv         - predicted block_assignments (block_id, split, n)
    preregister_C_split.csv   - pool rows whose split changes
                                (region, longitude, latitude, old, new)
    preregister_N.csv         - predicted negatives: region, split, year,
                                is_nonveg, longitude, latitude
"""
import os
import sys

import numpy as np
import pandas as pd

import acceptance_split as A

YEAR_MIN = 2020          # CR-0019 section 2 (regions.YEAR_MIN after the change)
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
OUT_LINES = []


def out(s=""):
    print(s)
    OUT_LINES.append(str(s))


class Floored(A.Replay):
    """The replay with CR-0019's positives step 2 (the only step it changes;
    the pool guard is a no-op on today's candidates, checked below)."""

    def habitat_rows(self, df):
        hab = super().habitat_rows(df)
        if hab["year"].isna().any():
            raise A.ReplayError("positive with no year")
        return hab[hab["year"].astype(int) >= YEAR_MIN].copy()


def year_match_feasibility(rep):
    """NOT part of CR-0019: the supply a year-matched draw (per region,
    split, year, NonVeg cap per cell, no NonVeg top-up) would need from
    the post-change pool. Evidence for CR-0019's rejected option (1b)."""
    pool = rep.pool_full
    nv_all = A.bool_array(pool["is_nonveg"])
    pyear = pool["year"].astype(int).to_numpy()
    cells = []
    for R in rep.regions:
        for s in A.SPLITS:
            P = rep.pos[R]
            P = P[P["split"] == s]
            m = ((pool["region"] == R) & (pool["split"] == s)).to_numpy()
            for y, cnt in sorted(P["year"].astype(int).value_counts().items()):
                n = A.py_round(cnt * rep.C["NEG_RATIO"])
                cell = m & (pyear == y)
                snv, shab = int((cell & nv_all).sum()), int((cell & ~nv_all).sum())
                n_nv = min(A.py_round(n * rep.C["NONVEG_MAX_FRAC"]), snv)
                cells.append((R, s, y, cnt, n, n_nv, n - n_nv, snv, shab))
    return cells


def keyset(df):
    return set(zip(df["longitude"].round(5), df["latitude"].round(5)))


def auc(pos_years, neg_years):
    """Mann-Whitney AUC of year as a score for label 1."""
    p = np.asarray(pos_years, float)
    n = np.asarray(neg_years, float)
    if len(p) == 0 or len(n) == 0:
        return float("nan")
    allv = np.concatenate([p, n])
    ranks = pd.Series(allv).rank().to_numpy()
    return (ranks[:len(p)].sum() - len(p) * (len(p) + 1) / 2) / (len(p) * len(n))


def gap_filter_counts(frames, rasters_years, tol):
    """Rows train.filter_by_year_gap would drop at tolerance tol, per class."""
    res = {}
    for cls, df in frames.items():
        drop = 0
        for R, sub in df.groupby("region"):
            yrs = rasters_years[R]
            ok = {int(y): all(min(abs(v - int(y)) for v in ys) <= tol for ys in yrs.values())
                  for y in sub["year"].unique()}
            drop += int((~sub["year"].map(lambda y: ok[int(y)])).sum())
        res[cls] = (drop, len(df))
    return res


def main():
    os.chdir(ROOT)
    cfg = A.load_config()
    out(f"CR-0019 pre-registration; config sha256 {cfg['_sha256']}; YEAR_MIN {YEAR_MIN}")
    rec = A.os.path.join(ROOT, A.rpath(cfg, "acceptance_record"))
    import json
    with open(rec) as f:
        record = json.load(f)
    bad = [rel for rel, h in record["artifacts"].items()
           if A.sha256_file(os.path.join(ROOT, rel)) != h]
    out(f"today's 20 digested artifacts equal acceptance_record.json: {not bad} {bad}")
    if bad:
        sys.exit("stale: the accepted artifacts changed")

    # ---- CONTROL: unmodified replay == today's files ----------------------
    ctl = A.Replay(ROOT, cfg).run(stop_on_error=True)
    ok = True
    for R in ctl.regions:
        for kind, frame in (("thinned_positives", ctl.pos[R]), ("negatives", ctl.neg[R])):
            disk = A.read_csv(os.path.join(ROOT, A.rpath(cfg, kind, R)))
            same = (keyset(disk) == keyset(frame) and len(disk) == len(frame))
            if kind == "thinned_positives":
                same &= (disk["split"].tolist() == frame["split"].tolist()
                         and disk["block_id"].astype(str).tolist() == frame["block_id"].astype(str).tolist())
            ok &= same
            out(f"control {kind:18s} {R}: replay == disk: {same}")
    Bd = A.read_csv(os.path.join(ROOT, A.rpath(cfg, "block_assignments")))
    sameB = Bd.astype(str).values.tolist() == ctl.B.astype(str).values.tolist()
    Cd = A.read_csv(os.path.join(ROOT, A.rpath(cfg, "candidate_pool")))
    sameC = (len(Cd) == len(ctl.pool) and Cd["split"].tolist() == ctl.pool["split"].tolist()
             and keyset(Cd) == keyset(ctl.pool))
    out(f"control block_assignments: {sameB}; candidate_pool (keys, split): {sameC}")
    if not (ok and sameB and sameC):
        sys.exit("CONTROL FAILED: the replay does not reproduce today's files")

    # ---- today's per-class year support ---------------------------------
    P0 = pd.concat([ctl.pos[R] for R in ctl.regions], ignore_index=True)
    N0 = pd.concat([ctl.neg[R] for R in ctl.regions], ignore_index=True)
    out("")
    out("TODAY (accepted files)")
    for name, df in (("P", P0), ("N", N0)):
        vc = df["year"].astype(int).value_counts().sort_index()
        out(f"  {name} n={len(df)} years {dict(vc)}; year < {YEAR_MIN}: "
            f"{int((df['year'] < YEAR_MIN).sum())}")
    for R in ctl.regions:
        for s in A.SPLITS:
            p = P0[(P0["region"] == R) & (P0["split"] == s)]
            out(f"  {R} {s}: P {len(p)}, pre-{YEAR_MIN} {int((p['year'] < YEAR_MIN).sum())} "
                f"({100 * (p['year'] < YEAR_MIN).mean():.2f} %); N pre-{YEAR_MIN} "
                f"{int((N0[(N0['region'] == R) & (N0['split'] == s)]['year'] < YEAR_MIN).sum())}")
    from grouse_data import GrouseData
    from models import FEATURE_SPEC
    gd = GrouseData()
    ryears = {R: {f: gd[R].raster_years(f) for f in FEATURE_SPEC if gd[R].raster_years(f)}
              for R in ctl.regions}
    for tol in (2, 1, 0):
        g = gap_filter_counts({"P": P0, "N": N0}, ryears, tol)
        out(f"  filter_by_year_gap tol {tol}: dropped P {g['P'][0]}/{g['P'][1]}, "
            f"N {g['N'][0]}/{g['N'][1]}")
    for s in A.SPLITS:
        keep = P0[(P0["split"] == s) & (P0["year"] >= YEAR_MIN)]
        nn = N0[N0["split"] == s]
        out(f"  {s} prevalence after the tol-2 filter: {len(keep)}/{len(keep) + len(nn)} = "
            f"{len(keep) / (len(keep) + len(nn)):.4f}")
    Pk = P0[P0["year"] >= YEAR_MIN]
    out(f"  year->label AUC: all rows {auc(P0['year'], N0['year']):.4f}; "
        f"after the tol-2 filter {auc(Pk['year'], N0['year']):.4f}")

    # ---- CR-0019 prediction ------------------------------------------------
    new = Floored(ROOT, cfg).run(stop_on_error=True)
    P1 = pd.concat([new.pos[R] for R in new.regions], ignore_index=True)
    N1 = pd.concat([new.neg[R] for R in new.regions], ignore_index=True)
    out("")
    out("AFTER CR-0019 (predicted)")
    out(f"  positives step counts: {new.counts['positives']}")
    for R in new.regions:
        for s in A.SPLITS:
            p0 = P0[(P0["region"] == R) & (P0["split"] == s)]
            p1 = P1[(P1["region"] == R) & (P1["split"] == s)]
            out(f"  {R} {s}: P {len(p0)} -> {len(p1)} (today post-filter "
                f"{int((p0['year'] >= YEAR_MIN).sum())}); N {len(p1)}")
    out(f"  total P {len(P0)} -> {len(P1)}; today post-filter {int((P0['year'] >= YEAR_MIN).sum())}")
    kP0, kP1 = keyset(P0), keyset(P1)
    kP0f = keyset(P0[P0["year"] >= YEAR_MIN])
    out(f"  P keys: kept from today {len(kP0 & kP1)}, removed {len(kP0 - kP1)} "
        f"(of which year >= {YEAR_MIN}: {len(kP0f - kP1)}), added {len(kP1 - kP0)}")
    b0 = dict(zip(ctl.B["block_id"], ctl.B["split"]))
    b1 = dict(zip(new.B["block_id"], new.B["split"]))
    flips = sorted(b for b in set(b0) & set(b1) if b0[b] != b1[b])
    out(f"  blocks: {len(b0)} -> {len(b1)} positive-occupied; vanished {len(set(b0) - set(b1))}, "
        f"new {len(set(b1) - set(b0))}, split flipped {len(flips)} "
        f"(train->val {sum(b0[b] == 'train' for b in flips)}, val->train "
        f"{sum(b0[b] == 'val' for b in flips)}); val share "
        f"{(ctl.B['split'] == 'val').mean():.6f} -> {(new.B['split'] == 'val').mean():.6f}")
    # training rows of today's P that the new split puts in validation (CR-0009 model leakage)
    m = P0.merge(P1[["longitude", "latitude", "split"]], on=["longitude", "latitude"],
                 how="inner", suffixes=("_old", "_new"))
    out(f"  today's P rows kept, split changed: train->val "
        f"{int(((m.split_old == 'train') & (m.split_new == 'val')).sum())}, val->train "
        f"{int(((m.split_old == 'val') & (m.split_new == 'train')).sum())}")
    Cs = ctl.pool[["region", "longitude", "latitude", "split"]].merge(
        new.pool[["region", "longitude", "latitude", "split"]],
        on=["region", "longitude", "latitude"], how="outer", suffixes=("_old", "_new"),
        indicator=True)
    if (Cs["_merge"] != "both").any():
        sys.exit("pool rows differ beyond split: the change should touch only step 10")
    cflip = Cs[Cs.split_old != Cs.split_new]
    out(f"  pool: {len(new.pool)} rows (unchanged set); split changes {len(cflip)} "
        f"(train->val {int((cflip.split_old == 'train').sum())}, val->train "
        f"{int((cflip.split_old == 'val').sum())})")
    out(f"  draw counts per (R, s): {new.draw_counts}")
    out(f"  year->label AUC after (no filter needed): {auc(P1['year'], N1['year']):.4f}")
    for s in A.SPLITS:
        out(f"  {s} prevalence after: {int((P1.split == s).sum())}/"
            f"{int((P1.split == s).sum()) + int((N1.split == s).sum())}")
    for tol in (2, 1, 0):
        g = gap_filter_counts({"P": P1, "N": N1}, ryears, tol)
        out(f"  filter_by_year_gap tol {tol}: dropped P {g['P'][0]}/{g['P'][1]}, "
            f"N {g['N'][0]}/{g['N'][1]}")
    for name, df in (("P", P1), ("N", N1)):
        vc = df["year"].astype(int).value_counts().sort_index()
        out(f"  {name} years after: {dict(vc)}")
    cand_years = []
    for R in new.regions:
        g = A.read_csv(os.path.join(ROOT, A.rpath(cfg, "gbif_candidates", R)))
        cand_years.append((R, len(g), int(g["year"].isna().sum()), int((g["year"] < YEAR_MIN).sum())))
    out(f"  pool guard (raw candidates: region, rows, null year, year < {YEAR_MIN}): {cand_years}")
    # source axis (PA-0020 Swept? item owned by BUG-0034): the datasetKey of
    # every raw sighting row, and the negatives' dataset key in get_negatives.py
    import glob
    import re
    dk = {}
    nrows = 0
    for f in sorted(glob.glob(os.path.join(ROOT, "data", "sightings", "*_sightings_*.csv"))):
        d = pd.read_csv(f, usecols=["datasetKey", "year"])
        nrows += len(d)
        for k, v in d["datasetKey"].value_counts().items():
            dk[k] = dk.get(k, 0) + int(v)
    with open(os.path.join(ROOT, "get_negatives.py")) as f:
        m = re.search(r'EOD_DATASET_KEY\s*=\s*"([^"]+)"', f.read())
    out(f"  source axis: {nrows} raw sighting rows, datasetKey counts {dk}; "
        f"get_negatives.EOD_DATASET_KEY {m.group(1) if m else None}")
    out("")
    out("REJECTED OPTION 1b - year-matched draw on the post-change pool (not part of CR-0019)")
    out("  cell: n_pos, n, n_nv, n_hab, NonVeg supply, habitat supply")
    short = 0
    for (R, s, y, cnt, n, n_nv, n_hab, snv, shab) in year_match_feasibility(new):
        flag = f"  SHORT {n_hab - shab}" if shab < n_hab else ""
        short += max(0, n_hab - shab)
        out(f"    {R} {s} {y}: {cnt:5d} {n:5d} {n_nv:5d} {n_hab:5d} {snv:6d} {shab:6d}{flag}")
    out(f"  total habitat shortfall {short}")
    kN0, kN1 = keyset(N0), keyset(N1)
    out(f"  N keys: kept {len(kN0 & kN1)}, removed {len(kN0 - kN1)}, added {len(kN1 - kN0)}")

    # ---- files --------------------------------------------------------------
    P1[["region", "split", "longitude", "latitude", "year", "block_id"]].to_csv(
        os.path.join(HERE, "preregister_P.csv"), index=False)
    new.B.to_csv(os.path.join(HERE, "preregister_B.csv"), index=False)
    cflip[["region", "longitude", "latitude", "split_old", "split_new"]].to_csv(
        os.path.join(HERE, "preregister_C_split.csv"), index=False)
    N1[["region", "split", "year", "is_nonveg", "longitude", "latitude"]].to_csv(
        os.path.join(HERE, "preregister_N.csv"), index=False)
    with open(os.path.join(HERE, "preregister.txt"), "w") as f:
        f.write("\n".join(OUT_LINES) + "\n")


if __name__ == "__main__":
    main()
