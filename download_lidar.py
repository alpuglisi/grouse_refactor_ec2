"""
download_lidar.py

Downloads USGS 3DEP LiDAR-derived terrain features from Google Earth
Engine over each region's bounding box, at the resolution
models.FEATURE_SPEC declares for them (lidar_elev/lidar_rough,
currently 10m - see resolve_patch_geometry() in models.py, the single
source of truth this script and the training pipeline both defer to,
so the two can never disagree about resolution).

HONEST SCOPE: USGS/3DEP/1m is a BARE-EARTH ELEVATION DEM. There is no
canopy-height band in this EE collection - deriving one would need a
first-return DSM differenced against this DTM, which 3DEP does not
publish as a matching nationwide EE asset. This script does not
pretend otherwise. What it produces instead are two honest, genuinely
useful TERRAIN features, aggregated (not merely resampled) from the
native 1m data:
  lidar_elev  : mean bare-earth elevation per output cell (m)
  lidar_rough : local relief - the STD DEV of the native 1m elevation
                within each output cell. This is the actual payoff of
                starting from 1m data: microtopography (hummocks,
                drainage, edge structure) that a 30m, or even a
                resampled 10m, DEM cannot resolve - reduceResolution
                aggregates the real sub-cell variance; resampling
                would just pick/interpolate one value and throw it
                away.

COVERAGE: 3DEP LiDAR is flown project-by-project, not on a repeating
national schedule - large parts of a state may be uncovered, and
covered parts may date from any year the acquiring project flew.
raster_years()/raster_path() elsewhere in the pipeline treat these as
STATIC features (grouse_data.STATIC_FEATURES) exempt from the
vegetation year-currency policy, since terrain doesn't go stale the
way vegetation does. This script downloads ONE representative mosaic
per region (there is no repeating "next year" to choose between) and
reports actual AOI coverage honestly - a region with sparse 3DEP
flights will show a low percentage and much of its output will be
nodata (never silently filled).

AUTH: same as download_tcc_nlcd.py - run `earthengine authenticate`
once, pass --project (or set EARTHENGINE_PROJECT).

USAGE
    python download_lidar.py --project my-gee-project
    python download_lidar.py --regions NH --force
"""
import os
import sys
import argparse

import numpy as np
import rasterio
from rasterio.merge import merge as rio_merge
import tempfile
from tqdm import tqdm

_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _here)

from prepare_training_data import BOXES
from grouse_data import DataConfig
from models import FEATURE_SPEC, native_scale_m
from download_tcc_nlcd import ee_init, region_grid, tiles, fetch_tile, _fetch_all

COLLECTION_ID = "USGS/3DEP/1m"
NODATA = -9999
# Both features share one target resolution - models.py's FEATURE_SPEC
# is the single source of truth so download and training can't drift
# apart; lidar_elev/lidar_rough are defined with the same
# native_scale_m by construction (enforced by the assert below).
TARGET_PIXEL_M = native_scale_m("lidar_elev")
assert TARGET_PIXEL_M == native_scale_m("lidar_rough"), (
    "lidar_elev/lidar_rough must share one native_scale_m - "
    "download_lidar.py produces both at a single target resolution.")


def aoi_coverage(ee, geom):
    """(years present, fraction of the AOI actually covered by any
    3DEP 1m tile) - printed honestly since coverage is often partial."""
    col = ee.ImageCollection(COLLECTION_ID).filterBounds(geom)
    n = col.size().getInfo()
    if n == 0:
        return [], 0.0
    import datetime as dt
    starts = col.aggregate_array("system:time_start").getInfo()
    years = sorted({dt.datetime.fromtimestamp(t / 1000, dt.timezone.utc).year
                    for t in starts if t})
    mask = col.mosaic().mask()
    stats = mask.reduceRegion(
        reducer=ee.Reducer.mean(), geometry=geom, scale=90,
        maxPixels=1e10, bestEffort=True).getInfo()
    frac = float(next(iter(stats.values()), 0.0) or 0.0)
    return years, frac


def build_band_image(ee, geom, reducer_name):
    """3DEP 1m mosaic -> reduceResolution(reducer) -> reprojected to
    the target grid. reduceResolution aggregates the real sub-cell
    distribution (mean or stdDev of the native 1m pixels inside each
    output cell) - this is NOT the same as resampling, which would
    just pick/interpolate a single value and discard the variance
    reduceResolution preserves."""
    reducer = {"mean": ee.Reducer.mean(),
              "stdDev": ee.Reducer.stdDev()}[reducer_name]
    mosaic = ee.ImageCollection(COLLECTION_ID).filterBounds(geom).mosaic()
    proj = ee.Projection("EPSG:5070").atScale(TARGET_PIXEL_M)
    return (mosaic.reduceResolution(reducer=reducer, maxPixels=1024)
            .reproject(proj))


def build_lidar_raster(ee, feature, reducer_name, bounds_lonlat, out_path,
                       tile_m, workers, valid_range):
    x0, y0, x1, y1 = region_grid(bounds_lonlat)
    geom = ee.Geometry.Rectangle([x0, y0, x1, y1], "EPSG:5070", False)
    image = build_band_image(ee, geom, reducer_name)
    tile_list = list(tiles(x0, y0, x1, y1, tile_m))
    lo, hi = valid_range
    with tempfile.TemporaryDirectory() as td:
        paths = [os.path.join(td, f"t{i}.tif") for i in range(len(tile_list))]
        _fetch_all(len(tile_list),
                   lambda i: fetch_tile(ee, image, tile_list[i], paths[i]),
                   workers, f"   {os.path.basename(out_path)}")
        srcs = [rasterio.open(p) for p in paths]
        try:
            mosaic, transform = rio_merge(srcs)
        finally:
            for s in srcs:
                s.close()
        arr = mosaic[0].astype(np.float64)
        # 3DEP's own masked/no-data cells arrive as either NaN (GeoTIFF
        # export of a masked EE image) or an implausible value outside
        # the physically valid range for this band.
        out = np.where(np.isfinite(arr) & (arr >= lo) & (arr <= hi),
                      arr, NODATA)
        # Storage precision differs by band, chosen against int16's
        # +/-32767 range: elevation runs to ~1900m in these states, so
        # it's stored in whole METERS (a x100 cm scale would overflow
        # int16 above ~327m - well within New England's actual relief,
        # not a hypothetical edge case). Roughness is a much smaller
        # magnitude (mostly 0-3m, rarely >20m), so it's stored in
        # CENTIMETERS (x100) for sub-meter precision without risking
        # overflow. FEATURE_SPEC's scale divisors in models.py are
        # denominated in these SAME stored units.
        precision = 1.0 if feature == "lidar_elev" else 100.0
        out_i16 = np.where(out == NODATA, NODATA,
                           np.clip(out * precision, -32000, 32000)
                           ).astype(np.int16)
        valid_frac = float((out_i16 != NODATA).mean())
        with rasterio.open(out_path, "w", driver="GTiff",
                           height=out_i16.shape[0], width=out_i16.shape[1],
                           count=1, dtype="int16", crs="EPSG:5070",
                           transform=transform, nodata=NODATA,
                           compress="lzw", tiled=True) as dst:
            dst.write(out_i16, 1)
    print(f"   wrote {out_path} ({out_i16.shape[1]}x{out_i16.shape[0]} px, "
          f"{100 * valid_frac:.1f}% valid)")
    return valid_frac


def main():
    parser = argparse.ArgumentParser(
        description="Download USGS 3DEP LiDAR-derived terrain features "
                    "(elevation, local relief) from Earth Engine.")
    parser.add_argument("--regions", nargs="+", default=["ME", "NH", "VT"],
                        choices=list(BOXES))
    parser.add_argument("--project",
                        default=os.environ.get("EARTHENGINE_PROJECT"))
    parser.add_argument("--tile-m", type=int, default=48000,
                        help=f"Download tile edge in meters, at "
                             f"{TARGET_PIXEL_M}m/px. Smaller than "
                             f"download_tcc_nlcd.py's default because "
                             f"reduceResolution is heavier per-pixel "
                             f"than a plain band select.")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--year", type=int, default=None,
                        help="Nominal year stamped on the output "
                             "filename ({region}_{year}_lidar_*.tif). "
                             "Default: this region's most common 3DEP "
                             "acquisition year (LiDAR isn't annual, so "
                             "there is one representative mosaic per "
                             "region, not one per sighting year).")
    args = parser.parse_args()

    ee = ee_init(args.project)
    out_dir = args.out_dir or DataConfig().raster_dir
    os.makedirs(out_dir, exist_ok=True)
    print(f"USGS 3DEP 1m bare-earth DEM -> lidar_elev/lidar_rough at "
          f"{TARGET_PIXEL_M}m (matches models.FEATURE_SPEC "
          f"native_scale_m - do not change one without the other).")
    print("NOTE: 3DEP publishes bare-earth elevation only - these are "
          "terrain features (microtopography), not a canopy-height "
          "layer. See the module docstring for why.")

    for region in args.regions:
        x0, y0, x1, y1 = region_grid(BOXES[region])
        geom = ee.Geometry.Rectangle([x0, y0, x1, y1], "EPSG:5070", False)
        years, frac = aoi_coverage(ee, geom)
        year = args.year or (max(set(years), key=years.count)
                             if years else None)
        print(f"\n[{region}] 3DEP coverage: {100 * frac:.1f}% of AOI "
              f"({'no 3DEP tiles intersect this region - skipping' if not years else f'years present: {years}'})")
        if not years:
            continue
        print(f"   Nominal output year: {year} (most common acquisition "
              f"year present; parts of the region may date from "
              f"other years in {years}, or be uncovered -> nodata).")
        if frac < 0.5:
            print(f"   [warn] less than half the AOI has 3DEP coverage - "
                  f"most points in the remainder will read this "
                  f"feature as nodata, and (being STATIC_FEATURES) they "
                  f"will still train, just without this signal.")

        for feature, reducer_name, vrange in (
                ("lidar_elev", "mean", (-100.0, 6000.0)),
                ("lidar_rough", "stdDev", (0.0, 200.0))):
            out_path = os.path.join(out_dir, f"{region}_{year}_{feature}.tif")
            if os.path.exists(out_path) and not args.force:
                print(f"   {out_path} exists - skipping (--force to redo).")
                continue
            build_lidar_raster(ee, feature, reducer_name, BOXES[region],
                               out_path, args.tile_m, args.workers, vrange)

    print("\nDone. lidar_elev/lidar_rough are discovered automatically "
          "by grouse_data.py once these files exist; train.py's "
          "resolve_patch_geometry() grows the patch grid to "
          f"{TARGET_PIXEL_M}m/px the next time it runs against a "
          "feature set that includes them.")


if __name__ == "__main__":
    main()
