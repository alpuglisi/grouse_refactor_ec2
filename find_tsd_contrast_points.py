"""
find_tsd_contrast_points.py

Finds two real, contrasting points to run inspect_point.py against, to
check whether the 'tsd' feature actually varies - the check that came
out of the flat/uniform Patches/tsd tile in TensorBoard.

Rather than guess coordinates, this reads the ACTUAL tsd raster for a
region and finds:
  - the pixel with the SMALLEST decoded tsd (most recently disturbed)
  - a pixel at/near TSD_MAX_YEARS (long-undisturbed / the cap value)

excluding the -9999 nodata sentinel, and prints ready-to-paste
inspect_point.py commands for both. If tsd is genuinely constant across
the whole region, this will print the same value for both and that IS
the answer - a real finding, not a coincidence of which two points got
picked.

FIRST RUN'S RESULT AND WHY THIS VERSION EXISTS
------------------------------------------------
The first version only excluded tsd's OWN nodata pixels. On NH it
picked two points that both landed on row=0 (the raster's top edge)
where nlcd, sclass and all four TreeMap features read as entirely
zero/padding across the whole 64x64 window - a coverage gap at the
clip boundary, not a tsd problem, but it made the two inspect_point.py
scores an unfair comparison (half the feature stack was degenerate at
both points, not just tsd differing).

This version excludes two more things before searching:
  1. A border margin of IMG_SIZE//2 pixels on every side. A point
     inside the margin has its own 64x64 read window run off the edge
     of the raster, which read_window_stack pads with 0 fill - so even
     a point with a genuinely valid CENTER pixel can have a partially
     fake surrounding window.
  2. Pixels where nlcd reads as 0 (padding/nodata - real Anderson
     classes start at 11) once warped onto tsd's own grid. nlcd is a
     reliable, always-populated-where-real proxy for "this location has
     actual data coverage," cheaper than checking every feature.

Usage:
    python find_tsd_contrast_points.py --region NH
"""
import argparse

import numpy as np
import rasterio
from rasterio.vrt import WarpedVRT
from rasterio.enums import Resampling
from pyproj import Transformer

from grouse_data import GrouseData
from models import tsd_decode, TSD_MAX_YEARS
from predict import IMG_SIZE


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--region", default="NH")
    ap.add_argument("--model", default="grouse_single_best.pth",
                    help="Passed through to the printed inspect_point.py "
                         "commands. Default: %(default)s")
    ap.add_argument("--margin", type=int, default=IMG_SIZE // 2,
                    help="Border pixels excluded on every side, so the "
                         "picked point's own read window can't run off "
                         "the raster edge. Default: %(default)s "
                         "(IMG_SIZE//2).")
    args = ap.parse_args()

    data = GrouseData()
    rd = data[args.region]
    tsd_path = rd.latest_raster_path("tsd")
    print(f"Reading {tsd_path} ...")

    with rasterio.open(tsd_path) as src:
        arr = src.read(1)
        nodata = src.nodata
        transform = src.transform
        crs = src.crs
        height, width = src.height, src.width

    valid = arr != nodata if nodata is not None else np.ones_like(arr, dtype=bool)

    # --- margin: exclude a border strip so the picked point's own
    # 64x64 read window can't run off the raster edge into fill-padding. ---
    m = args.margin
    if m > 0:
        border = np.zeros_like(valid)
        border[m:height - m, m:width - m] = True
        valid &= border
        print(f"   excluding a {m}px border: {valid.sum():,} pixels "
             f"remain of {arr.size:,}")

    # --- coverage gate: nlcd must be a REAL class (not the 0 padding
    # value), warped onto tsd's own grid. ---
    nlcd_years = rd.raster_years("nlcd")
    if nlcd_years:
        nlcd_path = rd.raster_path("nlcd", max(nlcd_years))
        with rasterio.open(nlcd_path) as nsrc:
            if (nsrc.crs == crs and nsrc.transform == transform
                    and nsrc.shape == (height, width)):
                nlcd_arr = nsrc.read(1)
            else:
                with WarpedVRT(nsrc, crs=crs, transform=transform,
                               width=width, height=height,
                               resampling=Resampling.nearest) as vrt:
                    nlcd_arr = vrt.read(1)
        has_coverage = nlcd_arr != 0
        before = valid.sum()
        valid &= has_coverage
        print(f"   excluding nlcd=0 (padding, not a real class): "
             f"{valid.sum():,} pixels remain (dropped {before - valid.sum():,})")
    else:
        print("   [warn] no nlcd raster found for this region - "
             "skipping the coverage gate, margin exclusion only.")

    if not valid.any():
        raise SystemExit(
            "No pixels pass both the margin and coverage checks. Try "
            "--margin 0, or check that nlcd actually covers this region.")

    decoded_full = np.full(arr.shape, np.nan)
    decoded_full[valid] = tsd_decode(arr[valid].astype(np.float64))
    years = decoded_full[valid]
    print(f"   {valid.sum():,} candidate pixels. Decoded years: "
         f"min={years.min():.2f}  max={years.max():.2f}  "
         f"mean={years.mean():.2f}  unique values={len(np.unique(np.round(years, 2)))}")

    if years.max() - years.min() < 0.5:
        print(f"\n[!] tsd is (near-)CONSTANT across the valid/covered "
             f"area of {args.region}: every candidate pixel decodes to "
             f"~{years.mean():.1f} years. That would explain the flat "
             f"Patches/tsd tile directly - this is not a sampling "
             f"coincidence, the feature has no spatial variation to "
             f"show here. Worth checking generate_time_since_"
             f"disturbance.py's output for this region rather than "
             f"just re-running inspect_point.py.")

    min_idx = np.unravel_index(np.nanargmin(decoded_full), decoded_full.shape)
    min_year = decoded_full[min_idx]
    dist_from_cap = np.abs(decoded_full - TSD_MAX_YEARS)
    max_idx = np.unravel_index(np.nanargmin(dist_from_cap), dist_from_cap.shape)
    max_year = decoded_full[max_idx]

    to_lonlat = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)

    def point_cmd(row, col, label, years_val):
        x, y = rasterio.transform.xy(transform, row, col)
        lon, lat = to_lonlat.transform(x, y)
        print(f"\n{label}: tsd decodes to {years_val:.1f} years "
             f"(row={row}, col={col})")
        print(f"   python inspect_point.py --region {args.region} "
             f"--lon {lon:.6f} --lat {lat:.6f} --model {args.model}")

    point_cmd(*min_idx, "Most recently disturbed pixel found", min_year)
    point_cmd(*max_idx, "Longest-undisturbed pixel found (at/near cap)", max_year)

    print("\nBoth points now have real nlcd coverage and aren't within "
         f"{m}px of the raster edge, so the comparison should isolate "
         "tsd's difference rather than a coverage gap. Run both "
         "commands and check whether the OTHER features (nlcd, sclass, "
         "balive, etc.) look like plausible real values this time, not "
         "another wall of zeros.")


if __name__ == "__main__":
    main()
