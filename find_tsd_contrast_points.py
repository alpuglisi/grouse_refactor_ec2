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

Usage:
    python find_tsd_contrast_points.py --region NH
"""
import argparse

import numpy as np
import rasterio
from pyproj import Transformer

from grouse_data import GrouseData
from models import tsd_decode, TSD_MAX_YEARS


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--region", default="NH")
    ap.add_argument("--model", default="grouse_single_best.pth",
                    help="Passed through to the printed inspect_point.py "
                         "commands. Default: %(default)s")
    args = ap.parse_args()

    data = GrouseData()
    rd = data[args.region]
    path = rd.latest_raster_path("tsd")
    print(f"Reading {path} ...")

    with rasterio.open(path) as src:
        arr = src.read(1)
        nodata = src.nodata
        transform = src.transform
        crs = src.crs

    valid = arr != nodata if nodata is not None else np.ones_like(arr, dtype=bool)
    if not valid.any():
        raise SystemExit("Every pixel is nodata - can't pick points from this raster.")

    years = tsd_decode(arr[valid].astype(np.float64))
    print(f"   {valid.sum():,} valid pixels. Decoded years: "
         f"min={years.min():.2f}  max={years.max():.2f}  "
         f"mean={years.mean():.2f}  unique values={len(np.unique(np.round(years, 2)))}")

    if years.max() - years.min() < 0.5:
        print(f"\n[!] tsd is (near-)CONSTANT across all of {args.region}: "
             f"every valid pixel decodes to ~{years.mean():.1f} years. "
             f"That would explain the flat Patches/tsd tile directly - "
             f"this is not a sampling coincidence, the feature has no "
             f"spatial variation to show. Worth checking "
             f"generate_time_since_disturbance.py's output for this "
             f"region rather than just re-running inspect_point.py.")

    decoded_full = np.full(arr.shape, np.nan)
    decoded_full[valid] = tsd_decode(arr[valid].astype(np.float64))

    # Most recently disturbed: smallest decoded year, excluding a literal
    # 0 unless that's genuinely the minimum (0 = disturbed in the same
    # year as the raster's own vintage).
    min_idx = np.unravel_index(np.nanargmin(decoded_full), decoded_full.shape)
    min_year = decoded_full[min_idx]

    # Longest-undisturbed: closest to the fixed cap.
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

    print("\nRun both commands. If the reported tsd years differ "
         "meaningfully between them, the feature has real signal and "
         "the flat TensorBoard tile was just this validation batch's "
         "sampling. If they come back the same (or inspect_point.py "
         "itself errors), that points at a real generation bug.")


if __name__ == "__main__":
    main()
