"""check_lidar_structure.py - CR-0036 acceptance gate for the 3DEP lidar
structure layers (generate_lidar_structure.py).

Every GATE is paired with a NEGATIVE CONTROL: a deliberately broken
version of the same input that the check MUST reject (PA-0021(a)). A gate
passes only when the real input passes AND its control fails, so a check
that cannot fail can never report PASS.

    C1 grid           grid_mismatch(out, template) is None
                      control: transform offset by half a cell
    C2 registration   road sweep (diagnose_layer_registration's continuous
                      score) on >= MIN_WINDOWS windows of SWEEP_PX cells;
                      lid_wcov5 and lid_p95 must peak at (0, 0)
                      control: layer shifted by one cell
    C3 height scale   median(lid_p95 / LANDFIRE ch) on forest cells within
                      [RATIO_LO, RATIO_HI], per work unit
                      control: lid_p95 x 3.2808 (feet read as metres)
    C4 understory     median lid_u1_3 (regenerating forest, tsd 3-10 y)
                      minus median (mature forest: tsd cap, cc >= 60 %)
                      >= MIN_REGEN_CONTRAST per mille and > the p99 of a
                      100-draw permutation null
                      control: lid_u1_3 permuted across cells
    C5 coverage       per work unit, valid share of its assigned forest
                      cells >= MIN_COVERAGE
                      control: one work unit's cells set to NODATA
    C6 seam           blocks of 64 assembled == one 128 block, bit for bit,
                      in every feature and the count bands
                      control (pilot): the same blocks computed with pad 0,
                      which must differ; (self-test): one perturbed cell
    C9 steep ground   (W3) leave-one-out ground-Z RMSE of the pinned IDW on
                      steep ground (slope >= 0.30) <= LOO_MAX_M, from the
                      generator's W3_hag_loo.json
                      control: the nearest-1 predictor (no distance limit)
    C7, C8            OBS only (project offsets, throughput) - reported by
                      the generator's pilot log, never gating here.

Usage (repository root):
    python check_lidar_structure.py --self-test
    python check_lidar_structure.py --pilot /tmp/lidar_pilot --region NH

Pilot directory layout (written by generate_lidar_structure.py --pilot):
    {W}_{feature}.tif       W in W1..W4; features LIDAR_FEATURES
    W3_hag_loo.json         C9 evidence (generate_lidar_structure.hag_loo)
    {W}_lidar_meta.tif      bands: year, doy, n_returns, n_ground,
                            n_nohag, work-unit index
    W2seam_{feature}.tif, W2seam_lidar_meta.tif
                            W2 recomputed as one 128-cell block (C6)
    W2pad0_{feature}.tif, W2pad0_lidar_meta.tif
                            W2 in 64-cell blocks with pad 0 (C6 control)
"""
import argparse
import os
import sys

import numpy as np

K = 2                         # sweep offsets -K..K (as the BUG-0094 sweep)
SWEEP_PX = 128                # window edge, cells
MIN_WINDOWS = 8               # usable sweep windows required (C2)
MIN_ROAD_CELLS = 125          # road cells per window (500 * (128/256)^2)
ROAD_M = 15.0                 # road cell: road_dist <= ROAD_M metres
SEED = 0
RATIO_LO, RATIO_HI = 0.5, 2.0  # C3 band for median lid_p95 / ch
FEET = 3.2808                 # C3 control factor
LANDFIRE_CH_PER_M = 10.0      # LANDFIRE CH is coded in decimetres
REGEN_YEARS = (3.0, 10.0)     # C4 regenerating stand age (tsd), years (B36-2-9)
MATURE_CC_PCT = 60            # C4 mature forest: LANDFIRE cc >= this
MIN_REGEN_CONTRAST = 50       # C4, per mille
N_PERM = 100                  # C4 permutation-null draws (PA-0021(c))
PERM_Q = 99.0                 # C4: real contrast must exceed this
                              # percentile of the null
MIN_CELLS = 200               # C3/C4 minimum cells per group, else FAIL
MIN_COVERAGE = 0.99           # C5
FOREST_NLCD = (41, 42, 43)
LOO_MAX_M = 0.5               # C9 steep-ground RMSE limit, metres
LOO_MIN_N = 500               # C9 minimum steep ground points
NODATA = -9999

LIDAR_FEATURES = ("lid_u05_2", "lid_u1_3", "lid_u3_5", "lid_u5_10",
                  "lid_p95", "lid_wcov5", "lid_sd")
REGISTRATION_FEATURES = ("lid_wcov5", "lid_p95")


# ----------------------------------------------------------------------
# Pure checks (arrays in, verdicts out) - what the tests exercise
# ----------------------------------------------------------------------
def _score_continuous(x, valid, road):
    on, off = x[valid & road], x[valid & ~road]
    sd = float(x[valid].std()) if valid.any() else 0.0
    if on.size < 20 or off.size < 20 or sd == 0:
        return np.nan
    return abs(float(on.mean()) - float(off.mean())) / sd


def registration_peak(layer, valid, road, window=SWEEP_PX,
                      min_road=MIN_ROAD_CELLS, seed=SEED):
    """Mean sweep score per offset over seeded windows; returns
    (best_offset, n_windows). best_offset is None when no window is
    usable. layer, valid and road share one grid."""
    H, W = layer.shape
    cand = [(r, c)
            for r in range(K, H - window - K + 1, window)
            for c in range(K, W - window - K + 1, window)
            if road[r:r + window, c:c + window].sum() >= min_road]
    if not cand:
        return None, 0
    rng = np.random.default_rng(seed)
    wins = [cand[i] for i in sorted(rng.permutation(len(cand)))]
    tab = {(dy, dx): [] for dy in range(-K, K + 1) for dx in range(-K, K + 1)}
    for r, c in wins:
        x = layer[r:r + window, c:c + window].astype(np.float64)
        v = valid[r:r + window, c:c + window]
        for (dy, dx) in tab:
            rr = road[r + dy:r + dy + window, c + dx:c + dx + window]
            tab[(dy, dx)].append(_score_continuous(x, v, rr))
    mean = {o: (float(np.nanmean(s)) if np.isfinite(s).any() else np.nan)
            for o, s in tab.items()}
    usable = [o for o in mean if np.isfinite(mean[o])]
    if not usable:
        return None, 0
    n_ok = int(np.sum(np.isfinite(tab[(0, 0)])))
    return max(usable, key=mean.get), n_ok


def check_registration(layer, valid, road):
    best, n = registration_peak(layer, valid, road)
    ok = best == (0, 0) and n >= MIN_WINDOWS
    return ok, f"peak {best}, {n} windows (need (0, 0) and >= {MIN_WINDOWS})"


def height_ratio(p95_dm, ch_coded, forest, valid):
    """Median of lid_p95 (dm) / LANDFIRE ch (coded dm) over forest cells
    where both are valid and ch > 0."""
    m = forest & valid & (ch_coded > 0) & (ch_coded != NODATA)
    if m.sum() < MIN_CELLS:
        return np.nan, int(m.sum())
    lid_m = p95_dm[m] / 10.0
    ch_m = ch_coded[m] / LANDFIRE_CH_PER_M
    return float(np.median(lid_m / ch_m)), int(m.sum())


def check_height(p95_dm, ch_coded, forest, valid):
    r, n = height_ratio(p95_dm, ch_coded, forest, valid)
    ok = np.isfinite(r) and RATIO_LO <= r <= RATIO_HI
    return ok, f"median ratio {r:.3f} over {n} cells (band [{RATIO_LO}, {RATIO_HI}])"


def regen_contrast(u13, tsd_years, cc_pct, forest, valid, tsd_cap):
    """Median lid_u1_3 in regenerating forest minus mature forest."""
    regen = forest & valid & (tsd_years >= REGEN_YEARS[0]) & \
        (tsd_years <= REGEN_YEARS[1])
    mature = forest & valid & (tsd_years >= tsd_cap - 0.5) & \
        (cc_pct >= MATURE_CC_PCT)
    if regen.sum() < MIN_CELLS or mature.sum() < MIN_CELLS:
        return np.nan, int(regen.sum()), int(mature.sum())
    return (float(np.median(u13[regen]) - np.median(u13[mature])),
            int(regen.sum()), int(mature.sum()))


def regen_null(u13, tsd_years, cc_pct, forest, valid, tsd_cap,
               n=N_PERM, seed=SEED):
    """Contrast under N_PERM permutations of u13 across valid cells."""
    rng = np.random.default_rng(seed)
    idx = np.flatnonzero(valid.ravel())
    out = []
    for _ in range(n):
        p = u13.copy()
        p.ravel()[idx] = rng.permutation(u13.ravel()[idx])
        out.append(regen_contrast(p, tsd_years, cc_pct, forest, valid,
                                  tsd_cap)[0])
    return np.asarray(out, dtype=np.float64)


def check_regen(u13, tsd_years, cc_pct, forest, valid, tsd_cap):
    d, nr, nm = regen_contrast(u13, tsd_years, cc_pct, forest, valid, tsd_cap)
    if not np.isfinite(d):
        return False, f"too few cells (regen {nr}, mature {nm}; need {MIN_CELLS})"
    null = regen_null(u13, tsd_years, cc_pct, forest, valid, tsd_cap)
    q = float(np.nanpercentile(null, PERM_Q))
    ok = d >= MIN_REGEN_CONTRAST and d > q
    return ok, (f"contrast {d:.1f} per mille (regen {nr}, mature {nm}; "
                f"need >= {MIN_REGEN_CONTRAST} and > null p{PERM_Q:g} "
                f"{q:.1f} over {N_PERM} permutations)")


def gated_units(forest, wu_index):
    """Work units with >= MIN_CELLS assigned forest cells. Smaller units
    (slivers at a project edge) are reported, never gated (A36-2-3)."""
    u, n = np.unique(wu_index[(wu_index >= 0) & forest], return_counts=True)
    return [int(a) for a, b in zip(u, n) if b >= MIN_CELLS], \
        [int(a) for a, b in zip(u, n) if b < MIN_CELLS]


def coverage(valid, forest, wu_index):
    """Valid share of assigned forest cells, per gated work unit."""
    gated, _ = gated_units(forest, wu_index)
    return {w: float(valid[forest & (wu_index == w)].mean()) for w in gated}


def check_coverage(valid, forest, wu_index):
    cov = coverage(valid, forest, wu_index)
    _, slivers = gated_units(forest, wu_index)
    ok = bool(cov) and min(cov.values()) >= MIN_COVERAGE
    txt = ", ".join(f"wu{w}={v:.4f}" for w, v in sorted(cov.items()))
    sl = f"; slivers (OBS) {slivers}" if slivers else ""
    return ok, f"{txt or 'no gated work units'} (need >= {MIN_COVERAGE}){sl}"


def check_seam(a, b):
    """a, b: dict name -> array (all features and the meta count bands),
    or two arrays. Bit-identical in every entry."""
    if not isinstance(a, dict):
        a, b = {"x": a}, {"x": b}
    bad = [k for k in a if k not in b or a[k].shape != b[k].shape
           or not np.array_equal(a[k], b[k])]
    return not bad, "bit-identical" if not bad else f"differs: {bad}"


def check_loo(loo, key):
    """C9: RMSE of predictor `key` on steep ground <= LOO_MAX_M."""
    st = loo.get("steep") or {}
    n, v = int(st.get("n") or 0), st.get(key)
    ok = n >= LOO_MIN_N and v is not None and v <= LOO_MAX_M
    return ok, (f"steep RMSE {v} m over {n} ground points "
                f"(need <= {LOO_MAX_M} and n >= {LOO_MIN_N})")


def gate(name, real, control):
    """PASS only if the real input passes and the broken one fails."""
    r_ok, r_msg = real
    c_ok, c_msg = control
    ok = r_ok and not c_ok
    print(f"   {name:16s} {'PASS' if ok else 'FAIL'}  real: "
          f"{'pass' if r_ok else 'fail'} ({r_msg}); control: "
          f"{'REJECTED' if not c_ok else 'ACCEPTED (check cannot fail)'} "
          f"({c_msg})")
    return ok


# Negative controls -----------------------------------------------------
def shift_one(a, fill):
    out = np.full_like(a, fill)
    out[1:, 1:] = a[:-1, :-1]
    return out


def as_feet(p95_dm):
    return np.rint(p95_dm * FEET)


def permute(a, valid, seed=SEED):
    out = a.copy()
    idx = np.flatnonzero(valid.ravel())
    out.ravel()[idx] = np.random.default_rng(seed).permutation(
        a.ravel()[idx])
    return out


def drop_unit(valid, wu_index, forest):
    w = np.unique(wu_index[(wu_index >= 0) & forest])
    out = valid.copy()
    if w.size:
        out[wu_index == w[0]] = False
    return out


def perturb_one(a):
    out = a.copy()
    out.flat[out.size // 2] += 1
    return out


def check_grid(src, template):
    from grouse_data import grid_mismatch
    mm = grid_mismatch(src, template)
    return mm is None, mm or "same grid"


class _Grid:
    """Minimal stand-in with the attributes grid_mismatch reads."""
    def __init__(self, crs, transform):
        self.crs, self.transform = crs, transform


def half_cell_off(src):
    from rasterio.transform import Affine
    t = src.transform
    return _Grid(src.crs, Affine(t.a, t.b, t.c + t.a / 2, t.d, t.e, t.f))


# ----------------------------------------------------------------------
# Self-test: a synthetic world where every real check passes
# ----------------------------------------------------------------------
def synthetic_world(n=520, seed=1):
    rng = np.random.default_rng(seed)
    road = np.zeros((n, n), bool)
    for k in range(10, n, 37):
        road[k, :] = True
        road[:, (k * 3) % n] = True
    forest = rng.random((n, n)) < 0.8
    forest &= ~road
    tsd_cap = 30.0
    tsd = np.where(rng.random((n, n)) < 0.3, rng.uniform(1, 25, (n, n)),
                   tsd_cap)
    cc = np.where(tsd >= tsd_cap - 0.5, rng.integers(60, 95, (n, n)),
                  rng.integers(5, 60, (n, n)))
    ch = np.where(forest, rng.integers(120, 260, (n, n)), 0)   # dm
    p95 = np.where(forest, np.rint(ch * rng.uniform(0.85, 1.15, (n, n))),
                   rng.integers(0, 20, (n, n)))
    wcov = np.where(road, rng.integers(0, 150, (n, n)),
                    np.where(forest, rng.integers(500, 950, (n, n)),
                             rng.integers(0, 300, (n, n))))
    regen = (tsd >= REGEN_YEARS[0]) & (tsd <= REGEN_YEARS[1])
    u13 = np.where(regen, rng.integers(250, 500, (n, n)),
                   rng.integers(20, 150, (n, n)))
    valid = np.ones((n, n), bool)
    wu = np.where(np.arange(n)[None, :] < n // 2, 0, 1) * np.ones((n, 1), int)
    return dict(road=road, forest=forest, tsd=tsd, tsd_cap=tsd_cap, cc=cc,
                ch=ch, p95=p95, wcov=wcov, u13=u13, valid=valid, wu=wu,
                v_p95=valid, v_wcov=valid, v_u13=valid)


def run_checks(w, seam=None):
    """All array checks with their controls; True if every gate PASSes."""
    ok = True
    for f, layer, v in (("lid_wcov5", w["wcov"], w["v_wcov"]),
                        ("lid_p95", w["p95"], w["v_p95"])):
        ok &= gate(f"C2 {f}",
                   check_registration(layer, v, w["road"]),
                   check_registration(shift_one(layer, 0),
                                      shift_one(v, False), w["road"]))
    for u in gated_units(w["forest"], w["wu"])[0]:
        m = w["wu"] == u
        ok &= gate(f"C3 wu{u}",
                   check_height(w["p95"], w["ch"], w["forest"] & m,
                                w["v_p95"]),
                   check_height(as_feet(w["p95"]), w["ch"], w["forest"] & m,
                                w["v_p95"]))
    ok &= gate("C4 understory",
               check_regen(w["u13"], w["tsd"], w["cc"], w["forest"],
                           w["v_u13"], w["tsd_cap"]),
               check_regen(permute(w["u13"], w["v_u13"]), w["tsd"], w["cc"],
                           w["forest"], w["v_u13"], w["tsd_cap"]))
    ok &= gate("C5 coverage",
               check_coverage(w["v_p95"], w["forest"], w["wu"]),
               check_coverage(drop_unit(w["v_p95"], w["wu"], w["forest"]),
                              w["forest"], w["wu"]))
    if seam is not None:
        a, b = seam
        ok &= gate("C6 seam", check_seam(a, b), check_seam(a, perturb_one(b)))
    return ok


def self_test():
    print("Self-test (synthetic world):")
    w = synthetic_world()
    from rasterio.crs import CRS
    from rasterio.transform import from_origin
    t = from_origin(1_000_000, 2_000_000, 30, 30)
    g = _Grid(CRS.from_epsg(5070), t)
    ok = gate("C1 grid", check_grid(g, g), check_grid(half_cell_off(g), g))
    ok &= run_checks(w, seam=(w["p95"], w["p95"].copy()))
    print(f"Self-test: {'PASS' if ok else 'FAIL'}")
    return ok


# ----------------------------------------------------------------------
# Pilot mode: read the generator's pilot outputs and the on-disk refs
# ----------------------------------------------------------------------
def _read_ref_window(rd, feature, year, out_src):
    """The reference raster's cells under out_src's extent. Refuses if the
    reference is not on the same grid (integer offset)."""
    import rasterio
    from rasterio.windows import Window
    from grouse_data import grid_mismatch
    path = rd.raster_path(feature, year)
    with rasterio.open(path) as ref:
        mm = grid_mismatch(out_src, ref)
        if mm is not None:
            raise SystemExit(f"{feature}: pilot not on its grid ({mm})")
        col = int(round((out_src.transform.c - ref.transform.c)
                        / ref.transform.a))
        row = int(round((out_src.transform.f - ref.transform.f)
                        / ref.transform.e))
        return ref.read(1, window=Window(col, row, out_src.width,
                                         out_src.height), boundless=True,
                        fill_value=NODATA)


def _read_set(directory, prefix):
    """Every feature plus the meta count bands (returns, ground, no-HAG)
    of one pilot output set; raises FileNotFoundError if any is missing."""
    import rasterio
    out = {}
    for f in LIDAR_FEATURES:
        p = os.path.join(directory, f"{prefix}_{f}.tif")
        if not os.path.exists(p):
            raise FileNotFoundError(2, "missing", p)
        with rasterio.open(p) as s:
            out[f] = s.read(1)
    p = os.path.join(directory, f"{prefix}_lidar_meta.tif")
    if not os.path.exists(p):
        raise FileNotFoundError(2, "missing", p)
    with rasterio.open(p) as s:
        for b, name in ((3, "n_returns"), (4, "n_ground"), (5, "n_nohag")):
            out[name] = s.read(b)
    return out


def pilot(directory, region):
    import rasterio
    from grouse_data import GrouseData
    from models import TSD_MAX_YEARS, road_dist_decode, tsd_decode
    rd = GrouseData()[region]
    ok = True
    for W in ("W1", "W2", "W3", "W4"):
        meta_p = os.path.join(directory, f"{W}_lidar_meta.tif")
        if not os.path.exists(meta_p):
            print(f"{W}: missing {meta_p} - FAIL")
            ok = False
            continue
        print(f"\n{W}:")
        with rasterio.open(meta_p) as m:
            years, wu = m.read(1), m.read(6)
        yr = int(np.median(years[years > 0])) if (years > 0).any() else 2020
        lay = {}
        for f in LIDAR_FEATURES:
            with rasterio.open(os.path.join(directory, f"{W}_{f}.tif")) as s, \
                    rasterio.open(rd.latest_raster_path("evt")) as tmpl:
                lay[f] = s.read(1).astype(np.float64)
                src = _Grid(s.crs, s.transform)
                src.width, src.height = s.width, s.height
                ok &= gate(f"C1 {f}", check_grid(s, tmpl),
                           check_grid(half_cell_off(s), tmpl))
        vf = {f: lay[f] != NODATA for f in LIDAR_FEATURES}   # per feature
        nlcd = _read_ref_window(rd, "nlcd", yr, src)
        forest = np.isin(nlcd, FOREST_NLCD)
        ch = _read_ref_window(rd, "ch", yr, src).astype(np.float64)
        cc = _read_ref_window(rd, "cc", yr, src).astype(np.float64)
        tsd = tsd_decode(_read_ref_window(rd, "tsd", yr, src))
        used = {f: rd.raster_path(f, yr) for f in ("ch", "cc", "tsd", "nlcd")}
        print("   reference rasters used: " + ", ".join(
            f"{k}={os.path.basename(v)}" for k, v in used.items()))
        rraw = _read_ref_window(rd, "road_dist", yr, src)
        road = (road_dist_decode(rraw) <= ROAD_M) & (rraw != NODATA)
        w = dict(road=road, forest=forest, tsd=tsd, tsd_cap=TSD_MAX_YEARS,
                 cc=cc, ch=ch, p95=lay["lid_p95"], wcov=lay["lid_wcov5"],
                 u13=lay["lid_u1_3"], wu=wu, v_p95=vf["lid_p95"],
                 v_wcov=vf["lid_wcov5"], v_u13=vf["lid_u1_3"])
        # C2 (>= MIN_WINDOWS sweep windows) and C4 (enough regenerating and
        # mature cells) need W1's 20 km extent; W2/W3 run C3, C5 (and C6).
        if W == "W1":
            ok &= run_checks(w)
            continue
        if W == "W4":       # C2 on a rockyweb (native-CRS) source
            for f, layer, vv in (("lid_wcov5", w["wcov"], w["v_wcov"]),
                                 ("lid_p95", w["p95"], w["v_p95"])):
                ok &= gate(f"C2 {f}", check_registration(layer, vv, road),
                           check_registration(shift_one(layer, 0),
                                              shift_one(vv, False), road))
        v = vf["lid_p95"]
        for u in gated_units(forest, wu)[0]:
            m = wu == u
            ok &= gate(f"C3 wu{u}", check_height(w["p95"], ch, forest & m, v),
                       check_height(as_feet(w["p95"]), ch, forest & m, v))
        ok &= gate("C5 coverage", check_coverage(v, forest, wu),
                   check_coverage(drop_unit(v, wu, forest), forest, wu))
        if W == "W3":
            lp = os.path.join(directory, "W3_hag_loo.json")
            if not os.path.exists(lp):
                print(f"   C9 steep ground: missing {lp} - FAIL")
                ok = False
            else:
                import json
                with open(lp) as fh:
                    loo = json.load(fh)
                ok &= gate("C9 steep ground", check_loo(loo, "rmse_idw"),
                           check_loo(loo, "rmse_nn1"))
        if W == "W2":
            try:
                blocks = _read_set(directory, "W2")
                whole = _read_set(directory, "W2seam")
                pad0 = _read_set(directory, "W2pad0")
            except FileNotFoundError as e:
                print(f"   C6 seam: missing {e.filename} - FAIL")
                ok = False
            else:
                ok &= gate("C6 seam", check_seam(blocks, whole),
                           check_seam(pad0, whole))
    print(f"\nPilot gate: {'PASS' if ok else 'FAIL'}")
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--pilot", metavar="DIR")
    ap.add_argument("--region", default="NH")
    args = ap.parse_args()
    if args.self_test:
        sys.exit(0 if self_test() else 1)
    if args.pilot:
        sys.exit(0 if pilot(args.pilot, args.region) else 1)
    ap.print_help()
    sys.exit(2)


if __name__ == "__main__":
    main()
