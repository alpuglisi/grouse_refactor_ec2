"""Decompose I5 cost: raster_path(validate=True) full-raster validation
vs the window predicate itself. READ-ONLY."""
import time, resource, sys
import numpy as np, pandas as pd, rasterio
from pyproj import Transformer
sys.path.insert(0, "/home/ec2-user/grouse2")
from grouse_data import GrouseData
from models import FEATURE_SPEC


def rss():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


regions = ["ME", "NH", "VT"]
data = GrouseData()
feats = sorted(set.intersection(
    *[set(data[r].available_features()) & set(FEATURE_SPEC) for r in regions]))
print("features:", len(feats), feats, flush=True)
YEARS_ALL = list(range(2016, 2025))
YEARS_POST = [y for y in YEARS_ALL if y >= 2020]

for label, years, validate in (
        ("resolve paths validate=FALSE, 9 years", YEARS_ALL, False),
        ("resolve paths validate=TRUE, 5 post-filter years", YEARS_POST, True),
        ("resolve paths validate=TRUE, 9 pre-filter years", YEARS_ALL, True)):
    data = GrouseData()          # fresh validity cache
    t = time.perf_counter()
    n = 0
    for r in regions:
        rd = data[r]
        for f in feats:
            for y in years:
                rd.raster_path(f, y, validate=validate)
                n += 1
    print(f"{label:52s} {time.perf_counter()-t:7.1f}s  {n} calls  "
          f"maxRSS {rss():.0f} MB", flush=True)

data = GrouseData()
paths = {}
for r in regions:
    for f in feats:
        for y in YEARS_ALL:
            paths[(r, f, y)] = data[r].raster_path(f, y, validate=False)
frames = {}
for r in regions:
    fr = [pd.read_csv(p)[["longitude", "latitude", "year"]] for p in
          (f"data/pipeline/train_positives_{r}.csv",
           f"data/pipeline/val_positives_{r}.csv",
           f"data/negatives/train_negatives_{r}.csv",
           f"data/negatives/val_negatives_{r}.csv")]
    d = pd.concat(fr, ignore_index=True)
    d["year"] = d["year"].fillna(2024).astype(int)
    frames[r] = d
t = time.perf_counter()
viol = {}
uniq = len(set(paths.values()))
for r in regions:
    d = frames[r]
    bad = np.zeros(len(d), bool)
    for f in feats:
        for y in sorted(d["year"].unique()):
            m = d["year"].values == y
            with rasterio.open(paths[(r, f, int(y))]) as src:
                tr = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
                xs, ys = tr.transform(d.loc[m, "longitude"].values,
                                      d.loc[m, "latitude"].values)
                fc, frr = (~src.transform) * (np.asarray(xs), np.asarray(ys))
                r0 = np.floor(frr).astype(np.int64) - 32
                c0 = np.floor(fc).astype(np.int64) - 32
                bad[m] |= ~((r0 >= 0) & (c0 >= 0)
                            & (r0 + 64 <= src.height) & (c0 + 64 <= src.width))
    viol[r] = int(bad.sum())
print(f"{'I5 window predicate ONLY (metadata reads)':52s} "
      f"{time.perf_counter()-t:7.1f}s  {uniq} distinct rasters  viol={viol}  "
      f"maxRSS {rss():.0f} MB", flush=True)
