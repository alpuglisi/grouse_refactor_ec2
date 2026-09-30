"""(1) Which records fail I5 today, and what year are they?  Does the
    pre-filter vs post-filter placement change I5's answer?
(2) I18's under-specified record set: pooled vs per-region readings.
READ-ONLY."""
import time, sys
import numpy as np, pandas as pd, rasterio
from pyproj import Transformer
from scipy.spatial import cKDTree
sys.path.insert(0, "/home/ec2-user/grouse2")
from grouse_data import GrouseData
from models import FEATURE_SPEC

regions = ["ME", "NH", "VT"]
data = GrouseData()
feats = sorted(set.intersection(
    *[set(data[r].available_features()) & set(FEATURE_SPEC) for r in regions]))

t = time.perf_counter()
paths = {}
for r in regions:
    for f in feats:
        for y in range(2016, 2025):
            paths[(r, f, y)] = data[r].raster_path(f, y, validate=False)
print(f"path resolution validate=False: {time.perf_counter()-t:.2f}s")

rows = []
for r in regions:
    for cls, sp, p in (("pos", "train", f"data/pipeline/train_positives_{r}.csv"),
                       ("pos", "val",   f"data/pipeline/val_positives_{r}.csv"),
                       ("neg", "train", f"data/negatives/train_negatives_{r}.csv"),
                       ("neg", "val",   f"data/negatives/val_negatives_{r}.csv")):
        d = pd.read_csv(p)[["longitude", "latitude", "year"]]
        d["cls"], d["split"], d["region"] = cls, sp, r
        rows.append(d)
A = pd.concat(rows, ignore_index=True)
A["year"] = A["year"].fillna(2024).astype(int)

t = time.perf_counter()
A["i5_bad"] = False
A["bad_feats"] = ""
for r in regions:
    sel = A.region.values == r
    for f in feats:
        for y in sorted(A.loc[sel, "year"].unique()):
            m = sel & (A.year.values == int(y))
            if not m.any():
                continue
            with rasterio.open(paths[(r, f, int(y))]) as src:
                tr = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
                xs, ys = tr.transform(A.loc[m, "longitude"].values,
                                      A.loc[m, "latitude"].values)
                fc, frr = (~src.transform) * (np.asarray(xs), np.asarray(ys))
                r0 = np.floor(frr).astype(np.int64) - 32
                c0 = np.floor(fc).astype(np.int64) - 32
                ok = ((r0 >= 0) & (c0 >= 0) & (r0 + 64 <= src.height)
                      & (c0 + 64 <= src.width))
                idx = np.where(m)[0][~ok]
                A.loc[A.index[idx], "i5_bad"] = True
                for i in idx:
                    A.at[A.index[i], "bad_feats"] = (
                        A.at[A.index[i], "bad_feats"] + f + " ")
print(f"I5 window predicate only (paths pre-resolved, validate=False): "
      f"{time.perf_counter()-t:.1f}s")
bad = A[A.i5_bad]
print(f"I5 violations total {len(bad)}")
print(bad[["region", "cls", "split", "year", "longitude", "latitude",
           "bad_feats"]].to_string())
print("\nI5 pre-filter (all years) violations per region:",
      bad.groupby("region").size().to_dict())
print("I5 post-filter (year >= 2020) violations per region:",
      bad[bad.year >= 2020].groupby("region").size().to_dict())

# ---- I18 record set ambiguity ----
tr5070 = Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True)
A["X"], A["Y"] = tr5070.transform(A.longitude.values, A.latitude.values)
P = A[A.cls == "pos"]
tree = cKDTree(np.c_[P.loc[P.split == "train", "X"], P.loc[P.split == "train", "Y"]])
d, _ = tree.query(np.c_[P.loc[P.split == "val", "X"], P.loc[P.split == "val", "Y"]])
print(f"\nI18 POOLED positives median val->nearest-train = {np.median(d)/1000:.3f} km")
for r in regions:
    Q = P[P.region == r]
    tt = cKDTree(np.c_[Q.loc[Q.split == "train", "X"], Q.loc[Q.split == "train", "Y"]])
    dd, _ = tt.query(np.c_[Q.loc[Q.split == "val", "X"], Q.loc[Q.split == "val", "Y"]])
    print(f"I18 PER-REGION {r}: {np.median(dd)/1000:.3f} km")
