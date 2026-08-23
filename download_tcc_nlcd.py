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
from grouse_data import GrouseData, DataConfig

NODATA = -9999
PIXEL_M = 30
# Candidate collections are probed in order and the first that exists
# is used, so a newer product version added to the catalog is one list
# entry away.
PRODUCTS = {
    "tcc": {
        "collections": [
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
    try:
        import ee
    except ImportError:
        raise SystemExit("earthengine-api is not installed: "
                         "pip install earthengine-api")
    try:
        ee.Initialize(project=project) if project else ee.Initialize()
    except Exception as e:
        raise SystemExit(
            f"Earth Engine init failed ({e}).\nRun 'earthengine "
            f"authenticate' once on this machine, and pass a Google "
            f"Cloud project via --project or EARTHENGINE_PROJECT.")
    return ee


def resolve_collection(ee, candidates):
    """First candidate collection that exists and is non-empty."""
    for cid in candidates:
        try:
            if ee.ImageCollection(cid).limit(1).size().getInfo() > 0:
                return cid
        except Exception:
            continue
    raise SystemExit(f"None of the candidate collections exist/are "
                     f"readable: {candidates}")


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
            years |= {int(y) for y in re.findall(r"(19|20)\d{2}",
                                                 str(idx)) or []
                      if 1980 < int(y) < 2100}
        if not years:
            for idx in col.aggregate_array("system:index").getInfo():
                m = re.findall(r"\d{4}", str(idx))
                years |= {int(y) for y in m if 1980 < int(y) < 2100}
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
    grouse_data.raster_path), warning past +/-1; plus the latest
    published year for prediction-time use."""
    chosen = set()
    for sy in sorted(needed_years):
        c = min(product_years, key=lambda y: (abs(y - sy), y))
        if abs(c - sy) > 1:
            print(f"   [warn] sighting year {sy}: nearest published "
                  f"year is {c} ({abs(c - sy)} years off) - outside "
                  f"the +/-1 policy; the training loader will warn "
                  f"when it uses it.")
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


def fetch_tile(ee, image, band, rect, dest, retries=4):
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


def _fetch_all(tile_list, fetch_fn, workers, desc):
    """Fetch every tile through fetch_fn(index, rect) concurrently.
    Each getDownloadURL call is an EE server round-trip plus an HTTP
    transfer, and the tiles are independent - serializing them was the
    entire wall-clock cost. The first failure cancels the rest and
    propagates."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(fetch_fn, i, rect): i
                   for i, rect in enumerate(tile_list)}
        bar = tqdm(total=len(futures), desc=desc, leave=False)
        try:
            for fut in as_completed(futures):
                fut.result()
                bar.update(1)
        finally:
            bar.close()


def build_raster(ee, feature, spec, cid, year, bounds_lonlat, out_path,
                 tile_m, workers=8):
    image, band = year_image(ee, cid, spec["bands"], year)
    x0, y0, x1, y1 = region_grid(bounds_lonlat)
    tile_list = list(tiles(x0, y0, x1, y1, tile_m))
    lo, hi = spec["valid_range"]
    with tempfile.TemporaryDirectory() as td:
        paths = [os.path.join(td, f"t{i}.tif")
                 for i in range(len(tile_list))]
        _fetch_all(tile_list,
                   lambda i, rect=None: fetch_tile(
                       ee, image, band, tile_list[i], paths[i]),
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
        with rasterio.open(out_path, "w", driver="GTiff",
                           height=out.shape[0], width=out.shape[1],
                           count=1, dtype="int16", crs="EPSG:5070",
                           transform=transform, nodata=NODATA,
                           compress="lzw", tiled=True) as dst:
            dst.write(out, 1)
    print(f"   wrote {out_path} ({out.shape[1]}x{out.shape[0]} px, "
          f"{100 * valid_frac:.1f}% valid, band={band})")


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
            for year in years:
                out_path = os.path.join(out_dir,
                                        f"{region}_{year}_{feature}.tif")
                if os.path.exists(out_path) and not args.force:
                    print(f"   {out_path} exists - skipping "
                          f"(--force to redo).")
                    continue
                build_raster(ee, feature, spec, cid, year, BOXES[region],
                             out_path, args.tile_m, workers=args.workers)

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
