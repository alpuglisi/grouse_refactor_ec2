"""
scan_codes.py

Data-integrity check for the categorical rasters: per feature, per
region and vintage, the code range actually present on disk and how
much of the raster sits at or above each feature's FEATURE_SPEC vocab.
GrouseResNet.embed clamps codes into [0, vocab-1], so anything reported
under "clamped" is being merged into one embedding index and losing its
meaning - the failure that hid LANDFIRE's herbaceous block (EVC 310-399,
EVH 301-310) behind the old vocab of 300 (see CHANGELOG.md, 2026-09-20).

Reads at 1/8 resolution by default (a few seconds per state); FULL=1
reads every pixel for exact fractions.

    python scan_codes.py
    FULL=1 python scan_codes.py
    python scan_codes.py --features evc evh
"""
import argparse
import glob
import os

import numpy as np
import rasterio

from grouse_data import DataConfig, NODATA_SENTINELS
from models import FEATURE_SPEC


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", nargs="+",
                    default=[f for f, s in FEATURE_SPEC.items()
                             if s["kind"] == "categorical"])
    ap.add_argument("--decimate", type=int,
                    default=1 if os.environ.get("FULL") == "1" else 8)
    args = ap.parse_args()
    raster_dir = DataConfig().resolve(DataConfig().raster_dir)
    for feat in args.features:
        vocab = int(FEATURE_SPEC[feat]["vocab"])
        print(f"\n=== {feat} (vocab {vocab}) ===")
        for p in sorted(glob.glob(os.path.join(raster_dir, f"*_*_{feat}.tif"))):
            with rasterio.open(p) as src:
                d = max(1, args.decimate)
                # 2-D out_shape for a single band: (rows, cols). A 3-D
                # shape here silently returns (1, rows, cols) and the
                # first draft of this script then took row 0 only.
                a = src.read(1, out_shape=(max(1, src.height // d),
                                           max(1, src.width // d)))
                nd = src.nodata
            valid = a[~np.isin(a, list(NODATA_SENTINELS))]
            if nd is not None:
                valid = valid[valid != nd]
            if valid.size == 0:
                print(f"{os.path.basename(p):26s} nodata={nd}  no valid pixels")
                continue
            over = valid[valid >= vocab]
            hi = valid[valid >= 300]
            print(f"{os.path.basename(p):26s} nodata={nd} "
                  f"min={int(valid.min())} max={int(valid.max())} "
                  f"valid={valid.size:,} | >=300: {hi.size:,} "
                  f"({100.0 * hi.size / valid.size:.2f}%) | clamped "
                  f"(>={vocab}): {over.size:,} "
                  f"({100.0 * over.size / valid.size:.2f}%)"
                  f"{'' if d == 1 else f'  (decimated {d}x)'}")
            if hi.size and feat in ("evc", "evh"):
                codes, counts = np.unique(hi, return_counts=True)
                print("    codes>=300:", ", ".join(
                    f"{int(c)}x{int(n)}" for c, n in zip(codes, counts)))


if __name__ == "__main__":
    main()
