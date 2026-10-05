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
                N seeded pixels; the source is sampled at FOUR probes, the
                pixel centre moved RAW_PROBE_M along each diagonal - all
                inside the same source pixel for a native-lattice copy; a
                half-pixel-offset download (a tie broken in any direction)
                fails at least one. A pixel matches only if all four do.
  TreeMap derived (balive, tpa_live, qmd, carbon_dwn; template grid): local,
                no Earth Engine: each cell must equal the layer rebuilt
                exactly as generate_treemap_features builds it (its own raw
                attributes sampled at the cell centre, _clean, the models
                encoders) from the vintage that year maps to. Cells the
                file holds as nodata (outside NLCD coverage) are skipped.
Diagnostics (not gates): per template/raw file, the share of mismatches
within EDGE_M of a source pixel edge (datum or approximate-warp jitter
sits there; misregistration does not), and the equality against the
source sampled at the BUG-0094 offset (+15 m east, -15 m north) - high
for a file with the BUG-0094 shift, low for a repaired one.
Gate: every file's share of equal cells >= MIN_EQUAL; exit 1 otherwise.

The reference is computed independently of the file (Earth Engine point
sampling, or the raw file), never read from it (PA-0021(e)). Read-only.

Usage (repository root, on the EC2 host; --data-root is the directory
that CONTAINS data/):
    python check_layer_registration.py
    python check_layer_registration.py --data-root ~/grouse2_before --collection-nlcd <id> --collection-tcc <id>
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
EDGE_M = 4.0
BUG_OFFSET = (15.0, -15.0)      # BUG-0094: values came from the SE pixel
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


def edge_distance(xs, ys, grid):
    """Distance (m) of points (in grid["crs"]) to the nearest pixel edge
    of the 30 m lattice with origin grid x0/y0."""
    fx = np.mod(np.asarray(xs) - grid["x0"], 30.0)
    fy = np.mod(grid["y0"] - np.asarray(ys), 30.0)
    return np.minimum(np.minimum(fx, 30.0 - fx), np.minimum(fy, 30.0 - fy))


def _diagnostics(got, ref, valid, xs, ys, crs, sample_fn, grid):
    """Near-edge share of mismatches; equality at the BUG-0094 offset."""
    out = {"near_edge": np.nan, "equal_at_bug_offset": np.nan}
    if grid is None:
        return out
    from pyproj import Transformer
    gx, gy = Transformer.from_crs(crs, grid["crs"], always_xy=True).transform(xs, ys)
    gx, gy = np.asarray(gx), np.asarray(gy)
    miss = valid & (got != ref)
    if miss.any():
        out["near_edge"] = float((edge_distance(gx[miss], gy[miss], grid)
                                  <= EDGE_M).mean())
    from rasterio.crs import CRS
    ref_b = np.asarray(sample_fn(gx + BUG_OFFSET[0], gy + BUG_OFFSET[1],
                                 CRS.from_user_input(grid["crs"])),
                       dtype=np.float64)
    vb = valid & np.isfinite(ref_b)
    out["equal_at_bug_offset"] = (float((got[vb] == ref_b[vb]).mean())
                                  if vb.any() else np.nan)
    return out


def check_template_file(path, sample_fn, valid_range=None, n=N_CELLS,
                        grid=None):
    """nlcd/tcc on the template grid. sample_fn(xs, ys, crs) -> source
    values at those points (native scale). Returns {"equal", "n",
    "near_edge", "equal_at_bug_offset"}."""
    with rasterio.open(path) as src:
        a = src.read(1)
        rows, cols = seeded_cells(a, n)
        xs, ys = centres(src.transform, rows, cols)
        crs = src.crs
    ref = np.asarray(sample_fn(xs, ys, crs), dtype=np.float64)
    if valid_range is not None:
        lo, hi = valid_range
        valid = (ref >= lo) & (ref <= hi)
    else:
        valid = np.isfinite(ref) & (ref != NODATA)
    got = a[rows, cols].astype(np.float64)
    out = {"equal": equal_share(got, ref, valid), "n": int(valid.sum())}
    out.update(_diagnostics(got, ref, valid, xs, ys, crs, sample_fn, grid))
    return out


def check_raw_file(path, sample_fn, n=N_CELLS, grid=None):
    """Raw TreeMap file: each sampled pixel must equal the source at all
    four diagonal probes RAW_PROBE_M from its centre."""
    with rasterio.open(path) as src:
        a = src.read(1)
        rows, cols = seeded_cells(a, n, nodata=-1e30)
        crs = src.crs
        cx, cy = centres(src.transform, rows, cols)
    got = a[rows, cols].astype(np.float64)
    match = np.ones(len(rows), bool)
    valid = np.ones(len(rows), bool)
    for sx, sy in ((-1, 1), (1, 1), (-1, -1), (1, -1)):
        ref = np.asarray(sample_fn(cx + sx * RAW_PROBE_M, cy + sy * RAW_PROBE_M,
                                   crs), dtype=np.float64)
        valid &= np.isfinite(ref)
        match &= np.where(np.isfinite(ref), got == ref, False)
    out = {"equal": float(match[valid].mean()) if valid.any() else 0.0,
           "n": int(valid.sum())}
    ref_c = np.asarray(sample_fn(cx, cy, crs), dtype=np.float64)
    out.update(_diagnostics(got, ref_c, valid & np.isfinite(ref_c), cx, cy,
                            crs, sample_fn, grid))
    return out


def sample_raster(path, xs, ys, crs):
    """Values of a local raster at points (pixel containing each point);
    NaN outside."""
    from pyproj import Transformer
    with rasterio.open(path) as r:
        tx, ty = Transformer.from_crs(crs, r.crs, always_xy=True).transform(xs, ys)
        rr, cc = rasterio.transform.rowcol(r.transform, tx, ty)
        rr, cc = np.atleast_1d(rr), np.atleast_1d(cc)
        out = np.full(len(rr), np.nan)
        ok = (rr >= 0) & (rr < r.height) & (cc >= 0) & (cc < r.width)
        for i in np.nonzero(ok)[0]:
            out[i] = r.read(1, window=Window(int(cc[i]), int(rr[i]), 1, 1))[0, 0]
    return out


def rebuild_derived(feat, raw):
    """The derived layer exactly as generate_treemap_features writes it,
    from raw attribute values (dict attr -> float array). NODATA where a
    needed attribute is bad."""
    from generate_treemap_features import _clean
    from models import qmd_from_balive_tpa, tpa_live_encode, treemap_encode
    vals, bad = {}, {}
    for a, v in raw.items():
        vals[a], bad[a] = _clean(v)
    if feat == "balive":
        enc, inv = treemap_encode("balive", vals["BALIVE"]), bad["BALIVE"]
    elif feat == "tpa_live":
        enc, inv = tpa_live_encode(vals["TPA_LIVE"]), bad["TPA_LIVE"]
    elif feat == "qmd":
        enc = treemap_encode("qmd", qmd_from_balive_tpa(vals["BALIVE"],
                                                        vals["TPA_LIVE"]))
        inv = bad["BALIVE"] | bad["TPA_LIVE"]
    elif feat == "carbon_dwn":
        enc, inv = treemap_encode("carbon_dwn", vals["CARBON_DWN"]), bad["CARBON_DWN"]
    else:
        raise ValueError(feat)
    enc = np.asarray(enc).astype(np.int64)
    enc[inv] = NODATA
    return enc


NEEDS = {"balive": ("BALIVE",), "tpa_live": ("TPA_LIVE",),
         "qmd": ("BALIVE", "TPA_LIVE"), "carbon_dwn": ("CARBON_DWN",)}


def check_derived_file(path, feat, raw_paths, n=N_CELLS):
    """Derived TreeMap layer vs the same layer rebuilt from its raw
    attribute files (raw_paths: attr -> path) at the cell centres. Cells
    the file holds as NODATA (outside NLCD coverage) are skipped."""
    with rasterio.open(path) as src:
        a = src.read(1)
        rows, cols = seeded_cells(a, n)
        xs, ys = centres(src.transform, rows, cols)
        crs = src.crs
    raw = {at: sample_raster(raw_paths[at], xs, ys, crs) for at in NEEDS[feat]}
    inside = np.all([np.isfinite(v) for v in raw.values()], axis=0)
    exp = np.full(len(rows), NODATA, np.int64)
    if inside.any():
        exp[inside] = rebuild_derived(feat, {k: v[inside] for k, v in raw.items()})
    got = a[rows, cols].astype(np.int64)
    return {"equal": float((got[inside] == exp[inside]).mean()) if inside.any() else 0.0,
            "n": int(inside.sum())}


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

    def record(what, res):
        share, n = res["equal"], res["n"]
        ok = share >= MIN_EQUAL and n > 0
        rows.append((what, share, n, ok))
        extra = ""
        if np.isfinite(res.get("near_edge", np.nan)):
            extra += f"  mismatches near edge {res['near_edge']:.0%}"
        if np.isfinite(res.get("equal_at_bug_offset", np.nan)):
            extra += f"  at BUG-0094 offset {res['equal_at_bug_offset']:.0%}"
        print(f"   {what:48s} equal {share:7.2%} of {n:4d}  "
              f"{'PASS' if ok else 'FAIL'}{extra}", flush=True)

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
                record(f"{R} {feat} {year} ({os.path.basename(path)})",
                       check_template_file(path, fn, spec["valid_range"],
                                           args.n, grid=g))

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
            record(f"{R} raw TreeMap {vintage} {attr}",
                   check_raw_file(path, fn, args.n, grid=g))
        vintages = sorted({int(m.group(1)) for m in (
            re.match(r"TreeMap(\d{4})_", os.path.basename(p))
            for p in glob.glob(os.path.join(raw_dir, "TreeMap*.tif"))) if m})
        for R in regions:
            rd = data[R]
            for feat in DERIVED:
                for year in rd.raster_years(feat):
                    v = gtf.nearest_vintage(year, vintages)
                    raws = {at: gtf.find_source(raw_dir, v, at, R)
                            for at in NEEDS[feat]}
                    if any(p is None for p in raws.values()):
                        record(f"{R} {feat} {year}: raw {v} missing",
                               {"equal": 0.0, "n": 0})
                        continue
                    record(f"{R} {feat} {year} vs raw TreeMap {v}",
                           check_derived_file(rd.raster_path(feat, year),
                                              feat, raws, args.n))

    bad = [r for r in rows if not r[3]]
    print(f"\nGate (every file >= {MIN_EQUAL:.0%} equal): "
          f"{'PASS' if not bad else 'FAIL'} - {len(rows) - len(bad)} of "
          f"{len(rows)} files pass")
    sys.exit(1 if bad or not rows else 0)


if __name__ == "__main__":
    main()
