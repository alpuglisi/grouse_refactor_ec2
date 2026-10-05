"""check_layer_registration.py - CR-0035 gate: is every Earth Engine layer
file registered with its source? (BUG-0094)

Per file, for EVERY year on disk (not only the latest):
  nlcd, tcc     (data/landfire, template grid): N seeded valid cells; the
                source is sampled by Earth Engine at each cell CENTRE at
                its native scale (a point lies in exactly one source pixel:
                no resampling, no tie). Nearest-neighbour onto the template
                takes exactly that pixel, so a registered file equals the
                reference in (nearly) every cell.
  TreeMap raw   (data/treemap_raw, the source's own lattice after CR-0034):
                N seeded pixels; the reference point is the pixel centre
                moved RAW_PROBE_M north-west - inside the same source pixel
                for a native-lattice copy, but in the opposite neighbour to
                BUG-0094's south-east tie for a 0-origin download.
  TreeMap derived (balive, tpa_live, qmd, carbon_dwn; template grid): local,
                no Earth Engine: the forest mask (value > 0) of each cell
                must equal the raw BALIVE file sampled at the cell centre
                (the vintage generate_treemap_features maps that year to).
Gate: every file's share of equal cells >= MIN_EQUAL; exit 1 otherwise.

The reference is computed independently of the file (Earth Engine point
sampling, or the raw file), never read from it (PA-0021(e)). Read-only.

Usage (repository root, on the EC2 host):
    python check_layer_registration.py
    python check_layer_registration.py --data-root ~/grouse2/data_before_bug0094_root --collection-nlcd <id>
"""
import argparse
import glob
import os
import re
import sys

import numpy as np
import rasterio
from rasterio.windows import Window

NODATA = -9999
N_CELLS = 400
SEED = 0
MIN_EQUAL = 0.99
RAW_PROBE_M = 7.0
EE_FEATURES = ("nlcd", "tcc")
DERIVED = ("balive", "tpa_live", "qmd", "carbon_dwn")


def seeded_cells(arr, n, seed=SEED, nodata=NODATA):
    """Up to n (row, col) of valid cells, seeded."""
    rows, cols = np.nonzero(arr != nodata)
    if rows.size == 0:
        return rows, cols
    rng = np.random.default_rng(seed)
    pick = rng.choice(rows.size, size=min(n, rows.size), replace=False)
    return rows[pick], cols[pick]


def centres(transform, rows, cols, dx=0.0, dy=0.0):
    xs = transform.c + (cols + 0.5) * transform.a + dx
    ys = transform.f + (rows + 0.5) * transform.e + dy
    return xs, ys


def equal_share(got, ref, valid_ref):
    """Share of cells (reference valid) whose value equals the reference."""
    v = valid_ref & np.isfinite(ref)
    if not v.any():
        return 0.0
    return float((got[v] == ref[v]).mean())


def check_template_file(path, sample_fn, valid_range=None, n=N_CELLS):
    """nlcd/tcc on the template grid. sample_fn(xs, ys, crs) -> source
    values at those points (native scale)."""
    with rasterio.open(path) as src:
        a = src.read(1)
        rows, cols = seeded_cells(a, n)
        xs, ys = centres(src.transform, rows, cols)
        ref = np.asarray(sample_fn(xs, ys, src.crs), dtype=np.float64)
    if valid_range is not None:
        lo, hi = valid_range
        valid = (ref >= lo) & (ref <= hi)
    else:
        valid = ref != NODATA
    return equal_share(a[rows, cols].astype(np.float64), ref, valid), int(valid.sum())


def check_raw_file(path, sample_fn, n=N_CELLS):
    """Raw TreeMap file: value at each pixel vs the source at a point
    RAW_PROBE_M north-west of the pixel centre."""
    with rasterio.open(path) as src:
        a = src.read(1)
        rows, cols = seeded_cells(a, n, nodata=-1e30)
        xs, ys = centres(src.transform, rows, cols, -RAW_PROBE_M, RAW_PROBE_M)
        ref = np.asarray(sample_fn(xs, ys, src.crs), dtype=np.float64)
    valid = np.isfinite(ref)
    return equal_share(a[rows, cols].astype(np.float64), ref, valid), int(valid.sum())


def check_derived_file(path, raw_balive_path, n=N_CELLS):
    """Derived TreeMap layer vs its raw BALIVE: forest mask equality at
    the template cell centres (local, no Earth Engine)."""
    from pyproj import Transformer
    with rasterio.open(path) as src:
        a = src.read(1)
        rows, cols = seeded_cells(a, n)
        xs, ys = centres(src.transform, rows, cols)
        crs = src.crs
    with rasterio.open(raw_balive_path) as raw:
        tx, ty = Transformer.from_crs(crs, raw.crs, always_xy=True).transform(xs, ys)
        rr, cc = rasterio.transform.rowcol(raw.transform, tx, ty)
        rr, cc = np.asarray(rr), np.asarray(cc)
        ok = (rr >= 0) & (rr < raw.height) & (cc >= 0) & (cc < raw.width)
        ref = np.full(rr.shape, np.nan)
        for i in np.nonzero(ok)[0]:
            ref[i] = raw.read(1, window=Window(int(cc[i]), int(rr[i]), 1, 1))[0, 0]
    got = (a[rows, cols] > 0).astype(np.float64)
    refm = np.where(np.isfinite(ref), (ref > 0).astype(np.float64), np.nan)
    return equal_share(got, refm, np.isfinite(refm)), int(np.isfinite(refm).sum())


def ee_sampler(ee, image, scale_crs, scale_transform):
    """sample_fn backed by Earth Engine: reduceRegions(first) on points at
    the source's native grid."""
    def sample(xs, ys, crs):
        proj = ee.Projection(crs.to_wkt())
        feats = [ee.Feature(ee.Geometry.Point([float(x), float(y)], proj),
                            {"i": i}) for i, (x, y) in enumerate(zip(xs, ys))]
        out = image.rename("v").reduceRegions(
            collection=ee.FeatureCollection(feats),
            reducer=ee.Reducer.first(), crs=scale_crs,
            crsTransform=scale_transform).getInfo()
        ref = np.full(len(xs), np.nan)
        for f in out["features"]:
            v = f["properties"].get("first", f["properties"].get("v"))
            if v is not None:
                ref[int(f["properties"]["i"])] = v
        return ref
    return sample


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--data-root", default=".",
                    help="repository data root (default: here); point it at "
                         "the pre-repair snapshot to show the gate fails")
    ap.add_argument("--regions", nargs="+", default=None)
    ap.add_argument("--project", default=os.environ.get("EARTHENGINE_PROJECT"))
    ap.add_argument("--n", type=int, default=N_CELLS)
    ap.add_argument("--collection-nlcd", default=None)
    ap.add_argument("--collection-tcc", default=None)
    ap.add_argument("--skip-treemap", action="store_true")
    args = ap.parse_args()

    import download_tcc_nlcd as dtn
    import download_treemap as dtm
    import generate_treemap_features as gtf
    from grouse_data import DataConfig, GrouseData
    from regions import REGIONS
    regions = args.regions or list(REGIONS)
    ee = dtn.ee_init(args.project)
    data = GrouseData(DataConfig(base_dir=args.data_root))
    rows = []

    def record(what, share, n):
        ok = share >= MIN_EQUAL and n > 0
        rows.append((what, share, n, ok))
        print(f"   {what:48s} equal {share:7.2%} of {n:4d}  "
              f"{'PASS' if ok else 'FAIL'}", flush=True)

    for feat in EE_FEATURES:
        spec = dtn.PRODUCTS[feat]
        pinned = getattr(args, f"collection_{feat}")
        for R in regions:
            rd = data[R]
            for year in rd.raster_years(feat):
                path = rd.raster_path(feat, year)
                with rasterio.open(path) as s:
                    tag = s.tags().get("GROUSE_SOURCE", "")
                cid = pinned or (tag.split()[0] if tag else
                                 dtn.resolve_collection(ee, spec["collections"]))
                bounds = (-180, -90, 180, 90)
                with rasterio.open(path) as s:
                    from rasterio.warp import transform_bounds
                    bounds = transform_bounds(s.crs, "EPSG:4326", *s.bounds,
                                              densify_pts=21)
                g = dtn.year_native_grid(ee, cid, year, bounds)
                img, _ = dtn.year_image(ee, cid, spec["bands"], year)
                fn = ee_sampler(ee, img, g["crs"],
                                [30, 0, g["x0"], 0, -30, g["y0"]])
                share, n = check_template_file(path, fn, spec["valid_range"],
                                               args.n)
                record(f"{R} {feat} {year} ({os.path.basename(path)})", share, n)

    if not args.skip_treemap:
        raw_dir = os.path.join(args.data_root, dtm.DEFAULT_OUT_DIR)
        for path in sorted(glob.glob(os.path.join(raw_dir, "TreeMap*_*_*.tif"))):
            m = re.match(r"TreeMap(\d{4})_([A-Z]{2})_(\w+)\.tif$",
                         os.path.basename(path))
            if not m or m.group(2) not in regions:
                continue
            vintage, R, attr = int(m.group(1)), m.group(2), m.group(3)
            image, asset_id = dtm.resolve_vintage_image(ee, vintage)
            band = dtm.resolve_band(image.bandNames().getInfo(), attr)
            with rasterio.open(path) as s:
                from rasterio.warp import transform_bounds
                bounds = transform_bounds(s.crs, "EPSG:4326", *s.bounds,
                                          densify_pts=21)
            g = dtm.vintage_native_grid(ee, vintage, bounds)
            fn = ee_sampler(ee, image.select([band]).unmask(0).toFloat(),
                            g["crs"], [30, 0, g["x0"], 0, -30, g["y0"]])
            share, n = check_raw_file(path, fn, args.n)
            record(f"{R} raw TreeMap {vintage} {attr}", share, n)
        vintages = sorted({int(m.group(1)) for m in (
            re.match(r"TreeMap(\d{4})_", os.path.basename(p))
            for p in glob.glob(os.path.join(raw_dir, "TreeMap*.tif"))) if m})
        for R in regions:
            rd = data[R]
            for feat in DERIVED:
                for year in rd.raster_years(feat):
                    v = gtf.nearest_vintage(year, vintages)
                    raw = gtf.find_source(raw_dir, v, "BALIVE", R)
                    if raw is None:
                        record(f"{R} {feat} {year}: no raw BALIVE {v}", 0.0, 0)
                        continue
                    share, n = check_derived_file(rd.raster_path(feat, year),
                                                  raw, args.n)
                    record(f"{R} {feat} {year} vs raw BALIVE {v}", share, n)

    bad = [r for r in rows if not r[3]]
    print(f"\nGate (every file >= {MIN_EQUAL:.0%} equal): "
          f"{'PASS' if not bad else 'FAIL'} - {len(rows) - len(bad)} of "
          f"{len(rows)} files pass")
    sys.exit(1 if bad or not rows else 0)


if __name__ == "__main__":
    main()
