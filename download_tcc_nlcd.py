"""
download_tcc_nlcd.py

Downloads USFS Tree Canopy Cover (TCC) and Annual NLCD land cover from
Google Earth Engine over each region's bounding box, for the years the
grouse sightings actually need, and writes them into the standard
raster directory as {ST}_{year}_{feature}.tif - the same naming
convention grouse_data.py discovers automatically. Once the files
exist, train.py / predict.py pick the new features up with NO further
flags (dynamic geometry: FEATURE_SPEC now contains 'tcc' and 'nlcd').

PRODUCTS
  tcc  (continuous)  USFS Tree Canopy Cover: percent canopy 0-100,
                     Landsat-modeled, annual. EE collection
                     USGS/NLCD_RELEASES/2023_REL/TCC/v2023-5 (newer
                     versions probed first when available).
  nlcd (categorical) Annual NLCD land cover (LndCov): Anderson Level II
                     class codes, annual 1985-2023+.

YEAR SELECTION mirrors the pipeline's +/-1-year matching policy: the
script reads every sighting/negative year from the pipeline CSVs, maps
each to the closest year the product actually publishes, warns when
that is more than 1 year away, and also grabs the latest product year
(predict.py uses latest conditions). Only the resulting set of years is
downloaded. --years overrides.

NODATA: product nodata/non-processing values (NLCD 250/0, TCC >100) are
remapped to -9999 (int16), which the dataset layer already treats as
nodata -> padding.

GRID: Earth Engine delivers tiles on its own EPSG:5070 lattice, but the
LANDFIRE clips every other feature is built on sit in the LFPS local
Albers - and the training reader cuts each feature's window from that
feature's own grid, so a file left in 5070 is rotated against every
other channel (11 px at the patch corners, measured). The merged mosaic
is therefore warped onto the region's template grid (latest EVT clip,
nearest-neighbour) before it is written, exactly as realign_rasters.py
does for existing files. Without a LANDFIRE clip on disk the file stays
in 5070 and dataset.py will refuse it until realigned.

AUTH (one-time, on the machine that runs this):
    pip install earthengine-api
    earthengine authenticate          # opens a browser / prints a URL
    python download_tcc_nlcd.py --project <your-gcp-project-id>
The Google Cloud project is required by Earth Engine's API; pass it via
--project or the EARTHENGINE_PROJECT env var. NEVER paste
authentication codes into chats, scripts, or commits - the authenticate
flow stores credentials locally, and that is the only place they
belong.

USAGE
    python download_tcc_nlcd.py --project my-gee-project
    python download_tcc_nlcd.py --regions NH --features tcc --years 2020 2023
"""
import os
import io
import sys
import time
import math
import argparse
import tempfile

import numpy as np
import requests
import rasterio
from rasterio.merge import merge as rio_merge
from pyproj import Transformer
from tqdm import tqdm

_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _here)

from prepare_training_data import BOXES
from grouse_data import (GrouseData, DataConfig, YEAR_MATCH_TOLERANCE,
                         grid_mismatch)

NODATA = -9999
PIXEL_M = 30
# Candidate collections are probed in order and the first that exists
# is used, so a newer product version added to the catalog is one list
# entry away.
PRODUCTS = {
    "tcc": {
        "collections": [
            # v2025-6 (1985-2025). Two spellings are probed because the
            # catalog PAGE slug (underscores) and the asset ID (a slash
            # before the version) are easy to confuse, and a wrong
            # spelling fails the probe SILENTLY - resolve_collection
            # then falls back to v2023-5 and the last two years of TCC
            # quietly vanish. resolve_collection now prints which one
            # it settled on so that fallback is visible.
            "projects/gtac-data-publish/assets/TCC/Product_Version/2025-6",
            "projects/gtac-data-publish/assets/TCC/Product_Version_2025-6",
            "USGS/NLCD_RELEASES/2023_REL/TCC/v2023-5",
        ],
        "bands": ["Science_Percent_Tree_Canopy_Cover",
                  "NLCD_Percent_Tree_Canopy_Cover"],
        # values above 100 are mask/non-processing codes
        "valid_range": (0, 100),
    },
    "nlcd": {
        "collections": [
            "projects/sat-io/open-datasets/USGS/ANNUAL_NLCD/LANDCOVER",
        ],
        "bands": ["LndCov", "b1"],
        # Anderson II codes 11..95; 0 = background, 250 = nodata
        "valid_range": (11, 95),
    },
}


def ee_init(project):
    """Two auth paths, tried in order.

    1. Earth Engine's own stored credentials (written by
       `earthengine authenticate`). This is the normal case and needs
       nothing extra.
    2. Application Default Credentials, i.e. `gcloud auth
       application-default login`. This exists because `earthengine
       authenticate` (and ee.Authenticate(auth_mode='gcloud'), DESPITE
       its name) both drive their sign-in through Earth Engine's own
       shared OAuth client - and Google Workspace-managed accounts can
       have that specific client blocked outright ("This app is
       blocked... Google blocked this access", with no bypass link),
       while still allowing gcloud's own client through. When that
       happens, the fix is NOT to keep retrying `earthengine
       authenticate` - it is the same blocked client every time. Run:
           gcloud auth application-default login --scopes=\
               https://www.googleapis.com/auth/earthengine,\
               https://www.googleapis.com/auth/cloud-platform
           gcloud auth application-default set-quota-project <project>
       once, and this function picks the resulting credentials up
       automatically from then on - ee.Initialize(project=...)'s
       default path never looks for them on its own, which is why path
       1 fails first before this ever runs.
    """
    try:
        import ee
    except ImportError:
        raise SystemExit("earthengine-api is not installed: "
                         "pip install earthengine-api")
    try:
        ee.Initialize(project=project) if project else ee.Initialize()
        return ee
    except Exception as persistent_err:
        pass
    try:
        import google.auth
        credentials, adc_project = google.auth.default(scopes=[
            "https://www.googleapis.com/auth/earthengine",
            "https://www.googleapis.com/auth/cloud-platform",
        ])
        ee.Initialize(credentials, project=project or adc_project)
        print("   (authenticated via Application Default Credentials, "
             "not Earth Engine's own stored credentials - see ee_init's "
             "docstring if this is unexpected)")
        return ee
    except Exception as adc_err:
        raise SystemExit(
            f"Earth Engine init failed via both paths.\n"
            f"  earthengine's own credentials: {persistent_err}\n"
            f"  Application Default Credentials: {adc_err}\n"
            f"Run 'earthengine authenticate' once on this machine, and "
            f"pass a Google Cloud project via --project or "
            f"EARTHENGINE_PROJECT. If that specifically fails with "
            f"\"This app is blocked\" (common on Google Workspace-managed "
            f"accounts), run instead:\n"
            f"  gcloud auth application-default login --scopes="
            f"https://www.googleapis.com/auth/earthengine,"
            f"https://www.googleapis.com/auth/cloud-platform\n"
            f"  gcloud auth application-default set-quota-project "
            f"<project-id>")
    return ee


def resolve_collection(ee, candidates):
    """First candidate collection that exists and is non-empty. Says
    which - and which were skipped - because a fallback to an older
    product version is a silent loss of the newest years otherwise."""
    skipped = []
    for cid in candidates:
        try:
            if ee.ImageCollection(cid).limit(1).size().getInfo() > 0:
                if skipped:
                    print(f"   [note] using {cid}; not readable/empty: "
                          f"{skipped}")
                return cid
        except Exception as e:
            skipped.append(f"{cid} ({type(e).__name__})")
            continue
        skipped.append(f"{cid} (empty)")
    raise SystemExit(f"None of the candidate collections exist/are "
                     f"readable: {skipped}")


def collection_years(ee, cid):
    """Years published by a collection, from image dates (fallback:
    4-digit runs in the image ids)."""
    import re
    col = ee.ImageCollection(cid)
    years = set()
    try:
        starts = col.aggregate_array("system:time_start").getInfo()
        import datetime as dt
        years |= {dt.datetime.fromtimestamp(t / 1000,
                                            dt.timezone.utc).year
                  for t in starts if t}
    except Exception:
        pass
    if not years:
        for idx in col.aggregate_array("system:index").getInfo():
            years |= {int(y) for y in re.findall(r"(?:19|20)\d{2}",
                                                 str(idx))
                      if 1980 < int(y) < 2100}
    return sorted(years)


def year_image(ee, cid, band_prefs, year):
    """Single-band mosaic of a collection's images for one year."""
    col = ee.ImageCollection(cid)
    sub = col.filter(ee.Filter.calendarRange(year, year, "year"))
    if sub.size().getInfo() == 0:
        sub = col.filter(ee.Filter.stringContains("system:index",
                                                  str(year)))
    if sub.size().getInfo() == 0:
        raise RuntimeError(f"{cid} has no images for {year}")
    bands = sub.first().bandNames().getInfo()
    band = next((b for b in band_prefs if b in bands), bands[0])
    return sub.select(band).mosaic(), band


def sighting_years(rd):
    """Every year appearing in this region's positives/negatives."""
    ys = set()
    for getter in (rd.positives, rd.negatives):
        try:
            df = getter("all")
        except Exception:
            continue
        if "year" in df.columns:
            ys |= {int(y) for y in df["year"].dropna().astype(int)}
    return ys


def choose_product_years(product_years, needed_years):
    """The set of product years to download: for each sighting year the
    closest published year (ties -> earlier, matching
    grouse_data.raster_path), warning past the pipeline's shared
    YEAR_MATCH_TOLERANCE; plus the latest published year for
    prediction-time use."""
    chosen = set()
    for sy in sorted(needed_years):
        c = min(product_years, key=lambda y: (abs(y - sy), y))
        if abs(c - sy) > YEAR_MATCH_TOLERANCE:
            print(f"   [warn] sighting year {sy}: nearest published "
                  f"year is {c} ({abs(c - sy)} years off) - outside "
                  f"the +/-{YEAR_MATCH_TOLERANCE} policy; train.py "
                  f"will EXCLUDE these records unless "
                  f"--max-train-year-gap loosens it.")
        chosen.add(c)
    chosen.add(max(product_years))
    return sorted(chosen)


def region_grid(bounds_lonlat, pad_m=2000):
    """(x0, y0, x1, y1) in EPSG:5070, padded and snapped to the 30 m
    grid so every tile and the merged mosaic share pixel edges."""
    t = Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True)
    lons = [bounds_lonlat[0], bounds_lonlat[0],
            bounds_lonlat[2], bounds_lonlat[2]]
    lats = [bounds_lonlat[1], bounds_lonlat[3],
            bounds_lonlat[1], bounds_lonlat[3]]
    xs, ys = t.transform(lons, lats)
    x0 = math.floor((min(xs) - pad_m) / PIXEL_M) * PIXEL_M
    y0 = math.floor((min(ys) - pad_m) / PIXEL_M) * PIXEL_M
    x1 = math.ceil((max(xs) + pad_m) / PIXEL_M) * PIXEL_M
    y1 = math.ceil((max(ys) + pad_m) / PIXEL_M) * PIXEL_M
    return x0, y0, x1, y1


def tiles(x0, y0, x1, y1, tile_m):
    for ty in range(int(y0), int(y1), int(tile_m)):
        for tx in range(int(x0), int(x1), int(tile_m)):
            yield tx, ty, min(tx + tile_m, x1), min(ty + tile_m, y1)


def fetch_tile(ee, image, rect, dest, retries=4):
    """One getDownloadURL request -> GeoTIFF on disk, with backoff.
    crs_transform pins the global 30 m grid so tiles merge exactly."""
    params = {
        "crs": "EPSG:5070",
        "crs_transform": [PIXEL_M, 0, rect[0], 0, -PIXEL_M, rect[3]],
        "region": ee.Geometry.Rectangle(list(rect), "EPSG:5070", False),
        "format": "GEO_TIFF",
    }
    delay = 2.0
    for attempt in range(retries + 1):
        try:
            url = image.getDownloadURL(params)
            r = requests.get(url, timeout=300)
            r.raise_for_status()
            with open(dest, "wb") as f:
                f.write(r.content)
            with rasterio.open(dest):     # parse check
                pass
            return
        except Exception as e:
            if attempt == retries:
                raise RuntimeError(f"tile {rect} failed after "
                                   f"{retries + 1} attempts: {e}")
            time.sleep(delay)
            delay *= 2


def _fetch_all(n_tiles, fetch_fn, workers, desc):
    """Fetch every tile through fetch_fn(index) concurrently. Each
    getDownloadURL call is an EE server round-trip plus an HTTP
    transfer, and the tiles are independent - serializing them was the
    entire wall-clock cost. On the first failure, queued tiles are
    CANCELLED before the error propagates (plain executor shutdown
    would let every queued tile run its full retry cycle first)."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(fetch_fn, i): i for i in range(n_tiles)}
        bar = tqdm(total=len(futures), desc=desc, leave=False)
        try:
            for fut in as_completed(futures):
                try:
                    fut.result()
                except Exception:
                    ex.shutdown(wait=False, cancel_futures=True)
                    raise
                bar.update(1)
        finally:
            bar.close()


def template_raster(rd):
    """The region's template grid (its latest EVT clip - the grid
    road_dist/tsd/TreeMap are written on and dataset.py requires every
    feature to share), or None when no LANDFIRE clip exists yet."""
    if not rd.raster_years("evt"):
        return None
    return rd.latest_raster_path("evt")


def build_raster(ee, feature, spec, cid, year, bounds_lonlat, out_path,
                 tile_m, workers=8, template=None):
    image, band = year_image(ee, cid, spec["bands"], year)
    x0, y0, x1, y1 = region_grid(bounds_lonlat)
    tile_list = list(tiles(x0, y0, x1, y1, tile_m))
    lo, hi = spec["valid_range"]
    with tempfile.TemporaryDirectory() as td:
        paths = [os.path.join(td, f"t{i}.tif")
                 for i in range(len(tile_list))]
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
        out = np.where((arr >= lo) & (arr <= hi), arr,
                       NODATA).astype(np.int16)
        valid_frac = float((out != NODATA).mean())
        if valid_frac < 0.01:
            raise RuntimeError(
                f"{out_path}: <1% valid pixels after masking - wrong "
                f"collection/band/region? (band={band})")
        # The mosaic is on Earth Engine's EPSG:5070 lattice. The
        # training reader cuts every feature's window from that
        # feature's own grid, so this file MUST end up on the region's
        # template grid (the LFPS local Albers the LANDFIRE clips use)
        # or its windows are rotated against every other channel's -
        # 11 px at the corners, measured. Written to a temp file in
        # 5070 first, then warped onto the template exactly as
        # realign_rasters.py does for files already on disk. Nearest:
        # nlcd is categorical and tcc an integer percent.
        merged = os.path.join(td, "merged_5070.tif")
        with rasterio.open(merged, "w", driver="GTiff",
                           height=out.shape[0], width=out.shape[1],
                           count=1, dtype="int16", crs="EPSG:5070",
                           transform=transform, nodata=NODATA,
                           compress="lzw", tiled=True) as dst:
            dst.write(out, 1)
        if template is not None:
            from realign_rasters import warp_to_grid
            warp_to_grid(merged, template, out_path)
            with rasterio.open(out_path) as chk, \
                    rasterio.open(template) as ref:
                why = grid_mismatch(chk, ref)
                shape = (chk.width, chk.height)
            if why:
                raise RuntimeError(f"{out_path}: still not on the "
                                   f"template grid after warping: {why}")
            grid_note = f"on template grid {os.path.basename(template)}"
        else:
            import shutil
            shutil.copyfile(merged, out_path)
            shape = (out.shape[1], out.shape[0])
            grid_note = ("EPSG:5070 - NO LANDFIRE template yet; run "
                         "realign_rasters.py --apply once the LANDFIRE "
                         "clips exist, or dataset.py will refuse it")
    print(f"   wrote {out_path} ({shape[0]}x{shape[1]} px, "
          f"{100 * valid_frac:.1f}% valid, band={band}, {grid_note})")


def main():
    parser = argparse.ArgumentParser(
        description="Download USFS TCC + Annual NLCD from Earth Engine "
                    "into the pipeline's raster directory.")
    parser.add_argument("--regions", nargs="+", default=["ME", "NH", "VT"],
                        choices=list(BOXES))
    parser.add_argument("--features", nargs="+", default=["tcc", "nlcd"],
                        choices=list(PRODUCTS))
    parser.add_argument("--years", nargs="+", type=int, default=None,
                        help="Explicit product years; default: derived "
                             "from the sighting years on disk via the "
                             "+/-1 matching policy, plus the latest "
                             "published year.")
    parser.add_argument("--project",
                        default=os.environ.get("EARTHENGINE_PROJECT"),
                        help="Google Cloud project for Earth Engine "
                             "(or set EARTHENGINE_PROJECT).")
    parser.add_argument("--tile-m", type=int, default=96000,
                        help="Download tile edge in meters. 96000 = "
                             "3200x3200 px per tile, comfortably under "
                             "getDownloadURL's ~48MB uncompressed cap "
                             "for these 8/16-bit single-band products; "
                             "shrink it if EE returns size errors.")
    parser.add_argument("--workers", type=int, default=8,
                        help="Concurrent tile downloads. Tiles are "
                             "independent; 8 parallel requests is well "
                             "inside EE's per-user concurrency quota. "
                             "Lower this if you see 429 rate-limit "
                             "retries piling up.")
    parser.add_argument("--out-dir", default=None,
                        help="Raster directory; default: the pipeline's "
                             "standard data/landfire.")
    parser.add_argument("--force", action="store_true",
                        help="Re-download files that already exist.")
    args = parser.parse_args()

    ee = ee_init(args.project)
    out_dir = args.out_dir or DataConfig().raster_dir
    os.makedirs(out_dir, exist_ok=True)
    data = GrouseData()

    for feature in args.features:
        spec = PRODUCTS[feature]
        cid = resolve_collection(ee, spec["collections"])
        pub_years = collection_years(ee, cid)
        if not pub_years:
            raise SystemExit(f"Could not determine published years for "
                             f"{cid}.")
        print(f"{feature}: {cid} (years {pub_years[0]}-{pub_years[-1]})")
        for region in args.regions:
            if args.years:
                years = sorted(set(args.years) & set(pub_years))
                skipped = sorted(set(args.years) - set(pub_years))
                if skipped:
                    print(f"   [warn] {region}: requested years "
                          f"{skipped} not published - skipped.")
            else:
                need = sighting_years(data[region])
                if not need:
                    print(f"   [warn] {region}: no sighting years found "
                          f"on disk - downloading latest year only.")
                    need = {max(pub_years)}
                years = choose_product_years(pub_years, need)
            print(f"   {region}: downloading years {years}")
            template = template_raster(data[region])
            if template is None:
                print(f"   [warn] {region}: no LANDFIRE evt clip on disk "
                      f"yet - output stays in EPSG:5070 and must be "
                      f"realigned (realign_rasters.py --apply) before "
                      f"training; dataset.py refuses mixed grids.")
            for year in years:
                out_path = os.path.join(out_dir,
                                        f"{region}_{year}_{feature}.tif")
                if os.path.exists(out_path) and not args.force:
                    print(f"   {out_path} exists - skipping "
                          f"(--force to redo).")
                    continue
                build_raster(ee, feature, spec, cid, year, BOXES[region],
                             out_path, args.tile_m, workers=args.workers,
                             template=template)

    print("\nDone. grouse_data.py discovers the new rasters "
          "automatically:\n  - train.py will list tcc/nlcd under "
          "'Model features (discovered)' on its next run (delete stale "
          "patch caches under data/cache if you want them rebuilt "
          "immediately - the cache key includes the feature list, so "
          "new caches are built either way).\n  - predict.py picks "
          "them up the same way; models trained WITHOUT these features "
          "still predict correctly (the checkpoint's own feature list "
          "wins).")


if __name__ == "__main__":
    main()
