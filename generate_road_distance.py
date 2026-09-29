"""
generate_road_distance.py

Builds the 'road_dist' model feature: metres to the nearest PAVED road,
rasterized onto each region's own raster grid.

WHY THIS FEATURE EXISTS
-----------------------
NLCD's 30m cells cannot resolve a two-lane road from the land cover it
cuts through. Verified directly with inspect_point.py on NH Route 16:
  - a point ON the pavement, narrow stretch:
        nlcd = 90 (WOODY WETLANDS), model score 0.68
  - a point ON the pavement, wider stretch:
        nlcd = 22 (Developed Low),  model score 0.09
Same road, same model. Where the road is narrower than a pixel it
simply vanishes into the wetland around it, the model scores that
wetland (correctly, by its own inputs), and the rendered map paints the
result over the road line. Distance-to-road is the one input that can
say "there is a road here" at a resolution the land-cover rasters
structurally cannot.

"PAVED", AND WHAT TIGER ACTUALLY KNOWS
-------------------------------------
TIGER/Line has NO surface attribute - nothing in the data literally
says "paved". What it has is MTFCC (feature class), which separates the
unpaved classes well enough to be useful here:

  INCLUDED by default (--mtfcc):
    S1100  Primary road (interstate/limited access)
    S1200  Secondary road (US/state highway)
    S1400  Local neighborhood road, rural road, city street
    S1630  Ramp
    S1640  Service drive
  EXCLUDED by default:
    S1500  Vehicular trail (4WD)          - unpaved by definition
    S1740  Private road for service vehicles (LOGGING roads, ranches)
    S1710/S1720/S1820/S1830  walkway / stairway / bike / bridle path
    S1780  Parking lot road
    S1750  Internal Census Bureau use

The real caveat is S1400: it lumps paved town roads together with rural
gravel, and TIGER cannot tell them apart. Dropping it would remove
nearly every paved secondary road in these states, which is far worse
than including some gravel - so it is in by default. Pass --mtfcc
S1100 S1200 for a strict highways-only definition.

OUTPUT
------
data/landfire/{REGION}_{YEAR}_road_dist.tif - int16, LOG-ENCODED as
round(log1p(metres) * 1000), not raw metres: see models.road_dist_encode
for why (a linear cap saturated Maine's median at highways-only MTFCC,
and raising it instead would have squeezed the near field flat).
models.road_dist_decode inverts it for anything that wants metres back.
Written once per year already present for that region, since roads are
static but the pipeline's year-matching expects a vintage per feature.

WHICH ROADS: EVERY US COUNTY THE GRID TOUCHES, NOT JUST THE STATE'S
-------------------------------------------------------------------
A region's grid is the LANDFIRE request rectangle, which reaches well
into the neighbouring states (NH's runs to -70.60, deep into Maine).
The original version loaded only the region's own state's counties, so
every pixel across a state line held the distance to the nearest road IN
THE HOME STATE: a Maine pixel beside Route 26 read as kilometres from
any road. Since training positives sit far from roads, that would turn
neighbouring-state land into "remote, grouse-like" land, and give every
training point near a border a wrong road distance.

Now roads come from every TIGER county, in any state, whose polygon
intersects the grid expanded by --pad-km (default 10 km). The distance
transform also runs on that expanded grid, so a road just outside the
region's edge still counts, then the result is cropped back to the
region grid.

Pixels outside every US county (Canada, open ocean) are written as
NODATA: TIGER has no roads there, so any distance would be invented.
missing_mask models see them as missing. Distances just SOUTH of the
Canadian border are still upper bounds (Canadian roads are absent); the
run prints how much of the grid lies outside US coverage.

MEMORY: the distance transform runs on the whole region grid at once
(it has to - a pixel's nearest road can be arbitrarily far), so peak
usage is roughly 12 bytes per raster pixel, counted on the grid PLUS
its --pad-km margin on every side. A large state can want several GB.
Run one region at a time with --regions, or lower --pad-km, if that
bites.

Usage:
    python generate_road_distance.py
    python generate_road_distance.py --regions NH
    python generate_road_distance.py --mtfcc S1100 S1200   # highways only
    python generate_road_distance.py --pad-km 20   # wider road margin
"""
import os
import glob
import argparse
import urllib.request

import numpy as np
import rasterio
import rasterio.features
from scipy.ndimage import distance_transform_edt
from rasterio.transform import Affine, array_bounds

from grouse_data import GrouseData
from models import ROAD_DIST_MAX_M, road_dist_encode

CACHE_DIR = "data/roads"
# TIGER/Line vintage. 2025 shapefiles were released September 2025
# (database updates through May 2025); a 2026 vintage was in progress
# for the geodatabase formats as of September 2026, so --tiger-year can
# be raised once the shapefiles are confirmed live. Changing the
# vintage changes road_dist's VALUES (not its geometry): re-run this
# script, and the patch cache rebuilds itself from the new mtimes.
TIGER_YEAR = 2025
STATE_FIPS = {"ME": "23", "NH": "33", "VT": "50"}
# Margin around the region grid for road loading and the distance
# transform: a road this far outside the grid still sets the distance of
# the pixels at its edge.
PAD_KM_DEFAULT = 10.0
ROAD_DIST_NODATA = -9999
PAVED_MTFCC_DEFAULT = ["S1100", "S1200", "S1400", "S1630", "S1640"]


def _download(url, path):
    if os.path.exists(path):
        return path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    print(f"      downloading {os.path.basename(path)} ...")
    urllib.request.urlretrieve(url, path)
    return path


def load_counties(tiger_year=TIGER_YEAR):
    """TIGER's national county polygons (one ~80MB download, cached,
    shared by all regions)."""
    import geopandas as gpd
    path = os.path.join(CACHE_DIR, f"tl_{tiger_year}_us_county.zip")
    _download(f"https://www2.census.gov/geo/tiger/TIGER{tiger_year}/COUNTY/"
              f"tl_{tiger_year}_us_county.zip", path)
    return gpd.read_file(path)


def counties_for_grid(counties, grid_bounds, grid_crs):
    """Every county, in ANY state, whose polygon intersects the grid's
    bounding box (minx, miny, maxx, maxy in grid_crs). Returns the
    matching rows reprojected to grid_crs."""
    from shapely.geometry import box
    import geopandas as gpd
    footprint = gpd.GeoSeries([box(*grid_bounds)], crs=grid_crs)
    footprint = footprint.to_crs(counties.crs).iloc[0]
    sel = counties[counties.intersects(footprint)]
    return sel.to_crs(grid_crs)


def load_paved_roads(county_rows, mtfcc, target_crs, tiger_year=TIGER_YEAR):
    """TIGER roads for the given counties (any states), filtered to the
    paved MTFCC classes and reprojected to the region raster's CRS."""
    import geopandas as gpd
    import pandas as pd
    frames = []
    for state_fp, cf in zip(county_rows["STATEFP"], county_rows["COUNTYFP"]):
        name = f"tl_{tiger_year}_{state_fp}{cf}_roads.zip"
        path = os.path.join(CACHE_DIR, name)
        _download(f"https://www2.census.gov/geo/tiger/TIGER{tiger_year}/"
                  f"ROADS/{name}", path)
        gdf = gpd.read_file(path)
        kept = gdf[gdf["MTFCC"].isin(mtfcc)]
        frames.append(kept[["MTFCC", "geometry"]])
    roads = pd.concat(frames, ignore_index=True)
    roads = gpd.GeoDataFrame(roads, geometry="geometry", crs=frames[0].crs)
    by_class = roads["MTFCC"].value_counts().to_dict()
    print(f"      {len(roads):,} paved road segments kept ({by_class})")
    return roads.to_crs(target_crs)


def padded_grid(transform, height, width, pad_px):
    """The grid expanded by pad_px pixels on every side: (transform,
    height, width). The region grid is the window [pad_px:pad_px+height,
    pad_px:pad_px+width] of it."""
    t = transform * Affine.translation(-pad_px, -pad_px)
    return t, height + 2 * pad_px, width + 2 * pad_px


def build_distance_raster(roads, template_path, pad_px=0, coverage=None):
    """Rasterize the road lines onto the template's grid EXPANDED by
    pad_px pixels, Euclidean-distance-transform the complement, and crop
    back to the template grid, so roads up to pad_px outside the grid
    still count. all_touched=True so a diagonal line marks every pixel it
    crosses instead of leaving gaps a nearest-neighbour rasterization
    would punch through it.

    coverage: polygons (in the template CRS) where road data exists
    (the US counties). Pixels outside them come back as NaN in dist_m
    and as ROAD_DIST_NODATA in the encoded raster.
    Returns (encoded int16, dist_m float with NaN, transform, crs)."""
    with rasterio.open(template_path) as src:
        transform, crs = src.transform, src.crs
        height, width = src.height, src.width
    p_transform, p_h, p_w = padded_grid(transform, height, width, pad_px)
    mask = rasterio.features.rasterize(
        ((geom, 1) for geom in roads.geometry if geom is not None),
        out_shape=(p_h, p_w), transform=p_transform, fill=0,
        default_value=1, all_touched=True, dtype="uint8")
    inner = mask[pad_px:pad_px + height, pad_px:pad_px + width]
    covered = 100.0 * inner.sum() / inner.size
    print(f"      rasterized: {inner.sum():,} road pixels inside the grid "
         f"({covered:.3f}%), {mask.sum() - inner.sum():,} in the "
         f"{pad_px}-px margin")
    if mask.sum() == 0:
        raise SystemExit("No road pixels landed on this grid - check the "
                         "CRS/extent match between roads and rasters.")
    res_y, res_x = abs(transform.e), abs(transform.a)
    dist_m = distance_transform_edt(mask == 0, sampling=(res_y, res_x))
    del mask
    dist_m = dist_m[pad_px:pad_px + height, pad_px:pad_px + width]
    encoded = road_dist_encode(dist_m)
    if coverage is not None:
        inside = rasterio.features.rasterize(
            ((geom, 1) for geom in coverage if geom is not None),
            out_shape=(height, width), transform=transform, fill=0,
            default_value=1, all_touched=True, dtype="uint8").astype(bool)
        dist_m = np.where(inside, dist_m, np.nan)
        encoded = np.where(inside, encoded,
                           ROAD_DIST_NODATA).astype(np.int16)
    return encoded, dist_m, transform, crs


def process_region(region, data, mtfcc, tiger_year=TIGER_YEAR,
                   pad_km=PAD_KM_DEFAULT):
    print(f"\n{'=' * 60}\n{region}\n{'=' * 60}")
    rd = data[region]
    template_feature = next(
        (f for f in rd.available_features() if f != "road_dist"), None)
    if template_feature is None:
        print(f"   [!] No rasters on disk for {region} - skipping.")
        return
    template = rd.latest_raster_path(template_feature)
    # The UNION of every feature's vintages, not just the template's:
    # nlcd/tcc reach back years further than evt/evh/evc do, and a
    # sighting year that resolves fine for nlcd should resolve fine for
    # road_dist too rather than tripping the year-gap warning. Roads are
    # static, so these are identical copies - the duplication buys
    # silence from machinery that legitimately expects a vintage per
    # feature, at a few MB each (a distance field deflates well).
    years = sorted({y for f in rd.available_features() if f != "road_dist"
                   for y in rd.raster_years(f)})
    print(f"   template grid: {os.path.basename(template)} "
         f"({rd.raster_years(template_feature)})")
    print(f"   years to write (union across all features): {years}")

    with rasterio.open(template) as src:
        target_crs = src.crs
        pad_px = int(round(pad_km * 1000.0 / abs(src.transform.a)))
        p_transform, p_h, p_w = padded_grid(src.transform, src.height,
                                            src.width, pad_px)
    w, s_, e, n = array_bounds(p_h, p_w, p_transform)
    grid_bounds = (min(w, e), min(s_, n), max(w, e), max(s_, n))
    county_rows = counties_for_grid(load_counties(tiger_year), grid_bounds,
                                    target_crs)
    by_state = county_rows.groupby("STATEFP").size().to_dict()
    print(f"   roads from {len(county_rows)} counties across "
         f"{len(by_state)} state(s) (STATEFP: {by_state}), grid + "
         f"{pad_km:g} km margin")
    roads = load_paved_roads(county_rows, mtfcc, target_crs, tiger_year)
    encoded, dist_m, transform, crs = build_distance_raster(
        roads, template, pad_px=pad_px, coverage=county_rows.geometry)
    outside = float(np.isnan(dist_m).mean())
    print(f"      {100 * outside:.1f}% of the grid lies outside US county "
         f"coverage (Canada/ocean) -> NODATA")
    if outside > 0:
        print("      [note] distances near the Canadian border are upper "
              "bounds: TIGER has no Canadian roads.")
    # Reported in METRES (the encoded raster is log-scaled - see
    # models.road_dist_encode). A median anywhere near ROAD_DIST_MAX_M
    # would mean the sanity bound is actually binding, which it should
    # not be at any sane --mtfcc choice.
    valid = dist_m[np.isfinite(dist_m)]
    pct = [float(np.percentile(valid, p)) for p in (50, 90, 99)]
    print(f"      distance: min {valid.min():.0f}m | median {pct[0]:.0f}m "
         f"| p90 {pct[1]:.0f}m | p99 {pct[2]:.0f}m | max "
         f"{valid.max():.0f}m")
    enc_valid = encoded[encoded != ROAD_DIST_NODATA]
    print(f"      encoded (log1p) int16 range: {enc_valid.min()}-"
         f"{enc_valid.max()}")
    if pct[0] >= ROAD_DIST_MAX_M * 0.5:
        print(f"      [warn] median distance is more than half the "
             f"{ROAD_DIST_MAX_M}m sanity bound - this road set is very "
             f"sparse for this region. Consider a broader --mtfcc (adding "
             f"S1400 local/rural roads) so the feature carries near-field "
             f"structure rather than mostly 'far'.")

    raster_dir = data.config.resolve(data.config.raster_dir)
    for year in years:
        out = os.path.join(raster_dir, f"{region}_{year}_road_dist.tif")
        with rasterio.open(out, "w", driver="GTiff",
                           height=encoded.shape[0], width=encoded.shape[1],
                           count=1, dtype="int16",
                           crs=crs, transform=transform,
                           nodata=ROAD_DIST_NODATA,
                           compress="deflate", predictor=2, tiled=True) as dst:
            dst.write(encoded, 1)
        print(f"      wrote {os.path.basename(out)} "
             f"({os.path.getsize(out) / 1e6:.1f} MB)")


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--regions", nargs="+", default=list(STATE_FIPS),
                    choices=list(STATE_FIPS))
    ap.add_argument("--mtfcc", nargs="+", default=PAVED_MTFCC_DEFAULT,
                    help="TIGER MTFCC road classes to treat as paved. "
                         "Default: %(default)s. Use S1100 S1200 for a "
                         "strict highways-only definition.")
    ap.add_argument("--tiger-year", type=int, default=TIGER_YEAR,
                    help="TIGER/Line vintage to download. Default: "
                         "%(default)s. Raise it when a newer shapefile "
                         "release is confirmed live; the URL pattern is "
                         "unchanged across vintages.")
    ap.add_argument("--pad-km", type=float, default=PAD_KM_DEFAULT,
                    help="Margin around each region grid for loading "
                         "roads and running the distance transform, so "
                         "roads just outside the grid still count. "
                         "Default: %(default)s km.")
    args = ap.parse_args()

    try:
        import geopandas  # noqa: F401
    except ImportError:
        raise SystemExit("generate_road_distance.py needs geopandas: "
                         "pip install geopandas")

    print(f"Paved MTFCC classes: {args.mtfcc} | TIGER {args.tiger_year}")
    data = GrouseData()
    for region in args.regions:
        process_region(region, data, args.mtfcc, args.tiger_year,
                       args.pad_km)
    print("\nDone. road_dist VALUES changed (roads from neighbouring "
         "states, NODATA outside US coverage). The patch cache rebuilds "
         "itself from the new mtimes, but every model trained on the old "
         "rasters learned from wrong distances near state lines - "
         "retrain with a fresh run (not --resume).")


if __name__ == "__main__":
    main()
