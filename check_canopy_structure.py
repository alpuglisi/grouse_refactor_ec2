"""check_canopy_structure.py - CR-0032 acceptance gate for the mch_* layers.

Recomputes a seeded sample of generated 30 m cells independently in Earth
Engine - reduceRegions over each cell's exact polygon (template CRS) at
the source's native scale, no reduceResolution - and compares them with
the stored values. Also checks that the height shares are fractions, not
0/1000 samples (the signature of an aggregation that never happened).

Read-only: reads the generated files (or a dry-run pilot file), writes
nothing. This script owns the pass/fail constants; CR-0032 cites it.

Usage (repository root):
    python check_canopy_structure.py --pilot /tmp/mch_pilot_NH.tif
    python check_canopy_structure.py --regions ME NH VT
"""
import argparse
import os
import sys

import numpy as np

# Same source as generate_canopy_structure.MCH_ASSET (T2 ties the two);
# defined here so the check does not run the generator's code.
MCH_ASSET = "projects/sat-io/open-datasets/facebook/meta-canopy-height"
FEATURES = ("mch_mean", "mch_f01", "mch_f15", "mch_f512")
NODATA = -9999
SEED = 0
N_CELLS = 200            # valid cells recomputed per region (or pilot)
# Agreement of a stored value with the independent recomputation. The two
# reducers weight edge pixels differently (area-weighted reduceResolution
# vs pixel-centre reduceRegions), so small differences are expected; a
# m-vs-dm or %-vs-permille error, a shifted grid or a sampled (not
# aggregated) cell differs by far more.
TOL_MEAN_DM = 10         # 1 m
TOL_SHARE_PM = 60        # 6 percentage points
MIN_AGREE_FRAC = 0.9     # per feature, of the sampled cells
# Of the valid cells, the fraction with at least one share strictly inside
# (0, 1000). A cell value that is one sampled 1 m pixel has every share
# at exactly 0 or 1000, so this fraction is 0.
MIN_INTERIOR_SHARE_FRAC = 0.1
MIN_VALID_FRAC = 0.5     # models.MCH_MIN_VALID_FRAC (stated in CR-0032)


def compare(gen, ref):
    """gen: {feature: int array} stored values at the sampled cells
    (NODATA allowed). ref: {feature: float array} the recomputation in
    stored units, NaN where the source does not cover the cell.
    Returns (ok, lines)."""
    lines, ok = [], True
    tol = {"mch_mean": TOL_MEAN_DM}
    for f in FEATURES:
        g = np.asarray(gen[f], dtype=np.float64)
        r = np.asarray(ref[f], dtype=np.float64)
        g_valid, r_valid = g != NODATA, np.isfinite(r)
        both = g_valid & r_valid
        agree = np.zeros(len(g), bool)
        agree[both] = np.abs(g[both] - r[both]) <= tol.get(f, TOL_SHARE_PM)
        agree[~g_valid & ~r_valid] = True
        frac = float(agree.mean()) if len(g) else 0.0
        bad_nodata = int((g_valid & ~r_valid).sum())
        missing = int((~g_valid & r_valid).sum())
        good = frac >= MIN_AGREE_FRAC
        ok &= good
        diff = np.abs(g[both] - r[both])
        lines.append(f"  {f:9s} agree {frac:6.1%} (need {MIN_AGREE_FRAC:.0%}); "
                     f"median |diff| {np.median(diff) if diff.size else float('nan'):.1f}; "
                     f"value where source has none {bad_nodata}; "
                     f"nodata where source has data {missing}"
                     f"{'' if good else '  FAIL'}")
    shares = np.stack([np.asarray(gen[f]) for f in FEATURES[1:]])
    valid = (shares != NODATA).all(axis=0)
    interior = ((shares > 0) & (shares < 1000)).any(axis=0)
    ifrac = float(interior[valid].mean()) if valid.any() else 0.0
    good = ifrac >= MIN_INTERIOR_SHARE_FRAC
    ok &= good
    lines.append(f"  interior shares {ifrac:6.1%} of valid cells (need "
                 f"{MIN_INTERIOR_SHARE_FRAC:.0%}){'' if good else '  FAIL'}")
    return ok, lines


def sample_cells(paths, n, seed=SEED, tries=50):
    """Up to n random cells valid in every band. paths: four single-band
    files in FEATURES order, or one 4-band file. Returns (rows, cols,
    {feature: values}, transform, crs_wkt)."""
    import rasterio
    from rasterio.windows import Window
    srcs = [rasterio.open(p) for p in paths]
    try:
        bands = ([(srcs[0], b) for b in range(1, 5)] if len(srcs) == 1
                 else [(s, 1) for s in srcs])
        ref = srcs[0]
        rng = np.random.default_rng(seed)
        rows, cols, vals = [], [], {f: [] for f in FEATURES}
        for _ in range(n * tries):
            if len(rows) == n:
                break
            r, c = int(rng.integers(ref.height)), int(rng.integers(ref.width))
            v = [int(s.read(b, window=Window(c, r, 1, 1))[0, 0])
                 for s, b in bands]
            if NODATA in v:
                continue
            rows.append(r)
            cols.append(c)
            for f, x in zip(FEATURES, v):
                vals[f].append(x)
        return (np.array(rows), np.array(cols),
                {f: np.array(v) for f, v in vals.items()},
                ref.transform, ref.crs.to_wkt())
    finally:
        for s in srcs:
            s.close()


def recompute(ee, rows, cols, transform, crs_wkt):
    """Independent EE recomputation in stored units (NaN where < half the
    cell's 1 m pixels are valid)."""
    proj = ee.Projection(crs_wkt)
    feats = []
    for i, (r, c) in enumerate(zip(rows, cols)):
        x0, y0 = transform * (int(c), int(r))
        x1, y1 = transform * (int(c) + 1, int(r) + 1)
        g = ee.Geometry.Rectangle([min(x0, x1), min(y0, y1),
                                   max(x0, x1), max(y0, y1)], proj, False)
        feats.append(ee.Feature(g, {"i": i}))
    coll = ee.ImageCollection(MCH_ASSET)
    first = coll.first()
    native = first.projection()
    h = coll.mosaic().setDefaultProjection(native)
    img = ee.Image.cat([
        h.rename("h"), h.lt(1).rename("f01"),
        h.gte(1).And(h.lt(5)).rename("f15"),
        h.gte(5).And(h.lt(12)).rename("f512"),
        ee.Image(1).updateMask(h.mask()).unmask(0)
          .setDefaultProjection(native).rename("valid")])
    out = img.reduceRegions(collection=ee.FeatureCollection(feats),
                            reducer=ee.Reducer.mean(), crs=native,
                            scale=native.nominalScale()).getInfo()
    n = len(rows)
    ref = {f: np.full(n, np.nan) for f in FEATURES}
    for ft in out["features"]:
        p = ft["properties"]
        i = int(p["i"])
        if p.get("valid") is None or p["valid"] < MIN_VALID_FRAC \
                or p.get("h") is None:
            continue
        ref["mch_mean"][i] = p["h"] * 10.0
        for f, b in (("mch_f01", "f01"), ("mch_f15", "f15"),
                     ("mch_f512", "f512")):
            ref[f][i] = p[b] * 1000.0
    return ref


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--pilot", help="4-band pilot file from "
                    "generate_canopy_structure.py --dry-run")
    ap.add_argument("--regions", nargs="+", default=None)
    ap.add_argument("--project", default=os.environ.get("EARTHENGINE_PROJECT"))
    ap.add_argument("--n", type=int, default=N_CELLS)
    args = ap.parse_args()
    from download_tcc_nlcd import ee_init
    ee = ee_init(args.project)
    targets = []
    if args.pilot:
        targets.append(("pilot", [args.pilot]))
    if args.regions:
        from grouse_data import GrouseData
        data = GrouseData()
        for R in args.regions:
            rd = data[R]
            targets.append((R, [rd.latest_raster_path(f) for f in FEATURES]))
    if not targets:
        raise SystemExit("Give --pilot and/or --regions.")
    all_ok = True
    for name, paths in targets:
        rows, cols, gen, tr, wkt = sample_cells(paths, args.n)
        if len(rows) == 0:
            print(f"{name}: no valid cell found  FAIL")
            all_ok = False
            continue
        ref = recompute(ee, rows, cols, tr, wkt)
        ok, lines = compare(gen, ref)
        print(f"{name}: {len(rows)} cells  {'PASS' if ok else 'FAIL'}")
        print("\n".join(lines))
        all_ok &= ok
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
