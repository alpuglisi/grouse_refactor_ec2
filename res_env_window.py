"""RESEARCH (read-only): CR-0007 s5 drops candidates lacking a full
img_size + 2*jitter (= 64 px) window in EVERY feature raster they would be
read from.  That drop is NOT in the faithful pool, so measure how many of the
22,201 pooled candidates it removes, per region — it is the one pool-shrinking
step a clean rebuild adds that the envelopes here do not model."""
import numpy as np, pandas as pd, rasterio
from pyproj import Transformer
from models import FEATURE_SPEC
from grouse_data import GrouseData
import inv_formalC_lib as L
import res_env_core as K

HALF = 32          # img_size 64, jitter 0 -> 32 px each side
P, C = K.load_all()
data = GrouseData()
YEARS = sorted(set(int(y) for y in C.year.dropna().unique())
               | set(int(y) for y in P.year.dropna().unique()))
print("years present:", YEARS)
for label, D in (("candidates", C), ("positives", P)):
    print(f"\n--- {label} ---")
    tot_bad = 0
    for r in L.R:
        sub = D[D.state == r]
        bad = np.zeros(len(sub), dtype=bool)
        rd = data[r]
        for f in FEATURE_SPEC:
            paths = {}
            for y in sorted(set(int(v) for v in sub.year.dropna().unique())):
                try:
                    paths[y] = rd.raster_path(f, y)
                except Exception:
                    paths[y] = None
            for y, pth in paths.items():
                if pth is None:
                    continue
                m = (sub.year.values == y)
                if not m.any():
                    continue
                with rasterio.open(pth) as s:
                    tf = Transformer.from_crs("EPSG:4326", s.crs, always_xy=True)
                    xs, ys = tf.transform(sub.loc[m, 'longitude'].values,
                                          sub.loc[m, 'latitude'].values)
                    rows, cols = rasterio.transform.rowcol(s.transform, xs, ys)
                    rows = np.asarray(rows); cols = np.asarray(cols)
                    oob = ((rows - HALF < 0) | (cols - HALF < 0)
                           | (rows + HALF > s.height) | (cols + HALF > s.width))
                    idx = np.where(m)[0]
                    bad[idx[oob]] = True
        print(f"  {r}: {int(bad.sum())} of {len(sub)} lack a full 64 px window "
              f"in some FEATURE_SPEC raster ({100*bad.mean():.2f}%)")
        tot_bad += int(bad.sum())
        if label == "candidates":
            sub2 = sub[~bad]
            print(f"       -> {r} pool {len(sub)} -> {len(sub2)}")
    print(f"  total dropped: {tot_bad}")
