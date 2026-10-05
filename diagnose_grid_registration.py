"""diagnose_grid_registration.py - which copy of the grid is off by a cell?

CR-0032's pilot grid check found NLCD fetched by generate_canopy_structure
(one step onto the template grid) best matches the on-disk NLCD one row
off. Both sides depend on Earth Engine, so the check alone cannot say
which is misplaced. This script compares every copy against a reference
built WITHOUT Earth Engine: road_dist, rasterised locally from TIGER road
vectors onto the template grid.

Over one window of the region's template grid (default: the window with
the most training positives) it builds:
  A  NLCD via generate_canopy_structure.fetch_window (template grid)
  B  NLCD via download_tcc_nlcd's route (fetch_tile on the EPSG:5070
     lattice, mask_to_valid, realign_rasters.warp_to_grid) - how the
     on-disk file was made
  D  the on-disk NLCD file
  M  mch_f01 (share of canopy < 1 m) via the generator's own route
and, for each, the offset (dy, dx) at which it best lines up with the
road cells (road_dist < ROAD_M): NLCD developed classes (21-24) for A, B,
D; open ground (mch_f01) for M. A copy registered with the template peaks
at (0, 0). Also prints the A-vs-D, B-vs-D and A-vs-B equality tables.

Read-only: temporary files only, nothing under data/.

Usage (repository root, on the EC2 host):
    python diagnose_grid_registration.py --region NH
"""
import argparse
import os
import sys
import tempfile

import numpy as np
import rasterio
from rasterio.windows import Window

import download_tcc_nlcd as dtn
import generate_canopy_structure as gcs
from grouse_data import GrouseData
from models import road_dist_decode

K = 2                 # offsets -K..K cells in each direction
ROAD_M = 15.0         # a cell centre within 15 m of a road centreline
DEVELOPED = (21, 22, 23, 24)


def table(score):
    """score(dy, dx) -> float, over -K..K. Returns {offset: value}."""
    return {(dy, dx): score(dy, dx)
            for dy in range(-K, K + 1) for dx in range(-K, K + 1)}


def show(name, t, higher_is_better=True):
    best = (max if higher_is_better else min)(t, key=t.get)
    print(f"\n{name}: best offset {best} = {t[best]:.4f}; (0, 0) = "
          f"{t[(0, 0)]:.4f}")
    for dy in range(-K, K + 1):
        print("   dy=%+d  " % dy + "  ".join(
            f"{t[(dy, dx)]:.3f}{'*' if (dy, dx) == best else ' '}"
            for dx in range(-K, K + 1)))
    return best


def padded(win):
    return Window(win.col_off - K, win.row_off - K,
                  win.width + 2 * K, win.height + 2 * K)


def shifted(ref_pad, dy, dx, h, w):
    return ref_pad[K + dy:K + dy + h, K + dx:K + dx + w]


def route_b(ee, image, tpl, win, lo, hi, td):
    """download_tcc_nlcd's route for one window: 5070 lattice tiles,
    merge, mask_to_valid, warp_to_grid onto the window's template grid."""
    from rasterio.merge import merge as rio_merge
    from rasterio.warp import transform_bounds
    from realign_rasters import warp_to_grid
    left, bottom, right, top = rasterio.windows.bounds(win, tpl.transform)
    lonlat = transform_bounds(tpl.crs, "EPSG:4326", left, bottom, right,
                              top, densify_pts=21)
    x0, y0, x1, y1 = dtn.region_grid(lonlat, pad_m=300)
    paths = []
    for i, rect in enumerate(dtn.tiles(x0, y0, x1, y1, 6000)):
        p = os.path.join(td, f"b{i}.tif")
        dtn.fetch_tile(ee, image, rect, p)
        paths.append(p)
    srcs = [rasterio.open(p) for p in paths]
    try:
        mosaic, transform = rio_merge(srcs)
    finally:
        for s in srcs:
            s.close()
    out = dtn.mask_to_valid(mosaic[0], lo, hi)
    merged = os.path.join(td, "merged_5070.tif")
    with rasterio.open(merged, "w", driver="GTiff", height=out.shape[0],
                       width=out.shape[1], count=1, dtype="int16",
                       crs="EPSG:5070", transform=transform,
                       nodata=dtn.NODATA) as dst:
        dst.write(out, 1)
    ref = os.path.join(td, "ref.tif")
    with rasterio.open(ref, "w", driver="GTiff", height=win.height,
                       width=win.width, count=1, dtype="int16",
                       crs=tpl.crs, transform=tpl.window_transform(win),
                       nodata=dtn.NODATA) as dst:
        dst.write(np.zeros((win.height, win.width), np.int16), 1)
    staged = os.path.join(td, "b_on_template.tif")
    warp_to_grid(merged, ref, staged)
    with rasterio.open(staged) as s:
        return s.read(1)


def fetch_a(ee, image, tpl, win, td, name, lo=None, hi=None, sub=None):
    """Generator route, in sub x sub windows (Earth Engine's reprojection
    limit for the 1 m source); returns the first band."""
    sub = sub or win.width
    out = None
    for r in range(0, win.height, sub):
        for c in range(0, win.width, sub):
            w = Window(win.col_off + c, win.row_off + r,
                       min(sub, win.width - c), min(sub, win.height - r))
            p = os.path.join(td, f"{name}_{r}_{c}.tif")
            gcs.fetch_window(ee, image, tpl.crs.to_wkt(),
                             tpl.window_transform(w), w.width, w.height, p)
            with rasterio.open(p) as s:
                a = s.read()
            if out is None:
                out = np.full((a.shape[0], win.height, win.width),
                              dtn.NODATA, a.dtype)
            out[:, r:r + w.height, c:c + w.width] = a
    band = out[0]
    if lo is not None:
        band = dtn.mask_to_valid(band, lo, hi)
    return band, out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--region", default="NH")
    ap.add_argument("--project", default=os.environ.get("EARTHENGINE_PROJECT"))
    ap.add_argument("--window-px", type=int, default=128)
    ap.add_argument("--pilot-lonlat", type=float, nargs=2, default=None)
    args = ap.parse_args()

    ee = dtn.ee_init(args.project)
    rd = GrouseData()[args.region]
    template = dtn.template_raster(rd)
    with rasterio.open(template) as tpl:
        wins = list(gcs.windows(tpl.width, tpl.height, args.window_px))
        win = gcs._pilot_window(rd, tpl, wins, args.pilot_lonlat)
        print(f"{args.region}: template {os.path.basename(template)}, "
              f"window rows {win.row_off}-{win.row_off + win.height}, cols "
              f"{win.col_off}-{win.col_off + win.width}")
        h, w = win.height, win.width
        with rasterio.open(rd.latest_raster_path("road_dist")) as src:
            road_pad = road_dist_decode(src.read(
                1, window=padded(win), boundless=True,
                fill_value=dtn.NODATA)) <= ROAD_M
            road_pad &= src.read(1, window=padded(win), boundless=True,
                                 fill_value=dtn.NODATA) != dtn.NODATA
        year = max(rd.raster_years("nlcd"))
        with rasterio.open(rd.raster_path("nlcd", year)) as src:
            disk_pad = src.read(1, window=padded(win), boundless=True,
                                fill_value=dtn.NODATA)
        disk = shifted(disk_pad, 0, 0, h, w)
        print(f"   road cells (<= {ROAD_M:g} m): "
              f"{int(shifted(road_pad, 0, 0, h, w).sum()):,} of {h * w:,}; "
              f"nlcd year {year}")
        if shifted(road_pad, 0, 0, h, w).sum() < 50:
            sys.exit("Too few road cells in this window to register "
                     "against; pass --pilot-lonlat near a road.")

        spec = dtn.PRODUCTS["nlcd"]
        lo, hi = spec["valid_range"]
        cid = dtn.resolve_collection(ee, spec["collections"])
        nlcd_img, _ = dtn.year_image(ee, cid, spec["bands"], year)
        bounds = gcs.template_bounds_lonlat(template)
        mch_img, _ = gcs.mch_image(ee, bounds)
        with tempfile.TemporaryDirectory() as td:
            a, _ = fetch_a(ee, nlcd_img, tpl, win, td, "a", lo, hi)
            b = route_b(ee, nlcd_img, tpl, win, lo, hi, td)
            _, m = fetch_a(ee, mch_img, tpl, win, td, "m", sub=64)
    f01 = np.where((m[4] >= 0.5) & (m[1] >= 0), m[1], np.nan)

    def dev_on_roads(x):
        def s(dy, dx):
            r = shifted(road_pad, dy, dx, h, w)
            v = (x != dtn.NODATA) & r
            return float(np.isin(x[v], DEVELOPED).mean()) if v.any() else 0.0
        return s

    def mean_on_roads(x):
        def s(dy, dx):
            r = shifted(road_pad, dy, dx, h, w) & np.isfinite(x)
            return float(np.nanmean(x[r])) if r.any() else 0.0
        return s

    print("\n== Against TIGER roads (no Earth Engine in the reference); a "
          "registered copy peaks at (0, 0) ==")
    results = {
        "A  NLCD, generator route (developed share on road cells)":
            show("A  NLCD, generator route", table(dev_on_roads(a))),
        "B  NLCD, download_tcc_nlcd route":
            show("B  NLCD, download_tcc_nlcd route", table(dev_on_roads(b))),
        "D  NLCD on disk":
            show("D  NLCD on disk", table(dev_on_roads(disk))),
        "M  mch_f01 (open-ground share on road cells)":
            show("M  mch_f01, generator route", table(mean_on_roads(f01))),
    }

    def equal(x, ypad):
        def s(dy, dx):
            y = shifted(ypad, dy, dx, h, w)
            v = (x != dtn.NODATA) & (y != dtn.NODATA)
            return float((x[v] == y[v]).mean()) if v.any() else 0.0
        return s

    b_pad = np.pad(b, K, constant_values=dtn.NODATA)
    print("\n== Copies against each other (equality share) ==")
    show("A vs D (the pilot's grid check)", table(equal(a, disk_pad)))
    show("B vs D (should be (0, 0) near 1.0 if the disk file is today's "
         "route)", table(equal(b, disk_pad)))
    show("A vs B", table(equal(a, b_pad)))

    print("\nSummary (best offset against roads):")
    for k, v in results.items():
        print(f"   {v}  {k}")


if __name__ == "__main__":
    main()
