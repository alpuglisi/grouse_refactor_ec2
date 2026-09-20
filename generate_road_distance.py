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

MEMORY: the distance transform runs on the whole region grid at once
(it has to - a pixel's nearest road can be arbitrarily far), so peak
usage is roughly 12 bytes per raster pixel. A large state can want
several GB. Run one region at a time with --regions if that bites.

Usage:
    python generate_road_distance.py
    python generate_road_distance.py --regions NH
    python generate_road_distance.py --mtfcc S1100 S1200   # highways only
"""
import os
import glob
import argparse
import urllib.request

import numpy as np
import rasterio
import rasterio.features
from scipy.ndimage import distance_transform_edt

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
PAVED_MTFCC_DEFAULT = ["S1100", "S1200", "S1400", "S1630", "S1640"]


def _download(url, path):
    if os.path.exists(path):
        return path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    print(f"      downloading {os.path.basename(path)} ...")
    urllib.request.urlretrieve(url, path)
    return path


def county_fips(state_fp, tiger_year=TIGER_YEAR):
    """County FIPS codes for a state, from TIGER's national county file
    (one ~80MB download, cached, shared by all three regions)."""
    import geopandas as gpd
    path = os.path.join(CACHE_DIR, f"tl_{tiger_year}_us_county.zip")
    _download(f"https://www2.census.gov/geo/tiger/TIGER{tiger_year}/COUNTY/"
              f"tl_{tiger_year}_us_county.zip", path)
    counties = gpd.read_file(path)
    sel = counties[counties["STATEFP"] == state_fp]
    return sorted(sel["COUNTYFP"].tolist())


def load_paved_roads(region, mtfcc, target_crs, tiger_year=TIGER_YEAR):
    """Every county's TIGER roads for this state, filtered to the paved
    MTFCC classes and reprojected to the region raster's CRS."""
    import geopandas as gpd
    import pandas as pd
    state_fp = STATE_FIPS[region]
    fips = county_fips(state_fp, tiger_year)
    print(f"   {region}: {len(fips)} counties (TIGER {tiger_year})")
    frames = []
    for cf in fips:
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
    print(f"   {region}: {len(roads):,} paved road segments kept "
         f"({by_class})")
    return roads.to_crs(target_crs)


def build_distance_raster(roads, template_path):
    """Rasterize the road lines onto the template's exact grid, then
    Euclidean-distance-transform the complement. all_touched=True so a
    diagonal line marks every pixel it crosses instead of leaving gaps
    a nearest-neighbour rasterization would punch through it."""
    with rasterio.open(template_path) as src:
        transform, crs = src.transform, src.crs
        height, width = src.height, src.width
    mask = rasterio.features.rasterize(
        ((geom, 1) for geom in roads.geometry if geom is not None),
        out_shape=(height, width), transform=transform, fill=0,
        default_value=1, all_touched=True, dtype="uint8")
    covered = 100.0 * mask.sum() / mask.size
    print(f"      rasterized: {mask.sum():,} road pixels "
         f"({covered:.3f}% of the grid)")
    if mask.sum() == 0:
        raise SystemExit("No road pixels landed on this grid - check the "
                         "CRS/extent match between roads and rasters.")
    res_y, res_x = abs(transform.e), abs(transform.a)
    dist_m = distance_transform_edt(mask == 0, sampling=(res_y, res_x))
    return road_dist_encode(dist_m), dist_m, transform, crs


def process_region(region, data, mtfcc, tiger_year=TIGER_YEAR):
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
    roads = load_paved_roads(region, mtfcc, target_crs, tiger_year)
    encoded, dist_m, transform, crs = build_distance_raster(roads, template)
    # Reported in METRES (the encoded raster is log-scaled - see
    # models.road_dist_encode). A median anywhere near ROAD_DIST_MAX_M
    # would mean the sanity bound is actually binding, which it should
    # not be at any sane --mtfcc choice.
    pct = [float(np.percentile(dist_m, p)) for p in (50, 90, 99)]
    print(f"      distance: min {dist_m.min():.0f}m | median {pct[0]:.0f}m "
         f"| p90 {pct[1]:.0f}m | p99 {pct[2]:.0f}m | max "
         f"{dist_m.max():.0f}m")
    print(f"      encoded (log1p) int16 range: {encoded.min()}-"
         f"{encoded.max()}")
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
                           crs=crs, transform=transform, nodata=-9999,
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
    args = ap.parse_args()

    try:
        import geopandas  # noqa: F401
    except ImportError:
        raise SystemExit("generate_road_distance.py needs geopandas: "
                         "pip install geopandas")

    print(f"Paved MTFCC classes: {args.mtfcc} | TIGER {args.tiger_year}")
    data = GrouseData()
    for region in args.regions:
        process_region(region, data, args.mtfcc, args.tiger_year)
    print("\nDone. Re-run train.py - 'road_dist' is now discoverable in "
         "FEATURE_SPEC/RASTER_FEATURES and will be picked up "
         "automatically. NOTE: this adds an input channel, which is a "
         "GEOMETRY change - it needs a fresh training run, not --resume "
         "or --init-from.")


if __name__ == "__main__":
    main()
