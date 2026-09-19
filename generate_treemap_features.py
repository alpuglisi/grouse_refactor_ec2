"""
generate_treemap_features.py

Builds four stand-structure model features from USFS TreeMap, resampled
onto each region's own raster grid:

    balive      live tree basal area          ft2/acre
    tpa_live    live stems per acre           stems/acre  (log-encoded)
    qmd         quadratic mean diameter       inches      (DERIVED)
    carbon_dwn  carbon in down dead wood      tons/acre

WHY THESE FOUR
--------------
Nothing in the existing stack measures stem DENSITY or stem SIZE. It
measures cover three ways (evc, cc, tcc) and height two ways (evh, ch)
and type once (evt) - so a stand reading 60% canopy cover at 50ft could
be 80 large stems per acre or 2,000 saplings, and those are identical in
every feature the model currently sees. For an early-successional
obligate they are opposite habitats: grouse cover is dense small stems,
high tpa_live and low qmd, thick enough that a goshawk cannot fly
through it.

TreeMap carries ~24 attributes and this takes four, because most of the
rest are algebraically the same two numbers. QMD is exactly
sqrt(BALIVE / (0.005454 * TPA)); SDIsum, ALSTK, GSSTK, DRYBIO_L,
CARBON_L and VOLCFNET_L are all functions of basal area and mean size.
Twelve channels would buy about three independent dimensions on a model
that is already overfitting.

Deliberately NOT taken: CANOPYPCT and STANDHT. TreeMap is imputed FROM
LANDFIRE - EVC/EVH/EVT are its Random Forest predictors - and USFS
report 94.2% / 99.0% within-class agreement with the EVC/EVH already in
this stack. They are near-duplicate channels, not independent evidence.

QMD IS DERIVED, NOT DOWNLOADED
------------------------------
TreeMap publishes QMD only for 2020/2022/2023; the 2016 vintage ships
QMD_RMRS under a different definition. Downloading it would either open
a definitional seam across vintages or cost the 2016 vintage entirely.
models.qmd_from_balive_tpa applies the published USFS formula
(SQRT((BALIVE/TPA)/0.005454), verified against the rastergateway's own
query definition) uniformly to all four vintages instead - one
definition, no seam, and one fewer CONUS download.

WHAT TO BE SUSPICIOUS OF
------------------------
TreeMap assigns each forested pixel the statistically nearest FIA plot.
Two adjacent pixels can be assigned different plots and jump
discontinuously in every attribute at once, so fine-grained texture in
these bands is largely IMPUTATION ARTIFACT, not ground truth - and this
architecture is texture-sensitive (its strongest measured signals are
edge-magnitude correlations: evt +0.402, fdist -0.509). Worse, TreeMap
has no reference data for boundaries at all: only single-condition,
100%-forested FIA plots were eligible for imputation, so plots
straddling a stand boundary were excluded by construction. A TreeMap
"edge" is the imputation switching between two interior plots.

Hence --smooth: a median filter over the raw bands before encoding,
deliberately destroying detail that is not real. Default 3 (a 3x3, i.e.
90m). --smooth 0 disables it, which is the right setting only if you
intend to measure how much of the signal was artifact.

Non-forest is NoData in TreeMap and is written here as 0, not as a
nodata sentinel: a hayfield genuinely has zero basal area, zero stems
and zero down wood. qmd=0 is the one fudge, and it stays consistent -
qmd=0 AND tpa_live=0 is exactly the non-forest signature, so the joint
pattern carries forest/non-forest without a mask channel.

carbon_dwn is the weakest of the four and the first to drop: TreeMap's
metadata says it is "estimated from models based on geographic area,
forest type, and live tree carbon density", i.e. it is not measured
down wood, and both of those predictors are already in the stack.

SOURCE DATA
-----------
Per-attribute CONUS rasters, four vintages (2016, 2020, 2022, 2023):
    https://data.fs.usda.gov/geodata/rastergateway/treemap/index.php

The rastergateway serves these through an HTML <select>, and the option
values were NOT recoverable without a browser - so no download URL
template here is trustworthy and this script does not guess one by
default. Download BALIVE, TPA_LIVE and CARBON_DWN for the vintages you
want, unpack them anywhere, and point --src-dir at that directory; the
files are located by name, recursively. Note the 2016 naming differs:
    2016:            TreeMap2016_{ATTR}.tif
    2020/2022/2023:  TreeMap{year}_CONUS_{ATTR}.tif

The full RDS publications (2022 is RDS-2025-0032, ~4.5 GB) are the
alternative acquisition path and additionally contain the per-tree
table, which is where species-specific and small-stem densities would
come from if this ever goes further.

YEAR MATCHING
-------------
TreeMap has four vintages; this project's other features have their
own. Each of OUR vintage years is written from the NEAREST TreeMap year
(ties to the earlier one, matching grouse_data's year-matching policy).
That guarantees a file exists for every year the rest of the stack has,
which is what stops these features from shrinking the year-gap filter's
retention - the binding constraint stays LANDFIRE, as it already was.

Usage:
    python generate_treemap_features.py --src-dir /data/treemap
    python generate_treemap_features.py --src-dir /data/treemap --regions NH
    python generate_treemap_features.py --src-dir /data/treemap --smooth 0
"""
import os
import glob
import shutil
import argparse
import functools

import numpy as np
import rasterio
from rasterio.vrt import WarpedVRT
from rasterio.enums import Resampling
from rasterio.windows import Window
from scipy.ndimage import median_filter

from grouse_data import GrouseData
from models import (TREEMAP_FIXED, qmd_from_balive_tpa, tpa_live_encode,
                    treemap_encode)

TREEMAP_YEARS = [2016, 2020, 2022, 2023]
# Downloaded attributes. qmd is absent on purpose - it is derived.
SOURCE_ATTRS = ["BALIVE", "TPA_LIVE", "CARBON_DWN"]
# TreeMap's NoData is 4.2949673e+09 (R's default, ~2^32-1), which GDAL
# does not auto-detect, and the metadata attributes it to the plot
# table rather than explicitly to these per-attribute rasters. Anything
# at or above this threshold is treated as non-forest regardless of how
# the header declares it - no real basal area, stem count or down-wood
# tonnage comes within nine orders of magnitude of it.
NODATA_FLOOR = 1e9


def nearest_vintage(year, available):
    """Closest TreeMap vintage to one of our years; ties go to the
    EARLIER vintage, i.e. conditions that existed at sighting time."""
    return min(available, key=lambda v: (abs(v - year), v))


@functools.lru_cache(maxsize=None)
def _source_is_valid(path, min_valid_frac=0.001):
    """True if a candidate source file has REAL content, not just a
    path that exists. Catches an interrupted or failed download that
    left a zero-byte or truncated GeoTIFF on disk - the same class of
    failure grouse_data._is_valid_raster exists to catch for the
    model's own rasters, applied here to TreeMap's raw sources before
    anything reads them.

    Deliberately NOT an all-nodata test like that one:
    download_treemap.py writes non-forest as 0 with nodata=None (a
    real value, not a sentinel - see its docstring), so a raster with
    no nodata pixels at all is the NORMAL case here, not evidence of
    validity. Instead this checks for at least some NONZERO pixels - a
    state-sized clip with literally zero forested pixels anywhere is
    itself the failure signature (wrong bbox landed outside the
    region, an empty EE tile, a truncated partial read), not a
    plausible real outcome for ME/NH/VT. Cached per path: this can run
    dozens of times across discover_vintages and every write_vintage
    call for the same handful of underlying files."""
    try:
        if os.path.getsize(path) == 0:
            return False
        with rasterio.open(path) as src:
            # A decimated probe read, not the real data read - this
            # only needs to answer "is there any signal here at all",
            # and these are CONUS-scale clips.
            arr = src.read(1, out_shape=(1, min(src.height, 1024),
                                         min(src.width, 1024)))
            frac = float((arr > 0).mean()) if arr.size else 0.0
            return frac >= min_valid_frac
    except Exception:
        return False


def find_source(src_dir, vintage, attr, region=None):
    """Locate one attribute raster for one vintage.

    Tries, in order:
      1. A REGION-SPECIFIC clip - download_treemap.py's own naming
         (TreeMap{vintage}_{region}_{attr}.tif). Required first: that
         script downloads a separate clip per region rather than one
         CONUS-wide file, and two regions' files are NOT
         interchangeable - an earlier version of this pair of scripts
         had no region in the filename at all, so New Hampshire and
         Vermont silently "found" Maine's file (same name, already on
         disk) and would have been trained on Maine's TreeMap data.
      2. A CONUS-wide file, the USFS rastergateway's own naming for
         anyone who downloaded by hand instead of running
         download_treemap.py (no per-region subsetting is offered
         there, so one file legitimately serves every region). 2016
         omits the study-area element 2020+ carries, hence two
         spellings.

    A path that MATCHES the naming but fails _source_is_valid is
    treated as not found, not returned - existence alone was already
    proven insufficient once tonight (see the region-collision bug
    above); an empty or truncated file at the right name is the same
    class of silent failure with a different cause.
    """
    pats = []
    if region:
        pats.append(f"TreeMap{vintage}_{region}_{attr}.tif")
    pats += [f"TreeMap{vintage}_CONUS_{attr}.tif",
            f"TreeMap{vintage}_{attr}.tif"]
    for pat in pats:
        hits = sorted(glob.glob(os.path.join(src_dir, "**", pat),
                                recursive=True))
        for h in hits:
            if _source_is_valid(h):
                return h
        if hits:
            print(f"   [warn] {[os.path.basename(h) for h in hits]} "
                 f"matches TreeMap {vintage} {attr}"
                 f"{f' ({region})' if region else ''} by name, but has "
                 f"no real content (empty/corrupt/zero valid pixels) - "
                 f"treating as not found, not falling back to it.")
    return None


def discover_vintages(src_dir, regions):
    """Which TreeMap vintages have a COMPLETE set of the three source
    attributes for EVERY region being processed. A vintage present for
    some regions but missing for others is excluded ENTIRELY rather
    than silently run for a subset - the same rule this project's
    model already applies to its own feature list (discover_features
    intersects across regions; see ARCHITECTURE.md). Checked once,
    up front, so a missing file is a clear message here instead of a
    cryptic rasterio crash three functions deep during write_vintage.
    """
    ok = []
    for v in TREEMAP_YEARS:
        missing = [(region, a) for region in regions for a in SOURCE_ATTRS
                  if find_source(src_dir, v, a, region) is None]
        if missing:
            print(f"   [warn] TreeMap {v}: missing {missing} - "
                  f"skipping this vintage entirely.")
            continue
        ok.append(v)
    if not ok:
        raise SystemExit(
            f"No TreeMap vintage under {src_dir} has {SOURCE_ATTRS} for "
            f"every region in {regions}. Need at least one of "
            f"{TREEMAP_YEARS} complete for ALL requested regions.")
    print(f"   complete TreeMap vintages available (all regions): {ok}")
    return ok


def _clean(arr):
    """Raw band -> float64 with non-forest as 0.0."""
    a = np.asarray(arr, dtype=np.float64)
    a[~np.isfinite(a)] = 0.0
    a[a >= NODATA_FLOOR] = 0.0
    a[a < 0] = 0.0
    return a


def write_vintage(region, year, vintage, src_dir, ref_path, profile,
                  raster_dir, smooth, block_rows):
    """One region, one of OUR vintage years, from one TreeMap vintage."""
    with rasterio.open(ref_path) as ref:
        height, width = ref.height, ref.width
        ref_crs, ref_transform = ref.crs, ref.transform

    halo = smooth // 2
    srcs, vrts, outs = [], {}, {}
    totals = {}
    try:
        for attr in SOURCE_ATTRS:
            path = find_source(src_dir, vintage, attr, region)
            if path is None:
                raise SystemExit(
                    f"{region}: no {attr} source for TreeMap {vintage} "
                    f"under {src_dir} (checked region-specific and "
                    f"CONUS naming). discover_vintages should have "
                    f"caught this before we got here - report as a bug.")
            s = rasterio.open(path)
            srcs.append(s)
            # NEAREST, not bilinear: every TreeMap value is one imputed
            # plot's measurement, and interpolating across an imputation
            # boundary produces a number that corresponds to no plot at
            # all. Smoothing happens afterwards, on purpose and at a
            # stated radius, rather than as a resampling side effect.
            vrts[attr] = WarpedVRT(s, crs=ref_crs, transform=ref_transform,
                                   width=width, height=height,
                                   resampling=Resampling.nearest)
        for feat in ("balive", "tpa_live", "qmd", "carbon_dwn"):
            path = os.path.join(raster_dir, f"{region}_{year}_{feat}.tif")
            outs[feat] = rasterio.open(path, "w", **profile)
            totals[feat] = [0.0, 0]

        for r0 in range(0, height, block_rows):
            nrows = min(block_rows, height - r0)
            # Read with a halo so the median filter sees real neighbours
            # across block seams instead of edge-replicated ones, then
            # trim it back off before writing.
            hr0 = max(0, r0 - halo)
            hr1 = min(height, r0 + nrows + halo)
            hwin = Window(0, hr0, width, hr1 - hr0)
            raw = {a: _clean(vrts[a].read(1, window=hwin))
                   for a in SOURCE_ATTRS}

            # QMD from the RAW bands, before smoothing: this is the exact
            # per-pixel quantity, and smoothing it afterwards alongside
            # the others keeps all four as the same operation applied to
            # the same definition.
            bands = {
                "balive": raw["BALIVE"],
                "tpa_live": raw["TPA_LIVE"],
                "qmd": qmd_from_balive_tpa(raw["BALIVE"], raw["TPA_LIVE"]),
                "carbon_dwn": raw["CARBON_DWN"],
            }
            top = r0 - hr0
            for feat, band in bands.items():
                if smooth > 1:
                    band = median_filter(band, size=smooth, mode="nearest")
                band = band[top:top + nrows]
                if feat == "tpa_live":
                    enc = tpa_live_encode(band)
                else:
                    enc = treemap_encode(feat, band)
                outs[feat].write(enc, 1, window=Window(0, r0, width, nrows))
                totals[feat][0] += float(band.sum())
                totals[feat][1] += band.size
    finally:
        for o in outs.values():
            o.close()
        for v in vrts.values():
            v.close()
        for s in srcs:
            s.close()

    units = {"balive": "ft2/ac", "tpa_live": "stems/ac",
             "qmd": "in", "carbon_dwn": "t/ac"}
    means = ", ".join(
        f"{f} {totals[f][0] / max(totals[f][1], 1):.1f}{units[f]}"
        for f in ("balive", "tpa_live", "qmd", "carbon_dwn"))
    print(f"      {year} <- TreeMap {vintage}: mean over grid "
          f"(non-forest counted as 0) {means}")


def process_region(region, data, src_dir, vintages, smooth, block_rows):
    print(f"\n{'=' * 60}\n{region}\n{'=' * 60}")
    rd = data[region]
    derived = {"balive", "tpa_live", "qmd", "carbon_dwn"}
    others = [f for f in rd.available_features() if f not in derived]
    if not others:
        print(f"   [!] No rasters on disk for {region} - skipping.")
        return
    ref_path = rd.latest_raster_path(others[0])
    years = sorted({y for f in others for y in rd.raster_years(f)})
    print(f"   template grid: {os.path.basename(ref_path)}")
    mapping = {y: nearest_vintage(y, vintages) for y in years}
    print(f"   year -> TreeMap vintage: {mapping}")
    far = {y: v for y, v in mapping.items() if abs(y - v) > 2}
    if far:
        print(f"   [warn] {far} are more than 2 years from any TreeMap "
              f"vintage. Those rasters describe a landscape the sighting "
              f"year did not have; the year-gap filter will NOT catch it, "
              f"because a file exists for every year either way.")

    with rasterio.open(ref_path) as ref:
        profile = ref.profile.copy()
    profile.update(driver="GTiff", count=1, dtype="int16", nodata=-9999,
                   compress="deflate", predictor=2, tiled=True)

    raster_dir = data.config.resolve(data.config.raster_dir)
    # write_vintage's actual work - opening the three source rasters,
    # warping them onto THIS region's grid, the smoothing pass,
    # deriving QMD, encoding - depends only on (region, vintage). `year`
    # only names the output file. Several of our years can map to the
    # SAME vintage (e.g. 2016/2017/2018 -> TreeMap 2016), and re-running
    # the full pipeline for each one was producing byte-identical output
    # from scratch every time - up to 4x the actual work for no reason,
    # against 200-360MB source rasters. Compute once per vintage, copy
    # the result to every other year sharing it.
    by_vintage = {}
    for y in years:
        by_vintage.setdefault(mapping[y], []).append(y)
    for vintage in sorted(by_vintage):
        yrs = sorted(by_vintage[vintage])
        first_year = yrs[0]
        write_vintage(region, first_year, vintage, src_dir, ref_path,
                      profile, raster_dir, smooth, block_rows)
        for y in yrs[1:]:
            for feat in ("balive", "tpa_live", "qmd", "carbon_dwn"):
                shutil.copy2(
                    os.path.join(raster_dir, f"{region}_{first_year}_{feat}.tif"),
                    os.path.join(raster_dir, f"{region}_{y}_{feat}.tif"))
            print(f"      {y} <- copied from {first_year} (same "
                  f"TreeMap vintage {vintage}: byte-identical output, "
                  f"not re-derived)")


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src-dir", required=True,
                    help="Directory holding the downloaded TreeMap "
                         "per-attribute GeoTIFFs (searched recursively). "
                         f"Needs {SOURCE_ATTRS} for at least one vintage.")
    ap.add_argument("--regions", nargs="+", default=None,
                    help="Default: every region discovered on disk.")
    ap.add_argument("--smooth", type=int, default=3,
                    help="Median filter window in pixels applied before "
                         "encoding, to suppress imputation texture that "
                         "is artifact rather than ground truth. 0 or 1 "
                         "disables. Default: %(default)s (3x3 = 90m).")
    ap.add_argument("--block-rows", type=int, default=512,
                    help="Rows per streaming block. Default: %(default)s")
    args = ap.parse_args()

    print(f"TreeMap source: {args.src_dir}")
    print(f"Smoothing: {args.smooth}x{args.smooth} median"
          if args.smooth > 1 else "Smoothing: DISABLED")
    print(f"Encodings: tpa_live log1p; "
          + ", ".join(f"{f} x{s['mult']:g} ({s['unit']})"
                      for f, s in TREEMAP_FIXED.items()))
    data = GrouseData()
    regions = args.regions or data.discover_regions()
    vintages = discover_vintages(args.src_dir, regions)

    for region in regions:
        process_region(region, data, args.src_dir, vintages,
                       args.smooth, args.block_rows)
    print("\nDone. Remember: new features are a GEOMETRY change - "
          "train.py needs a cold start, and --resume/--init-from are "
          "invalid against any older checkpoint.")


if __name__ == "__main__":
    main()
