"""diagnose_source_lattice.py - BUG-0094 root cause, step 2.

diagnose_fetch_tile_offset.py showed the download route's own geometry is
exact (fetch_tile, rio_merge and warp_to_grid all within 0.1 m), so the
one-row shift must enter where Earth Engine RESAMPLES a source onto the
requested grid. Hypothesis: NLCD/TCC/TreeMap sit on a 30 m Albers grid
whose pixel edges are at odd multiples of 15 m, so every centre of the
0-origin EPSG:5070 lattice that fetch_tile requests lands exactly on a
corner of four source pixels, and nearest-neighbour breaks that tie the
same way every time.

This prints each source's native projection and its origin modulo 30 m,
then, for NLCD, fetches one tile on the 0-origin lattice and the same
area on the source's own lattice, and counts which of the four source
pixels around each output centre the output value came from (NW, NE,
SW, SE; a cell is decisive when exactly one neighbour matches).

Read-only; temporary files only. Usage (repository root):
    python diagnose_source_lattice.py --region NH
"""
import argparse
import os
import tempfile

import numpy as np
import rasterio

import download_tcc_nlcd as dtn
import generate_canopy_structure as gcs
from grouse_data import GrouseData

PIXEL_M = 30


def native(ee, image, name):
    p = image.projection().getInfo()
    t = p.get("transform")
    crs = p.get("crs") or p.get("wkt", "")[:40]
    if t:
        print(f"   {name:24s} crs {crs}, transform {t}; origin mod 30: "
              f"x {t[2] % PIXEL_M:g}, y {t[5] % PIXEL_M:g}")
    else:
        print(f"   {name:24s} crs {crs}, no affine transform reported: {p}")
    return t


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--region", default="NH")
    ap.add_argument("--project", default=os.environ.get("EARTHENGINE_PROJECT"))
    args = ap.parse_args()
    ee = dtn.ee_init(args.project)
    rd = GrouseData()[args.region]
    print("Native grids:")
    spec = dtn.PRODUCTS["nlcd"]
    cid = dtn.resolve_collection(ee, spec["collections"])
    year = max(rd.raster_years("nlcd"))
    col = ee.ImageCollection(cid).filter(
        ee.Filter.calendarRange(year, year, "year"))
    nlcd_t = native(ee, col.first(), f"nlcd {year}")
    tspec = dtn.PRODUCTS["tcc"]
    tcid = dtn.resolve_collection(ee, tspec["collections"])
    native(ee, ee.ImageCollection(tcid).first(), "tcc")
    for v in (2016, 2020, 2022):
        aid = f"USFS/GTAC/TreeMap/v{v}"
        try:
            c = ee.ImageCollection(aid)
            img = c.first() if c.size().getInfo() > 0 else ee.Image(aid)
        except ee.EEException:
            img = ee.Image(aid)
        try:
            native(ee, img, f"TreeMap v{v}")
        except ee.EEException as e:
            print(f"   TreeMap v{v}: {type(e).__name__}: {e}")
    if not nlcd_t or nlcd_t[1] != 0 or nlcd_t[3] != 0 \
            or abs(nlcd_t[0]) != PIXEL_M:
        print("NLCD native grid is not a north-up 30 m affine; the "
              "tie-break test below assumes it is - stopping.")
        return

    image, band = dtn.year_image(ee, cid, spec["bands"], year)
    bounds = gcs.template_bounds_lonlat(dtn.template_raster(rd))
    x0, y0, x1, y1 = dtn.region_grid(bounds, grid=dtn.BUG0094_ZERO_GRID)
    cx = x0 + ((x1 - x0) // 2 // 6000) * 6000
    cy = y0 + ((y1 - y0) // 2 // 6000) * 6000
    rect = (cx, cy, cx + 6000, cy + 6000)
    ox, oy = nlcd_t[2] % PIXEL_M, nlcd_t[5] % PIXEL_M
    nrect = (rect[0] - PIXEL_M + ox, rect[1] - PIXEL_M + oy,
             rect[2] + PIXEL_M + ox, rect[3] + PIXEL_M + oy)
    with tempfile.TemporaryDirectory() as td:
        pz, pn = os.path.join(td, "zero.tif"), os.path.join(td, "native.tif")
        dtn.fetch_tile(ee, image, rect, pz, crs="EPSG:5070")
        dtn.fetch_tile(ee, image, nrect, pn, crs="EPSG:5070")
        with rasterio.open(pz) as s:
            z, zt = s.read(1), s.transform
        with rasterio.open(pn) as s:
            n, nt = s.read(1), s.transform
    print(f"\nNLCD {year} tile {rect}: 0-origin lattice vs native lattice "
          f"(origin offset x {ox:g}, y {oy:g} m)")
    counts = {"NW": 0, "NE": 0, "SW": 0, "SE": 0}
    decisive = ambiguous = 0
    h, w = z.shape
    for r in range(h):
        y = zt.f + (r + 0.5) * zt.e
        rf = (nt.f - y) / PIXEL_M
        for c in range(w):
            x = zt.c + (c + 0.5) * zt.a
            cf = (x - nt.c) / PIXEL_M
            if abs(rf - round(rf)) > 1e-6 or abs(cf - round(cf)) > 1e-6:
                continue            # centre not on a native corner
            R, C = int(round(rf)), int(round(cf))
            if not (1 <= R < n.shape[0] and 1 <= C < n.shape[1]):
                continue
            nb = {"NW": n[R - 1, C - 1], "NE": n[R - 1, C],
                  "SW": n[R, C - 1], "SE": n[R, C]}
            hit = [k for k, v in nb.items() if v == z[r, c]]
            if len(hit) == 1:
                counts[hit[0]] += 1
                decisive += 1
            else:
                ambiguous += 1
    if decisive == 0:
        print("   no output centre falls on a native corner: the "
              "tie-break hypothesis does not apply")
        return
    print(f"   decisive cells {decisive:,} (ambiguous {ambiguous:,}); "
          f"source pixel taken:")
    for k, v in counts.items():
        print(f"      {k}: {v:,} ({v / decisive:.1%})")


if __name__ == "__main__":
    main()
