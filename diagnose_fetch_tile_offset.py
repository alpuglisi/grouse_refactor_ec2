"""diagnose_fetch_tile_offset.py - BUG-0094 root cause: where does the
one-row shift of the Earth Engine downloads come from?

diagnose_layer_registration.py found every layer downloaded through
download_tcc_nlcd.fetch_tile / download_treemap.fetch_tile (nlcd, tcc,
the TreeMap four) one row off the template grid, the LANDFIRE clips
aligned. This fetches ee.Image.pixelCoordinates - an image whose pixel
values are the coordinates Earth Engine assigns to that pixel - through:
  T1  download_tcc_nlcd.fetch_tile, one tile (EPSG:5070 lattice)
  T2  the same, two vertically adjacent tiles merged with rio_merge
  T3  download_tcc_nlcd.fetch_tile with "dimensions" instead of "region"
  W   generate_canopy_structure.fetch_window on the template grid
and compares, per pixel, Earth Engine's coordinate with the pixel centre
the GeoTIFF's own transform implies. Any constant difference is the
route's offset; W is the reference convention (it registered at (0, 0)
against TIGER roads).

Read-only; temporary files only. Usage (repository root):
    python diagnose_fetch_tile_offset.py --region NH
"""
import argparse
import os
import tempfile

import numpy as np
import rasterio
from rasterio.merge import merge as rio_merge
from rasterio.windows import Window

import download_tcc_nlcd as dtn
import generate_canopy_structure as gcs
from grouse_data import GrouseData

PIXEL_M = 30


def offsets(arr, transform, label):
    """arr (2, h, w) EE x/y; mean and range of (EE - file centre)."""
    h, w = arr.shape[1:]
    cols, rows = np.meshgrid(np.arange(w) + 0.5, np.arange(h) + 0.5)
    fx = transform.c + cols * transform.a + rows * transform.b
    fy = transform.f + cols * transform.d + rows * transform.e
    dx, dy = arr[0] - fx, arr[1] - fy
    print(f"   {label:44s} shape {h}x{w}  EE-minus-file x {dx.mean():+8.2f} "
          f"[{dx.min():+.1f},{dx.max():+.1f}]  y {dy.mean():+8.2f} "
          f"[{dy.min():+.1f},{dy.max():+.1f}] m")
    return dx.mean(), dy.mean()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--region", default="NH")
    ap.add_argument("--project", default=os.environ.get("EARTHENGINE_PROJECT"))
    args = ap.parse_args()
    ee = dtn.ee_init(args.project)
    rd = GrouseData()[args.region]
    template = dtn.template_raster(rd)
    bounds = gcs.template_bounds_lonlat(template)
    x0, y0, x1, y1 = dtn.region_grid(bounds)
    # two vertically adjacent 6 km tiles near the grid's centre
    cx = x0 + ((x1 - x0) // 2 // 6000) * 6000
    cy = y0 + ((y1 - y0) // 2 // 6000) * 6000
    lower = (cx, cy, cx + 6000, cy + 6000)
    upper = (cx, cy + 6000, cx + 6000, cy + 12000)
    img5070 = ee.Image.pixelCoordinates(ee.Projection("EPSG:5070")).toDouble()
    print(f"{args.region}: tiles {lower} and {upper} (EPSG:5070)")
    with tempfile.TemporaryDirectory() as td:
        res = {}
        p1 = os.path.join(td, "t_lower.tif")
        p2 = os.path.join(td, "t_upper.tif")
        dtn.fetch_tile(ee, img5070, lower, p1)
        dtn.fetch_tile(ee, img5070, upper, p2)
        for p, lab in ((p1, "T1 fetch_tile lower"), (p2, "T1 fetch_tile upper")):
            with rasterio.open(p) as s:
                print(f"   {lab}: requested top {lower[3] if 'lower' in p else upper[3]}"
                      f", file transform {tuple(s.transform)[:6]}, "
                      f"{s.height}x{s.width}")
                res[lab] = offsets(s.read(), s.transform, lab)
        srcs = [rasterio.open(p) for p in (p1, p2)]
        try:
            mosaic, tr = rio_merge(srcs)
        finally:
            for s in srcs:
                s.close()
        res["T2"] = offsets(mosaic, tr, "T2 two tiles merged (rio_merge)")
        # T4: T2's mosaic warped onto the template grid exactly as the
        # downloads were (realign_rasters.warp_to_grid, nearest); each
        # cell's EE 5070 coordinate vs the template cell centre in 5070
        from pyproj import Transformer
        from rasterio.warp import transform_bounds
        from realign_rasters import warp_to_grid
        merged = os.path.join(td, "merged.tif")
        with rasterio.open(merged, "w", driver="GTiff",
                           height=mosaic.shape[1], width=mosaic.shape[2],
                           count=2, dtype="float64", crs="EPSG:5070",
                           transform=tr) as dst:
            dst.write(mosaic)
        with rasterio.open(template) as tpl:
            l, b_, r_, t_ = transform_bounds("EPSG:5070", tpl.crs,
                                             lower[0] + 600, lower[1] + 600,
                                             upper[2] - 600, upper[3] - 600)
            r0, c0 = tpl.index(l, t_)
            r1, c1 = tpl.index(r_, b_)
            win = Window(c0, r0, c1 - c0, r1 - r0)
            ref = os.path.join(td, "ref.tif")
            with rasterio.open(ref, "w", driver="GTiff", height=win.height,
                               width=win.width, count=1, dtype="int16",
                               crs=tpl.crs,
                               transform=tpl.window_transform(win)) as dst:
                dst.write(np.zeros((win.height, win.width), np.int16), 1)
            tpl_crs, wtr = tpl.crs, tpl.window_transform(win)
        out = {}
        for band in (1, 2):
            single = os.path.join(td, f"m{band}.tif")
            with rasterio.open(merged) as srcm, rasterio.open(
                    single, "w", driver="GTiff", height=srcm.height,
                    width=srcm.width, count=1, dtype="float64",
                    crs=srcm.crs, transform=srcm.transform,
                    nodata=-9999) as dst:
                dst.write(srcm.read(band), 1)
            warped = os.path.join(td, f"w{band}.tif")
            warp_to_grid(single, ref, warped)
            with rasterio.open(warped) as sw:
                out[band] = sw.read(1)
        h, w = out[1].shape
        cols, rows = np.meshgrid(np.arange(w) + 0.5, np.arange(h) + 0.5)
        tx = wtr.c + cols * wtr.a
        ty = wtr.f + rows * wtr.e
        ex, ey = Transformer.from_crs(tpl_crs, "EPSG:5070",
                                      always_xy=True).transform(tx, ty)
        ok = out[1] != -9999
        d4x = float((out[1][ok] - ex[ok]).mean())
        d4y = float((out[2][ok] - ey[ok]).mean())
        print(f"   {'T4 merged + warp_to_grid onto template':44s} cells "
              f"{int(ok.sum())}  EE-minus-template-centre x {d4x:+8.2f}  "
              f"y {d4y:+8.2f} m (5070)")
        res["T4 (5070 frame)"] = (d4x, d4y)
        # T3: same lattice, explicit dimensions, no region
        p3 = os.path.join(td, "t_dims.tif")
        url = img5070.getDownloadURL({
            "crs": "EPSG:5070",
            "crs_transform": [PIXEL_M, 0, lower[0], 0, -PIXEL_M, lower[3]],
            "dimensions": "200x200", "format": "GEO_TIFF"})
        import requests
        r = requests.get(url, timeout=300)
        if r.status_code >= 400:
            print(f"   T3 refused: HTTP {r.status_code}: {r.text[:500]}")
        else:
            with open(p3, "wb") as f:
                f.write(r.content)
            with rasterio.open(p3) as s:
                res["T3"] = offsets(s.read(), s.transform,
                                    "T3 fetch with dimensions, no region")
        # W: generator route on the template grid
        with rasterio.open(template) as tpl:
            win = Window(tpl.width // 2, tpl.height // 2, 64, 64)
            imgt = ee.Image.pixelCoordinates(
                ee.Projection(tpl.crs.to_wkt())).toDouble()
            pw = os.path.join(td, "w.tif")
            gcs.fetch_window(ee, imgt, tpl.crs.to_wkt(),
                             tpl.window_transform(win), 64, 64, pw)
            with rasterio.open(pw) as s:
                res["W"] = offsets(s.read(), s.transform,
                                   "W fetch_window on template grid")
    wx, wy = res["W"]
    print("\nRelative to W (the registered route's convention):")
    for k, (dx, dy) in res.items():
        if k.startswith("T4"):
            continue
        print(f"   {k:24s} x {dx - wx:+7.2f} m  y {dy - wy:+7.2f} m  "
              f"(= {(dy - wy) / PIXEL_M:+.2f} rows)")
    t1x, t1y = res["T1 fetch_tile lower"]
    t4x, t4y = res["T4 (5070 frame)"]
    print(f"\nT4 (whole download route, nearest warp) relative to T1's "
          f"convention, EPSG:5070: x {t4x - t1x:+7.2f} m  y {t4y - t1y:+7.2f} m"
          f"  (one row ~ +/-30 m in y; nearest-warp noise averages to ~0)")


if __name__ == "__main__":
    main()
