"""
realign_rasters.py

Puts every feature raster of a region onto ONE pixel grid - the region's
template grid (its latest EVT clip, the same template road_dist, tsd
and the TreeMap features are already written on).

WHY
---
The training reader (dataset.py) cuts each feature's 64x64 window from
that feature's OWN raster grid. That only produces co-registered
channels when every raster shares one grid. tcc and nlcd were written
by download_tcc_nlcd.py in EPSG:5070, while the LANDFIRE clips (and
everything derived from them) sit in the LFPS per-request local Albers.
The two grids are rotated relative to each other by the difference in
meridian convergence: measured on the training box, 11 px of corner
misregistration between an nlcd window and the evt window for the same
point. Every training patch carried tcc and nlcd rotated against the
other thirteen channels; predict.py warps onto one grid, so the model
was deployed on inputs it never trained on. Validation is built by the
same reader, so no metric could show it.

WHAT IT DOES
------------
For each region and each feature raster on disk, compares the raster
to the template with grouse_data.grid_mismatch (same CRS, same pixel
size, coincident pixel edges; extent may differ). Files that fail are
warped onto the template's exact grid with NEAREST resampling (these
are categorical codes and integer-encoded quantities - interpolating
them would invent values). NOTHING IS OVERWRITTEN: the original file is
moved, unchanged, into a backup directory (default
data/landfire/unaligned/, outside every discovery glob) before the
realigned raster is written at the original path. Files that pass are
left untouched. Dry run by default; --apply writes.

The patch cache keys on raster modification times, so it rebuilds
itself on the next training run. The model must then be retrained from
scratch: a checkpoint trained on rotated channels is not the same
function as one trained on aligned ones.

Usage:
    python realign_rasters.py                # report only
    python realign_rasters.py --apply
    python realign_rasters.py --apply --regions NH --features tcc nlcd
    python realign_rasters.py --apply --backup-dir /somewhere/else
"""
import argparse
import glob
import os
import re
import shutil

import rasterio
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT
from rasterio.windows import Window

from grouse_data import GrouseData, RASTER_FEATURES, grid_mismatch

# Features that define the template rather than follow it: the LANDFIRE
# clips. The template is the latest EVT; the others are checked too and
# would be realigned if LFPS ever changed a clip's projection between
# requests, which is the right outcome.
TEMPLATE_FEATURE = "evt"


def warp_to_grid(src_path, ref_path, out_path, block_rows=1024):
    """Resample `src_path` onto `ref_path`'s exact grid (CRS, transform,
    width, height) with nearest-neighbour, streaming by row blocks, and
    write it to `out_path` atomically (temp file + os.replace). Nodata
    is carried over (-9999 when the source declares none). Refuses to
    write over its own input - callers that want the result at the
    source path move the source aside first (see realign_file)."""
    if os.path.abspath(src_path) == os.path.abspath(out_path):
        raise ValueError(f"warp_to_grid would overwrite its input "
                         f"{src_path}; move the source aside first.")
    tmp = out_path + f".tmp{os.getpid()}"
    with rasterio.open(ref_path) as ref, rasterio.open(src_path) as src:
        nodata = src.nodata if src.nodata is not None else -9999
        dtype = src.dtypes[0]
        profile = dict(driver="GTiff", height=ref.height, width=ref.width,
                       count=1, dtype=dtype, crs=ref.crs,
                       transform=ref.transform, nodata=nodata,
                       compress="deflate", tiled=True,
                       predictor=3 if dtype.startswith("float") else 2)
        with WarpedVRT(src, crs=ref.crs, transform=ref.transform,
                       width=ref.width, height=ref.height,
                       resampling=Resampling.nearest,
                       src_nodata=nodata, nodata=nodata) as vrt, \
                rasterio.open(tmp, "w", **profile) as dst:
            for r0 in range(0, ref.height, block_rows):
                win = Window(0, r0, ref.width,
                             min(block_rows, ref.height - r0))
                dst.write(vrt.read(1, window=win), 1, window=win)
    os.replace(tmp, out_path)


def realign_file(path, template, backup_dir, block_rows=1024):
    """Move the unaligned original to backup_dir (same basename, never
    overwriting an earlier backup), then write the realigned raster at
    the original path from that moved copy. The original bytes are
    never modified or deleted."""
    os.makedirs(backup_dir, exist_ok=True)
    backup = os.path.join(backup_dir, os.path.basename(path))
    if os.path.exists(backup):
        raise SystemExit(
            f"{backup} already exists - refusing to overwrite an earlier "
            f"backup. Move it aside or pass a different --backup-dir.")
    shutil.move(path, backup)
    try:
        warp_to_grid(backup, template, path, block_rows)
    except BaseException:
        # Put the original back rather than leave the feature missing.
        if not os.path.exists(path):
            shutil.move(backup, path)
        raise
    return backup


def region_files(raster_dir, region, features):
    pat = re.compile(rf"^{region}_(\d{{4}})_([a-z_]+)\.tif$")
    out = []
    for p in sorted(glob.glob(os.path.join(raster_dir, f"{region}_*.tif"))):
        m = pat.match(os.path.basename(p))
        if m and m.group(2) in features:
            out.append((int(m.group(1)), m.group(2), p))
    return out


def process_region(region, data, features, apply, block_rows,
                   backup_dir):
    print(f"\n{'=' * 60}\n{region}\n{'=' * 60}")
    rd = data[region]
    if not rd.raster_years(TEMPLATE_FEATURE):
        print(f"   [!] no {TEMPLATE_FEATURE} raster for {region} - no "
              f"template grid to align to; skipping.")
        return 0, 0
    template = rd.latest_raster_path(TEMPLATE_FEATURE)
    raster_dir = data.config.resolve(data.config.raster_dir)
    print(f"   template grid: {os.path.basename(template)}")
    n_ok = n_bad = 0
    with rasterio.open(template) as ref:
        for year, feat, path in region_files(raster_dir, region, features):
            if os.path.abspath(path) == os.path.abspath(template):
                continue
            with rasterio.open(path) as src:
                why = grid_mismatch(src, ref)
            if why is None:
                n_ok += 1
                continue
            n_bad += 1
            print(f"   {os.path.basename(path):28s} {why}")
            if apply:
                backup = realign_file(path, template, backup_dir, block_rows)
                with rasterio.open(path) as chk:
                    left = grid_mismatch(chk, ref)
                print(f"      -> realigned; original kept at {backup}"
                      + (f"  [!] STILL MISMATCHED: {left}" if left else ""))
    print(f"   {n_ok} on the template grid, {n_bad} "
          f"{'realigned' if apply else 'NOT on it (dry run - use --apply)'}")
    return n_ok, n_bad


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--regions", nargs="+", default=None,
                    help="Default: every region discovered on disk.")
    ap.add_argument("--features", nargs="+", default=RASTER_FEATURES,
                    help="Default: every feature in RASTER_FEATURES.")
    ap.add_argument("--apply", action="store_true",
                    help="Rewrite mismatched files in place. Default: "
                         "report only.")
    ap.add_argument("--block-rows", type=int, default=1024)
    ap.add_argument("--backup-dir", default=None,
                    help="Where the unaligned originals are moved before "
                         "the realigned files are written. Default: "
                         "<raster dir>/unaligned/ - a subdirectory, so "
                         "the discovery globs never pick the originals "
                         "up as features. Never overwritten.")
    args = ap.parse_args()

    data = GrouseData()
    regions = args.regions or data.discover_regions()
    backup_dir = args.backup_dir or os.path.join(
        data.config.resolve(data.config.raster_dir), "unaligned")
    total_bad = 0
    for region in regions:
        _, bad = process_region(region, data, args.features, args.apply,
                                args.block_rows, backup_dir)
        total_bad += bad
    if args.apply and total_bad:
        print(f"\nRealigned {total_bad} file(s); originals kept under "
              f"{backup_dir}. The patch cache under "
              f"data/cache rebuilds itself (its key includes raster "
              f"mtimes). Retrain from scratch - a checkpoint trained on "
              f"the old, rotated channels is not valid for the aligned "
              f"ones.")
    elif total_bad:
        print(f"\n{total_bad} file(s) are not on their region's template "
              f"grid. Re-run with --apply to fix them.")
    else:
        print("\nEvery raster is on its region's template grid.")


if __name__ == "__main__":
    main()
