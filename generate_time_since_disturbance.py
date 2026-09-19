"""
generate_time_since_disturbance.py

Builds the 'tsd' model feature: YEARS since the most recent recorded
disturbance, resampled onto each region's own raster grid and written
once per vintage year already present for that region.

WHY THIS FEATURE EXISTS
-----------------------
The strongest signal this model has ever measured is a disturbance
signal: fdist boundary density correlates -0.509 with suitability
(predict.py --tensorboard, Edge/ breakdown), twice the magnitude of any
canopy correlation. Ruffed grouse are an early-successional obligate -
the single most informative thing about a stand is how long ago it was
cut, burned or blown down.

But fdist is a CATEGORICAL embedding lookup. The network gets a
separate 16-d vector per code and no notion that they are ordered: it
cannot learn that the code meaning "3 years since" is nearer to "5
years since" than to "20 years since", because embedding indices carry
no metric. tsd supplies that ordered magnitude directly, and from 25
annual vintages (LANDFIRE Annual Disturbance, 1999-2023) rather than
the four fdist vintages on disk - so it resolves the 1-25 year window
at annual resolution instead of in composite bins.

The two are not redundant. fdist says WHAT happened (type, severity);
tsd says HOW LONG AGO, as a number the network can do arithmetic on.

WHY tsd IS RECOMPUTED PER VINTAGE, UNLIKE road_dist
---------------------------------------------------
road_dist writes byte-identical copies to every year because roads are
static. tsd is not: the clock keeps running. A stand cut in 2015 reads
7 years in the 2022 raster and 10 in the 2025 one with no new
disturbance at all. Each vintage year Y is computed from the
disturbance record up to and including Y - never later, or the feature
would leak the future into a sighting's landscape.

THE UNDISTURBED CAP
-------------------
Pixels with no recorded disturbance since 1999 encode to a FIXED
models.TSD_MAX_YEARS, not to "years since the record began". If the cap
grew with the vintage (24 in the 2022 raster, 27 in the 2025 one) then
the most common value in the entire feature would itself identify the
vintage, and a network with this much capacity will learn the year
rather than the habitat. Same failure mode this project already worried
about for a mixed-vintage fdist code space.

OUTPUT
------
data/landfire/{REGION}_{YEAR}_tsd.tif - int16, LOG-ENCODED as
round(log1p(years) * 1000); see models.tsd_encode. A grouse's use of a
stand changes enormously between 2 and 8 years post-cut and not at all
between 40 and 46, so linear years would spend most of the input range
resolving distinctions the species does not make.
models.tsd_decode inverts it for anything reporting years to a human.

SOURCE DATA
-----------
LANDFIRE Annual Disturbance, CONUS, one 30m raster per disturbance year:
    https://landfire.gov/data-downloads/AnnualDist/USAnnualDisturbance_1999_present.zip
~1.92 GB. Note the release year and the disturbance year are
INDEPENDENT in the filenames - LF2020_Dist17_CONUS is the 2017
disturbance year published in the 2020 release. This script parses the
Dist{yy} portion and ignores the LF{yyyy} prefix.

The final (Dist) series' upper year can move as LANDFIRE publishes new
releases (LF2024_Dist24_CONUS appeared alongside this project's other
LF2024 downloads) - this script reads whatever years are actually on
disk rather than assuming a fixed end year, and prints the range it
found. For anything past the newest Dist year, LANDFIRE publishes
Limited and Preliminary series; point --dist-dir at their extracted
contents too if you want those years covered by observation rather than
by the clock running on the last final year.

Usage:
    python generate_time_since_disturbance.py
    python generate_time_since_disturbance.py --regions NH
    python generate_time_since_disturbance.py --dist-dir /data/annual_dist
"""
import os
import re
import glob
import zipfile
import argparse
import urllib.request

import numpy as np
import rasterio
from rasterio.vrt import WarpedVRT
from rasterio.enums import Resampling
from rasterio.windows import Window

from grouse_data import GrouseData
from models import TSD_MAX_YEARS, tsd_encode

CACHE_DIR = "data/disturbance"
DIST_URL = ("https://landfire.gov/data-downloads/AnnualDist/"
            "USAnnualDisturbance_1999_present.zip")
# LF{release}_Dist{yy}_CONUS.tif - only the Dist{yy} half is the
# disturbance year. Two digits, so 99 is 1999 and everything else 20xx.
DIST_NAME_RE = re.compile(r"Dist(\d{2})", re.IGNORECASE)


def _dist_year(path):
    m = DIST_NAME_RE.search(os.path.basename(path))
    if not m:
        return None
    yy = int(m.group(1))
    return 1900 + yy if yy >= 90 else 2000 + yy


def _extract_nested_zips(dist_dir):
    """LANDFIRE's CONUS bundle is a zip OF zips: unpacking
    USAnnualDisturbance_1999_present.zip yields one
    LF{release}_Dist{yy}_CONUS.zip per disturbance year, each of which
    still has to be opened to reach the actual .tif - a single
    extractall() on the outer zip never sees the rasters at all, which
    is what produced 'No Dist{yy} rasters found' on a directory that
    plainly had them.

    Looped rather than one pass, in case a year's zip itself contains
    another zip (seen elsewhere in LANDFIRE's downloads); it stops as
    soon as a pass extracts nothing new. Each inner zip gets its own
    '.tif' marker so a second run does not re-extract 25 archives to
    discover there is nothing new to do."""
    for _ in range(4):
        pending = [p for p in glob.glob(
                       os.path.join(dist_dir, "**", "*.zip"), recursive=True)
                   if not os.path.exists(p + ".extracted")]
        if not pending:
            return
        for zp in pending:
            print(f"      extracting {os.path.basename(zp)} ...")
            out_dir = zp[:-len(".zip")]
            os.makedirs(out_dir, exist_ok=True)
            with zipfile.ZipFile(zp) as z:
                z.extractall(out_dir)
            open(zp + ".extracted", "w").close()


def fetch_disturbance(dist_dir):
    """Return {disturbance_year: tif_path}, downloading and extracting
    the CONUS bundle on first use unless --dist-dir already has it."""
    if dist_dir is None:
        dist_dir = CACHE_DIR
        os.makedirs(dist_dir, exist_ok=True)
        zpath = os.path.join(dist_dir, os.path.basename(DIST_URL))
        if not os.path.exists(zpath):
            print(f"   downloading {os.path.basename(zpath)} "
                  f"(~1.9 GB, one time) ...")
            urllib.request.urlretrieve(DIST_URL, zpath)
        marker = os.path.join(dist_dir, ".extracted")
        if not os.path.exists(marker):
            print("   extracting ...")
            with zipfile.ZipFile(zpath) as z:
                z.extractall(dist_dir)
            open(marker, "w").close()
    # Runs for an explicit --dist-dir too, not just the downloaded
    # default: pointing --dist-dir at a raw, un-extracted copy of the
    # bundle hits the exact same zip-of-zips problem. Idempotent and
    # cheap (one glob, no-op) once every inner zip has its marker, so
    # there is no cost to always checking rather than trying to guess
    # whether it is needed.
    _extract_nested_zips(dist_dir)

    found = {}
    for p in glob.glob(os.path.join(dist_dir, "**", "*.tif"),
                       recursive=True):
        y = _dist_year(p)
        if y is None:
            continue
        # Several LANDFIRE releases republish the same disturbance year.
        # Keep the newest release, which is the corrected one: sorting
        # by path puts LF2020_Dist17 after LF2016_Dist17.
        if y not in found or p > found[y]:
            found[y] = p
    if not found:
        raise SystemExit(
            f"No Dist{{yy}} rasters found under {dist_dir}. Extract the "
            f"Annual Disturbance bundle there, or pass --dist-dir.")
    print(f"   disturbance years found: {min(found)}-{max(found)} "
          f"({len(found)} rasters)")
    missing = [y for y in range(min(found), max(found) + 1)
               if y not in found]
    if missing:
        print(f"   [warn] gaps in the disturbance record: {missing} - "
              f"a stand disturbed in a missing year will read as older "
              f"than it is.")
    return found


def _report_codes(path):
    """Print the distinct values in one disturbance raster. This script
    treats 'value > 0 and not nodata' as disturbed; that assumption is
    worth eyeballing once against the real code set rather than
    trusting it silently."""
    with rasterio.open(path) as src:
        # A decimated read is enough to see the code vocabulary and
        # costs a fraction of the full-raster pass.
        arr = src.read(1, out_shape=(1, min(src.height, 2000),
                                     min(src.width, 2000)))
        vals, counts = np.unique(arr, return_counts=True)
    order = np.argsort(-counts)[:8]
    shown = ", ".join(f"{vals[i]}x{counts[i]:,}" for i in order)
    print(f"   sample codes in {os.path.basename(path)}: {shown}")
    print(f"   (treating value > 0 and != nodata as 'disturbed')")


def process_region(region, data, dist_paths, block_rows):
    print(f"\n{'=' * 60}\n{region}\n{'=' * 60}")
    rd = data[region]
    others = [f for f in rd.available_features() if f != "tsd"]
    if not others:
        print(f"   [!] No rasters on disk for {region} - skipping.")
        return
    template = rd.latest_raster_path(others[0])
    # Union across every feature, same reasoning as generate_road_distance:
    # nlcd/tcc reach back further than evt/evh/evc, and a sighting year
    # that resolves for those should resolve for tsd too.
    years = sorted({y for f in others for y in rd.raster_years(f)})
    print(f"   template grid: {os.path.basename(template)}")
    print(f"   years to write: {years}")

    usable = {d: p for d, p in dist_paths.items() if d <= max(years)}
    if not usable:
        print(f"   [!] No disturbance years at or before {max(years)} - "
              f"skipping.")
        return

    with rasterio.open(template) as ref:
        profile = ref.profile.copy()
        profile.update(driver="GTiff", count=1, dtype="int16",
                       nodata=-9999, compress="deflate", predictor=2,
                       tiled=True)
        height, width = ref.height, ref.width
        ref_crs, ref_transform = ref.crs, ref.transform

    raster_dir = data.config.resolve(data.config.raster_dir)
    # TreeMap and the disturbance bundle are on the LANDFIRE CONUS grid;
    # these regions are LFPS clips in a per-request LOCAL Albers (see
    # dataset.py's CRS note). WarpedVRT does the reprojection lazily so
    # each windowed read below pulls only the rows it needs. NEAREST
    # because disturbance codes are categorical at this stage - the
    # continuous quantity is derived afterwards, from the years.
    srcs, vrts = [], {}
    outs = {}
    try:
        for d, p in sorted(usable.items()):
            s = rasterio.open(p)
            srcs.append(s)
            vrts[d] = WarpedVRT(s, crs=ref_crs, transform=ref_transform,
                                width=width, height=height,
                                resampling=Resampling.nearest)
        for y in years:
            path = os.path.join(raster_dir, f"{region}_{y}_tsd.tif")
            outs[y] = rasterio.open(path, "w", **profile)

        stats = {y: [] for y in years}
        for r0 in range(0, height, block_rows):
            nrows = min(block_rows, height - r0)
            win = Window(0, r0, width, nrows)
            # -1 = never disturbed within the record.
            last = np.full((nrows, width), -1, dtype=np.int16)
            ti = 0
            targets = years
            for d in sorted(vrts):
                while ti < len(targets) and targets[ti] < d:
                    stats[targets[ti]].append(
                        _emit(outs[targets[ti]], targets[ti], last, win))
                    ti += 1
                v = vrts[d]
                arr = v.read(1, window=win)
                hit = arr > 0
                if v.nodata is not None:
                    hit &= arr != v.nodata
                last[hit] = d
            while ti < len(targets):
                stats[targets[ti]].append(
                    _emit(outs[targets[ti]], targets[ti], last, win))
                ti += 1
    finally:
        for o in outs.values():
            o.close()
        for v in vrts.values():
            v.close()
        for s in srcs:
            s.close()

    for y in years:
        tot = float(sum(n for n, _ in stats[y]))
        dist_px = float(sum(n * f for n, f in stats[y]))
        print(f"      {region}_{y}_tsd.tif: "
              f"{100.0 * dist_px / max(tot, 1):.1f}% of pixels carry a "
              f"disturbance within {TSD_MAX_YEARS}y of {y}")


def _emit(dst, year, last, win):
    """Write one stripe of one vintage. Returns (pixels, disturbed_frac)
    so the caller can report coverage without a second pass."""
    years_since = np.where(last >= 0, year - last, TSD_MAX_YEARS)
    dst.write(tsd_encode(years_since), 1, window=win)
    known = last >= 0
    return years_since.size, float(known.mean())


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--regions", nargs="+", default=None,
                    help="Default: every region discovered on disk.")
    ap.add_argument("--dist-dir", default=None,
                    help="Directory of already-extracted Annual "
                         "Disturbance rasters. Default: download and "
                         "extract into data/disturbance/.")
    ap.add_argument("--block-rows", type=int, default=512,
                    help="Rows per streaming block. Peak memory is "
                         "roughly block_rows * width * 2 bytes per open "
                         "disturbance year; lower it if a large state "
                         "runs out. Default: %(default)s")
    args = ap.parse_args()

    print("Fetching LANDFIRE Annual Disturbance ...")
    dist_paths = fetch_disturbance(args.dist_dir)
    _report_codes(dist_paths[max(dist_paths)])

    data = GrouseData()
    regions = args.regions or data.discover_regions()
    for region in regions:
        process_region(region, data, dist_paths, args.block_rows)
    print("\nDone. Remember: a new feature is a GEOMETRY change - "
          "train.py needs a cold start, and --resume/--init-from are "
          "invalid against any older checkpoint.")


if __name__ == "__main__":
    main()
