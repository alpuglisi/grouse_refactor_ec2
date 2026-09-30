# save as scan_codes.py in the project directory and run: python scan_codes.py
import glob, os, sys
import numpy as np
import rasterio

FULL = os.environ.get("FULL") == "1"
FEATURES = ["evc", "evh", "sclass", "evt", "fdist", "nlcd"]
paths = sorted(glob.glob("data/landfire/*_*_*.tif"))
for feat in FEATURES:
    print(f"\n=== {feat} ===")
    for p in paths:
        if not p.endswith(f"_{feat}.tif"):
            continue
        with rasterio.open(p) as src:
            if FULL:
                a = src.read(1)
            else:
                a = src.read(1, out_shape=(1, max(1, src.height // 8),
                                           max(1, src.width // 8)))[0]
            nd = src.nodata
            valid = a[(a != nd) if nd is not None else np.ones(a.shape, bool)]
            valid = valid[valid > -1000]
            hi = valid[valid >= 300]
            codes, counts = np.unique(hi, return_counts=True)
            print(f"{os.path.basename(p):28s} nodata={nd} "
                  f"min={valid.min() if valid.size else None} "
                  f"max={valid.max() if valid.size else None} "
                  f"pixels>=300: {hi.size}/{valid.size} "
                  f"({100.0 * hi.size / max(valid.size, 1):.2f}%)"
                  f"{'  (decimated 8x)' if not FULL else ''}")
            if codes.size:
                print("    codes>=300:", ", ".join(
                    f"{int(c)}x{int(n)}" for c, n in zip(codes, counts)))
