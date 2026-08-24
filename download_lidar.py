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

import shutil

import numpy as np
import rasterio
from rasterio.transform import from_origin
from tqdm import tqdm

_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _here)

from prepare_training_data import BOXES
from grouse_data import DataConfig
from models import FEATURE_SPEC, native_scale_m
from download_tcc_nlcd import ee_init, region_grid, tiles, fetch_tile, _fetch_all

COLLECTION_ID = "USGS/3DEP/1m"
# lidar_elev comes from the SEAMLESS 10m 3DEP product instead of
# aggregating the 1m tiles: same LiDAR program (USGS resamples its best
# available source, largely the same 1m lidar, to 10m), already at our
# target resolution, and a plain single band that downloads exactly
# like TCC/NLCD did. Aggregating 1m->10m by MEAN buys essentially
# nothing over USGS's own 10m for the elevation value itself - and the
# 1m pull is what kept hitting EE's reprojection size cap. lidar_rough
# is the one feature that genuinely NEEDS the native 1m source (its
# entire point is sub-cell variance), so it alone keeps the
# reduceResolution chain, at a tile size derived below.
ELEV_COLLECTION_ID = "USGS/3DEP/10m_collection"   # current asset
ELEV_IMAGE_ID = "USGS/3DEP/10m"                   # deprecated fallback
# EE's reprojection cap, measured empirically across two failed runs:
# 28776x28433 rejected, and - decisively - 11511x11385 ALSO rejected
# (the 9600m attempt), so the cap sits below 1.31e8 px and is almost
# certainly the 10000px max-DIMENSION limit. A 5070-aligned tile pulled
# through the 1m UTM source inflates 1.199x linearly (28776/24000), so
# the tile edge must satisfy edge_m * 1.199 < 10000 -> edge <= ~8.3km.
# 6000m -> ~7194px input side: under the dimension cap with 28% margin.
ROUGH_TILE_M = 6000
NODATA = -9999
# Both features share one target resolution - models.py's FEATURE_SPEC
# is the single source of truth so download and training can't drift
# apart; lidar_elev/lidar_rough are defined with the same
# native_scale_m by construction (enforced by the assert below).
TARGET_PIXEL_M = native_scale_m("lidar_elev")
assert TARGET_PIXEL_M == native_scale_m("lidar_rough"), (
    "lidar_elev/lidar_rough must share one native_scale_m - "
    "download_lidar.py produces both at a single target resolution.")


def state_land_geometry(ee, region, bbox_geom):
    """The region's ACTUAL land area (US Census TIGER state polygon,
    clipped to the AOI bbox) instead of the raw lon/lat bounding
    rectangle. BOXES' bounding boxes are rectangles, not state outlines
    - ME's in particular includes a large slice of Atlantic Ocean and
    Canada (Quebec/New Brunswick), which 3DEP (CONUS-only) will NEVER
    cover regardless of how complete its actual Maine coverage is.
    Measuring coverage against the raw bbox (as an earlier version of
    this script did) deflates the reported percentage with guaranteed-
    empty non-US area - the same root cause diagnosed for NLCD/wetland
    composition earlier in this project. Falls back to the raw bbox
    (with a warning) if the TIGER asset or state code lookup fails, so
    a transient EE hiccup degrades to the old behavior rather than
    crashing the download."""
    try:
        states = ee.FeatureCollection("TIGER/2018/States")
        state = states.filter(ee.Filter.eq("STUSPS", region))
        if state.size().getInfo() == 0:
            raise ValueError(f"no TIGER state polygon for '{region}'")
        return state.geometry().intersection(bbox_geom, ee.ErrorMargin(30))
    except Exception as e:
        print(f"   [warn] could not load the TIGER state boundary for "
              f"land-clipped coverage ({e}) - falling back to the raw "
              f"bounding box, which includes ocean/out-of-state area "
              f"and will understate real land coverage.")
        return bbox_geom


def aoi_coverage(ee, geom):
    """(years present, fraction of the LAND geometry actually covered
    by any 3DEP 1m tile) - printed honestly since coverage is often
    partial even within actual land area."""
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


def elev_image(ee, geom):
    """lidar_elev: the SEAMLESS 3DEP 10m DEM, clipped to the AOI bbox.
    A plain single-band source already at the target resolution - no
    reduceResolution, no 1m pull, so none of the EE size-cap failure
    modes the 1m chain hits. Prefers the current 10m_collection asset
    (the single-image USGS/3DEP/10m is deprecated per EE's warning);
    falls back to the deprecated image - which still downloads
    correctly today - if the collection is unavailable."""
    try:
        col = ee.ImageCollection(ELEV_COLLECTION_ID).filterBounds(geom)
        if col.size().getInfo() > 0:
            return col.select("elevation").mosaic().clip(geom)
    except Exception:
        pass
    return ee.Image(ELEV_IMAGE_ID).select("elevation").clip(geom)


def rough_image(ee, geom):
    """lidar_rough: 3DEP 1m mosaic -> reduceResolution(stdDev) - the
    real per-output-cell variance of the native 1m elevations, which is
    the entire point of this feature and cannot come from any
    pre-aggregated product.

    Clip is to the plain bbox rectangle, NOT the TIGER land polygon: an
    earlier version clipped to the land geometry and every tile failed
    with "Unable to export unbounded image" (the state-polygon-
    intersect-rectangle geometry is a GeometryCollection EE would not
    treat as a bounded footprint). 3DEP is CONUS-only, so ocean/Canada
    mask out by absence of source data regardless; the land polygon
    stays in use for the coverage statistics, where it works.

    mosaic() DISCARDS source projections (composites arrive in EE's
    meaningless default WGS84 pseudo-projection and reduceResolution
    refuses them), so the mosaic is re-stamped with a source tile's
    native projection - EE's own documented pattern for this case.
    There is deliberately NO .reproject(): the download request's
    crs + crs_transform define the output grid. Even so, each request
    must pull the full 1m input under its tile through a reprojection,
    which EE caps - hence ROUGH_TILE_M (see its derivation above);
    build_lidar_raster enforces it for this feature."""
    col = ee.ImageCollection(COLLECTION_ID).filterBounds(geom)
    mosaic = col.mosaic().setDefaultProjection(col.first().projection())
    return (mosaic.reduceResolution(reducer=ee.Reducer.stdDev(),
                                    maxPixels=1024)
            .clip(geom))


def _process_tile(raw_path, out_tile_path, rect, feature, valid_range):
    """Raw EE float tile -> the final int16/LZW tile that assembly
    stitches. Converting at fetch time (instead of caching raw float32
    tiles) cuts the resume cache's disk footprint roughly 10x.

    3DEP's own masked/no-data cells arrive as either NaN (GeoTIFF
    export of a masked EE image) or an implausible value outside the
    physically valid range for this band.

    Storage precision differs by band, chosen against int16's +/-32767
    range: elevation runs to ~1900m in these states, so it's stored in
    whole METERS (a x100 cm scale would overflow int16 above ~327m -
    well within New England's actual relief, not a hypothetical edge
    case). Roughness is a much smaller magnitude (mostly 0-3m, rarely
    >20m), so it's stored in CENTIMETERS (x100) for sub-meter precision
    without risking overflow. FEATURE_SPEC's scale divisors in
    models.py are denominated in these SAME stored units."""
    lo, hi = valid_range
    precision = 1.0 if feature == "lidar_elev" else 100.0
    with rasterio.open(raw_path) as src:
        arr = src.read(1).astype(np.float64)
    w = int(round((rect[2] - rect[0]) / TARGET_PIXEL_M))
    h = int(round((rect[3] - rect[1]) / TARGET_PIXEL_M))
    if arr.shape != (h, w):
        raise RuntimeError(f"tile {rect}: EE returned {arr.shape}, "
                           f"expected {(h, w)} at {TARGET_PIXEL_M}m/px")
    out = np.where(np.isfinite(arr) & (arr >= lo) & (arr <= hi),
                   arr, NODATA)
    out_i16 = np.where(out == NODATA, NODATA,
                       np.clip(out * precision, -32000, 32000)
                       ).astype(np.int16)
    tmp = out_tile_path + ".part"
    with rasterio.open(tmp, "w", driver="GTiff", height=h, width=w,
                       count=1, dtype="int16", crs="EPSG:5070",
                       transform=from_origin(rect[0], rect[3],
                                             TARGET_PIXEL_M,
                                             TARGET_PIXEL_M),
                       nodata=NODATA, compress="lzw") as dst:
        dst.write(out_i16, 1)
    os.replace(tmp, out_tile_path)


def build_lidar_raster(ee, feature, bounds_lonlat,
                       out_path, tile_m, workers, valid_range):
    x0, y0, x1, y1 = region_grid(bounds_lonlat)
    geom = ee.Geometry.Rectangle([x0, y0, x1, y1], "EPSG:5070", False)
    if feature == "lidar_elev":
        image = elev_image(ee, geom)
    else:
        image = rough_image(ee, geom)
        tile_m = min(tile_m, ROUGH_TILE_M)   # 1m-pull size cap
    tile_list = list(tiles(x0, y0, x1, y1, tile_m))

    # Tiles are cached in a PERSISTENT directory (self-describing
    # names: the tile's grid rect), not a TemporaryDirectory: at 10m
    # the rough download runs for HOURS per state, and losing every
    # finished tile to one network hiccup near the end is not an
    # acceptable failure mode. A rerun skips tiles already on disk
    # (fetch_tile + _process_tile both write atomically, so an
    # existing file is a complete one); the cache is removed only
    # after the merged output is safely written.
    tile_dir = out_path + ".tiles"
    os.makedirs(tile_dir, exist_ok=True)

    def tile_path(rect):
        return os.path.join(
            tile_dir, "t_{}_{}_{}_{}.tif".format(*(int(v) for v in rect)))

    def fetch_one(i):
        rect = tile_list[i]
        final = tile_path(rect)
        if os.path.exists(final):
            return
        raw = final + ".raw"
        try:
            fetch_tile(ee, image, rect, raw, pixel_m=TARGET_PIXEL_M)
            _process_tile(raw, final, rect, feature, valid_range)
        finally:
            if os.path.exists(raw):
                os.remove(raw)

    n_cached = sum(os.path.exists(tile_path(r)) for r in tile_list)
    if n_cached:
        print(f"   resuming: {n_cached}/{len(tile_list)} tiles already "
              f"cached in {tile_dir}")
    _fetch_all(len(tile_list), fetch_one, workers,
               f"   {os.path.basename(out_path)}")

    # Assemble into ONE preallocated int16 canvas instead of
    # rasterio.merge: at 10m the ME grid is ~47k x 60k px, and merge's
    # float32 mosaic plus the float64 copy the old masking pass made
    # would need >20GB of RAM. int16 (2 bytes/px) plus one tile in
    # flight stays under ~6GB for the worst case; masking/scaling
    # already happened per-tile in _process_tile.
    width = int((x1 - x0) // TARGET_PIXEL_M)
    height = int((y1 - y0) // TARGET_PIXEL_M)
    canvas = np.full((height, width), NODATA, dtype=np.int16)
    for rect in tqdm(tile_list, desc="   assembling", leave=False):
        with rasterio.open(tile_path(rect)) as src:
            data = src.read(1)
        r0 = int((y1 - rect[3]) // TARGET_PIXEL_M)
        c0 = int((rect[0] - x0) // TARGET_PIXEL_M)
        canvas[r0:r0 + data.shape[0], c0:c0 + data.shape[1]] = data
    valid_frac = float((canvas != NODATA).mean())
    tmp_out = out_path + ".part"
    with rasterio.open(tmp_out, "w", driver="GTiff",
                       height=height, width=width,
                       count=1, dtype="int16", crs="EPSG:5070",
                       transform=from_origin(x0, y1, TARGET_PIXEL_M,
                                             TARGET_PIXEL_M),
                       nodata=NODATA,
                       compress="lzw", tiled=True) as dst:
        dst.write(canvas, 1)
    os.replace(tmp_out, out_path)
    shutil.rmtree(tile_dir)
    print(f"   wrote {out_path} ({width}x{height} px, "
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
    parser.add_argument("--tile-m", type=int, default=24000,
                        help=f"Download tile edge in meters, at "
                             f"{TARGET_PIXEL_M}m/px. Much smaller than "
                             f"download_tcc_nlcd.py's default for two "
                             f"compounding reasons: elevation is a "
                             f"FLOAT32 band (4 bytes/px vs TCC/NLCD's "
                             f"1 - a 48km tile is ~92MB uncompressed, "
                             f"double getDownloadURL's ~48MB cap and "
                             f"the cause of a 400 on every tile), and "
                             f"each output pixel is a server-side "
                             f"aggregation over ~100 native 1m pixels. "
                             f"24000 -> 2400x2400x4B = 23MB, safely "
                             f"under the cap; lower it further if EE "
                             f"reports compute timeouts.")
    parser.add_argument("--workers", type=int, default=24,
                        help="Concurrent EE download requests. Each "
                             "lidar_rough tile is dominated by SERVER-"
                             "side stdDev aggregation (~a minute per "
                             "tile), so concurrency is the main wall-"
                             "clock lever; EE permits roughly 40 "
                             "concurrent requests per user and the "
                             "default leaves headroom under that. "
                             "Raise toward ~32-40 if EE isn't "
                             "throttling you; transient 429s are "
                             "retried with backoff either way.")
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
        bbox_geom = ee.Geometry.Rectangle([x0, y0, x1, y1], "EPSG:5070", False)
        # BOXES rectangles overshoot real state borders (ME's in
        # particular includes a lot of Atlantic Ocean and Canada) -
        # measure and report coverage against actual LAND, not the
        # raw bbox, or a state showing e.g. 41% looks alarming when
        # most of that "missing" 59% was never going to have data
        # (ocean, Canada) regardless of how complete 3DEP's real
        # Maine coverage is.
        land_geom = state_land_geometry(ee, region, bbox_geom)
        years, frac = aoi_coverage(ee, land_geom)
        year = args.year or (max(set(years), key=years.count)
                             if years else None)
        print(f"\n[{region}] 3DEP coverage: {100 * frac:.1f}% of "
              f"{region}'s LAND area (excludes ocean/out-of-state "
              f"portions of the bounding box) "
              f"({'no 3DEP tiles intersect this region - skipping' if not years else f'years present: {years}'})")
        if not years:
            continue
        print(f"   Nominal output year: {year} (most common acquisition "
              f"year present; parts of the region may date from "
              f"other years in {years}, or be uncovered -> nodata).")
        if frac < 0.5:
            print(f"   [warn] less than half of {region}'s LAND area has "
                  f"3DEP coverage - most points in the remainder will "
                  f"read this feature as nodata, and (being "
                  f"STATIC_FEATURES) they will still train, just "
                  f"without this signal.")

        for feature, vrange in (("lidar_elev", (-100.0, 6000.0)),
                                ("lidar_rough", (0.0, 200.0))):
            out_path = os.path.join(out_dir, f"{region}_{year}_{feature}.tif")
            if os.path.exists(out_path) and not args.force:
                # Guard against outputs from the earlier pixel-size
                # bug: fetch_tile inherited the TCC/NLCD module's 30m
                # grid instead of this script's 10m target, so any
                # file written before the fix is at the wrong
                # resolution and must be rebuilt, not skipped.
                with rasterio.open(out_path) as src:
                    res = abs(src.transform.a)
                if abs(res - TARGET_PIXEL_M) < 1e-6:
                    print(f"   {out_path} exists - skipping "
                          f"(--force to redo).")
                    continue
                print(f"   {out_path} exists but at {res:g}m/px, not "
                      f"the {TARGET_PIXEL_M}m FEATURE_SPEC declares - "
                      f"rebuilding at the correct resolution.")
            build_lidar_raster(ee, feature, BOXES[region],
                               out_path, args.tile_m, args.workers, vrange)

    print("\nDone. lidar_elev/lidar_rough are discovered automatically "
          "by grouse_data.py once these files exist; train.py's "
          "resolve_patch_geometry() grows the patch grid to "
          f"{TARGET_PIXEL_M}m/px the next time it runs against a "
          "feature set that includes them.")


if __name__ == "__main__":
    main()
