"""
check_raster_health.py

Directly inspects specific raster files to confirm whether they're
corrupted, empty, or have broken georeferencing - versus a sampling-code
bug. Prompted by background_envelope_sample reporting 0/20,000 valid
samples for the 2025 EVH/EVT rasters in all three states, while every
other feature/year sampled fine.

Usage:
    python check_raster_health.py
    python check_raster_health.py --files landfire_data/ME_2025_evh.tif
"""
import argparse
import os

import numpy as np
import rasterio


def check_one(path):
    print(f"\n{path}")
    if not os.path.exists(path):
        print("  [!] FILE DOES NOT EXIST")
        return
    size = os.path.getsize(path)
    print(f"  size: {size:,} bytes"
         + ("  [!] SUSPICIOUSLY SMALL" if size < 10_000 else ""))
    try:
        with rasterio.open(path) as src:
            print(f"  crs: {src.crs}")
            print(f"  bounds: {src.bounds}")
            print(f"  shape: {src.width} x {src.height}, dtype: {src.dtypes[0]}, "
                 f"nodata: {src.nodata}")
            data = src.read(1)
            total = data.size
            if src.nodata is not None:
                n_nodata = int((data == src.nodata).sum())
            else:
                n_nodata = 0
            n_valid = total - n_nodata
            pct_valid = 100 * n_valid / total if total else 0
            print(f"  pixels: {total:,} total, {n_valid:,} non-nodata "
                 f"({pct_valid:.1f}%)")
            if pct_valid < 1:
                print("  [!] RASTER IS EFFECTIVELY EMPTY (>99% nodata) - "
                     "corrupted or a failed/placeholder download")
            if src.crs is None:
                print("  [!] NO CRS DEFINED - this alone would make every "
                     "point sample fail (lon/lat can't be transformed "
                     "into the raster's space)")
            u = np.unique(data)
            print(f"  sample of distinct values present: {u[:10]}"
                 + (" ..." if len(u) > 10 else ""))
    except Exception as e:
        print(f"  [!] COULD NOT OPEN: {e}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--files", nargs="+", default=None,
                        help="Specific files to check. Default: the "
                             "2025 evh/evt files for ME/NH/VT that "
                             "background_envelope_sample flagged.")
    args = parser.parse_args()

    if args.files:
        targets = args.files
    else:
        targets = [f"data/landfire/{region}_2025_{feat}.tif"
                  for region in ("ME", "NH", "VT")
                  for feat in ("evh", "evt")]
        # Also grab one known-good file (sclass 2024) as a working control
        # for comparison - if it looks structurally different from the
        # broken files, that confirms what "healthy" should look like.
        targets.append("data/landfire/ME_2024_sclass.tif")

    for path in targets:
        check_one(path)


if __name__ == "__main__":
    main()

