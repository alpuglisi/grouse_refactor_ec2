"""
download_treemap.py

Downloads the three raw USFS TreeMap attributes this project uses
(BALIVE, TPA_LIVE, CARBON_DWN) from Google Earth Engine, over each
region's bounding box, and writes them in the exact filename
convention generate_treemap_features.py already expects under
--src-dir. Run this, then run that:

    python download_treemap.py --project <your-gcp-project-id>
    python generate_treemap_features.py --src-dir data/treemap_raw

WHY EARTH ENGINE, NOT THE USFS RASTERGATEWAY
----------------------------------------------
The rastergateway page (data.fs.usda.gov/geodata/rastergateway/treemap)
serves per-attribute downloads through an HTML <select> whose option
values are not visible HTML attributes - a script cannot construct
their URLs, and reading the page returns only the visible dropdown
text, not the hrefs. That is why generate_treemap_features.py takes a
manually-populated --src-dir rather than downloading anything itself.

TreeMap is ALSO published as an Earth Engine ImageCollection per
vintage - USFS/GTAC/TreeMap/v2016, v2020, v2022 - which this project
already has working machinery for (download_tcc_nlcd.py fetches tcc
and nlcd the same way). This script reuses that machinery rather than
fighting the rastergateway form.

**2023 is NOT available this way.** Only v2016/v2020/v2022 exist in
the Earth Engine catalog as of this writing; TreeMap 2023
(RDS-2026-0038) is recent enough that it has not been ingested yet.
generate_treemap_features.py already tolerates a partial vintage set -
it maps every one of our raster years to the NEAREST vintage it
actually finds - so running with only three vintages costs nothing
beyond what a missing 2023 vintage always would. If 2023 coverage
matters later, it has to come from the RDS zip (RDS-2026-0038,
fs.usda.gov Research Data Archive) instead.

BAND NAMES ARE VERIFIED AT RUNTIME, NOT HARDCODED
--------------------------------------------------
This project has been burned before by confidently-stated facts that
turned out to be recalled rather than checked. The exact band names on
each TreeMap vintage were not independently confirmed band-by-band
before this was written - only that BALIVE/TPA_LIVE/CARBON_DWN-shaped
attributes exist somewhere in a ~22-24 band image. So this script reads
the real band list from Earth Engine on every run and matches
case-insensitively; if an expected attribute is not found, it prints
every band name that WAS found and stops, rather than silently
downloading the wrong one.

NATIVE UNITS, NOT THIS PROJECT'S int16 ENCODING
-------------------------------------------------
Written as Float32, in TreeMap's own units (ft2/acre, stems/acre,
tons/acre) - the same thing a rastergateway download would have been.
generate_treemap_features.py owns the QMD derivation, the smoothing,
and the log/fixed-point encoding into this project's int16 rasters;
this script's only job is getting the raw numbers onto disk.

NON-FOREST: unmask(0) AT DOWNLOAD TIME, NOT LEFT AS A SENTINEL
------------------------------------------------------------------
TreeMap is masked (not simply zero) off forest in Earth Engine, and the
rastergateway's own NoData convention is famously unhelpful
(4.2949673e+09, R's default, which GDAL will not auto-detect). Rather
than carry that sentinel downstream and have generate_treemap_features
scrub it, every band is unmasked to 0 before download - which is also
the correct VALUE, not just a placeholder: a non-forest pixel really
does have zero live basal area, zero live stems, and zero down dead
wood. generate_treemap_features.py's own non-forest convention (see its
docstring) already expects exactly this.

RESAMPLING
----------
No .resample() call, so Earth Engine's export uses its default nearest-
neighbor pixel interpolation. TreeMap's value at a pixel is one imputed
FIA plot's measurement; interpolating between plots would invent a
number that corresponds to no plot at all. (Same reasoning
generate_treemap_features.py already applies at its own resampling
step, onto this project's per-region raster grid.)

AUTH (one-time, on the machine that runs this) - same as
download_tcc_nlcd.py:
    pip install earthengine-api
    earthengine authenticate
    python download_treemap.py --project <your-gcp-project-id>
NEVER paste authentication codes into chats, scripts, or commits - the
authenticate flow stores credentials locally, and that is the only
place they belong.

USAGE
    python download_treemap.py --project my-gee-project
    python download_treemap.py --project my-gee-project --regions NH
    python download_treemap.py --project my-gee-project --vintages 2022
"""
import os
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

DEFAULT_OUT_DIR = "data/treemap_raw"
PIXEL_M = 30
TREEMAP_VINTAGES = [2016, 2020, 2022]   # 2023 not yet in the EE catalog
ATTRS = ["BALIVE", "TPA_LIVE", "CARBON_DWN"]
ASSET_TEMPLATE = "USFS/GTAC/TreeMap/v{year}"


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


def resolve_vintage_image(ee, vintage):
    """One mosaicked image for a TreeMap vintage, tolerant of the
    asset being published as either an ImageCollection (the pattern
    Google's own example code uses) or a single Image - the catalog
    listing text was ambiguous about which, so both are tried rather
    than assumed."""
    asset_id = ASSET_TEMPLATE.format(year=vintage)
    try:
        col = ee.ImageCollection(asset_id)
        if col.size().getInfo() > 0:
            return col.mosaic(), asset_id
    except Exception:
        pass
    try:
        img = ee.Image(asset_id)
        img.bandNames().getInfo()   # forces a real check, not a lazy ref
        return img, asset_id
    except Exception as e:
        raise SystemExit(f"Could not open {asset_id} as either an "
                         f"ImageCollection or an Image: {e}")


def resolve_band(available, wanted):
    """Case-insensitive match of one wanted attribute name against the
    band names actually present. Fails loud with the real list rather
    than guessing - see the module docstring on why."""
    lut = {b.lower(): b for b in available}
    hit = lut.get(wanted.lower())
    if hit is None:
        raise SystemExit(
            f"Attribute '{wanted}' not found. Bands actually present "
            f"on this asset: {available}\nUpdate ATTRS in this script "
            f"to match the real band name, or drop it.")
    return hit


def region_grid(bounds_lonlat, pad_m=2000):
    """(x0, y0, x1, y1) in EPSG:5070, padded and snapped to the 30 m
    grid - identical to download_tcc_nlcd.py's region_grid, so tiles
    and any future cross-checking share pixel edges with tcc/nlcd."""
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
    crs_transform pins the global 30 m grid so tiles merge exactly -
    same approach as download_tcc_nlcd.fetch_tile."""
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
    """Fetch every tile through fetch_fn(index) concurrently, same
    pattern as download_tcc_nlcd._fetch_all: on the first failure,
    queued tiles are cancelled before the error propagates."""
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


def build_raster(ee, image, band, bounds_lonlat, out_path, tile_m,
                 workers=8):
    single_band = image.select([band]).unmask(0).toFloat()
    x0, y0, x1, y1 = region_grid(bounds_lonlat)
    tile_list = list(tiles(x0, y0, x1, y1, tile_m))
    with tempfile.TemporaryDirectory() as td:
        paths = [os.path.join(td, f"t{i}.tif")
                 for i in range(len(tile_list))]
        _fetch_all(len(tile_list),
                   lambda i: fetch_tile(ee, single_band, tile_list[i],
                                       paths[i]),
                   workers, f"   {os.path.basename(out_path)}")
        srcs = [rasterio.open(p) for p in paths]
        try:
            mosaic, transform = rio_merge(srcs)
        finally:
            for s in srcs:
                s.close()
        arr = mosaic[0].astype(np.float32)
        # Defensive only: unmask(0) already handles non-forest, so a
        # negative value here would mean something upstream is wrong,
        # not a normal case. Clip rather than fail the whole region
        # over one bad pixel; the mean printed below makes a systemic
        # problem visible immediately.
        arr = np.clip(arr, 0, None)
        with rasterio.open(out_path, "w", driver="GTiff",
                           height=arr.shape[0], width=arr.shape[1],
                           count=1, dtype="float32", crs="EPSG:5070",
                           transform=transform, nodata=None,
                           compress="lzw", predictor=3, tiled=True) as dst:
            dst.write(arr, 1)
    nonzero = float((arr > 0).mean())
    print(f"   wrote {out_path} ({arr.shape[1]}x{arr.shape[0]} px, "
         f"{100 * nonzero:.1f}% forested, mean over forested "
         f"{arr[arr > 0].mean() if nonzero else 0:.1f})")


def out_filename(vintage, attr):
    """generate_treemap_features.find_source()'s exact naming: 2016
    omits the study-area element that 2020+ carries."""
    if vintage == 2016:
        return f"TreeMap{vintage}_{attr}.tif"
    return f"TreeMap{vintage}_CONUS_{attr}.tif"


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--regions", nargs="+", default=list(BOXES),
                    choices=list(BOXES))
    ap.add_argument("--vintages", nargs="+", type=int,
                    default=TREEMAP_VINTAGES, choices=TREEMAP_VINTAGES,
                    help="Default: %(default)s (every TreeMap vintage "
                         "currently in the Earth Engine catalog).")
    ap.add_argument("--attrs", nargs="+", default=ATTRS,
                    help="Default: %(default)s - the three attributes "
                         "generate_treemap_features.py needs. Only "
                         "change this if you are extending that script "
                         "to derive something new.")
    ap.add_argument("--project",
                    default=os.environ.get("EARTHENGINE_PROJECT"),
                    help="Google Cloud project for Earth Engine (or "
                         "set EARTHENGINE_PROJECT).")
    ap.add_argument("--out-dir", default=DEFAULT_OUT_DIR,
                    help="Where the raw per-attribute rasters are "
                         "written. Pass this same path to "
                         "generate_treemap_features.py --src-dir. "
                         "Default: %(default)s")
    ap.add_argument("--tile-m", type=int, default=96000,
                    help="Download tile edge in meters. Same default "
                         "as download_tcc_nlcd.py; shrink it if Earth "
                         "Engine returns a size-limit error for a "
                         "large region. Default: %(default)s")
    ap.add_argument("--workers", type=int, default=8,
                    help="Concurrent tile downloads. Default: %(default)s")
    ap.add_argument("--force", action="store_true",
                    help="Re-download files that already exist.")
    args = ap.parse_args()

    ee = ee_init(args.project)
    os.makedirs(args.out_dir, exist_ok=True)

    for vintage in args.vintages:
        print(f"\n{'=' * 60}\nTreeMap {vintage}\n{'=' * 60}")
        image, asset_id = resolve_vintage_image(ee, vintage)
        available = image.bandNames().getInfo()
        print(f"   asset: {asset_id} ({len(available)} bands)")
        resolved = {a: resolve_band(available, a) for a in args.attrs}

        for region in args.regions:
            print(f"   {region}:")
            for attr, band in resolved.items():
                out_path = os.path.join(args.out_dir,
                                        out_filename(vintage, attr))
                if os.path.exists(out_path) and not args.force:
                    print(f"      {out_path} exists - skipping "
                         f"(--force to redo).")
                    continue
                build_raster(ee, image, band, BOXES[region], out_path,
                            args.tile_m, workers=args.workers)

    print(f"\nDone. Next:\n"
         f"    python generate_treemap_features.py --src-dir "
         f"{args.out_dir}\n"
         f"Note: 2023 is not in this download (not yet in the Earth "
         f"Engine catalog) - generate_treemap_features.py will map "
         f"every raster year to the nearest of {TREEMAP_VINTAGES} "
         f"instead, same as it would with any missing vintage.")


if __name__ == "__main__":
    main()
