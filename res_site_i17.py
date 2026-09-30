"""I17 cost + footing: per-record extraction of the 9 continuous
FEATURE_SPEC features for the pooled positives, then max two-sample KS
between val and train.

Two footings are compared:
  FIXED  -- one vintage (2022) for every record: what inv_formalA_i17.py
            (the script that calibrated the 0.095 gate) actually measured.
  PER-REC-- each record's own resolved vintage: what the datasets read.
READ-ONLY -- nothing is written into data/.
"""
import time, resource, sys
import numpy as np, pandas as pd, rasterio
from pyproj import Transformer
from scipy.stats import ks_2samp
sys.path.insert(0, "/home/ec2-user/grouse2")
from grouse_data import GrouseData
from models import FEATURE_SPEC, split_features


def rss():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


regions = ["ME", "NH", "VT"]
data = GrouseData()
avail = sorted(set.intersection(
    *[set(data[r].available_features()) & set(FEATURE_SPEC) for r in regions]))
cat_f, cont_f = split_features(avail)
print(f"continuous FEATURE_SPEC on disk: {len(cont_f)} {cont_f}", flush=True)

fr = []
for r in regions:
    for sp, p in (("train", f"data/pipeline/train_positives_{r}.csv"),
                  ("val", f"data/pipeline/val_positives_{r}.csv")):
        d = pd.read_csv(p)[["longitude", "latitude", "year"]]
        d["split"], d["region"] = sp, r
        fr.append(d)
pos = pd.concat(fr, ignore_index=True)
pos["year"] = pos["year"].fillna(2024).astype(int)
print(f"pooled positives: {len(pos)}  years {sorted(pos.year.unique())}",
      flush=True)

t = time.perf_counter()
paths = {}
for r in regions:
    for f in cont_f:
        for y in list(range(2016, 2025)) + [2022]:
            paths[(r, f, y)] = data[r].raster_path(f, y, validate=False)
print(f"path resolution (validate=False): {time.perf_counter()-t:.2f}s  "
      f"{len(paths)} entries  distinct files {len(set(paths.values()))}",
      flush=True)


def extract(year_of):
    vals = {f: np.full(len(pos), np.nan) for f in cont_f}
    n_open = 0
    for r in regions:
        for f in cont_f:
            for y in sorted(set(year_of[pos.region.values == r])):
                m = (pos.region.values == r) & (year_of == y)
                if not m.any():
                    continue
                with rasterio.open(paths[(r, f, int(y))]) as src:
                    n_open += 1
                    tr = Transformer.from_crs("EPSG:4326", src.crs,
                                              always_xy=True)
                    xs, ys = tr.transform(pos.loc[m, "longitude"].values,
                                          pos.loc[m, "latitude"].values)
                    v = np.array([s[0] for s in src.sample(zip(xs, ys))],
                                 dtype=np.float64)
                    if src.nodata is not None:
                        v[v == src.nodata] = np.nan
                    v[v <= -9990] = np.nan
                    vals[f][m] = v
    return vals, n_open


def ks_max(vals):
    trm = pos.split.values == "train"
    vam = pos.split.values == "val"
    out = {}
    for f in cont_f:
        a = vals[f][trm]
        b = vals[f][vam]
        a = a[np.isfinite(a)]
        b = b[np.isfinite(b)]
        out[f] = float(ks_2samp(a, b).statistic) if len(a) and len(b) else np.nan
    return out


for label, yo in (("FIXED vintage 2022",
                   np.full(len(pos), 2022, dtype=np.int64)),
                  ("PER-RECORD vintage", pos.year.values.astype(np.int64))):
    t = time.perf_counter()
    vals, n_open = extract(yo)
    dt = time.perf_counter() - t
    ks = ks_max(vals)
    print(f"\n{label}: extraction {dt:.1f}s  {n_open} raster opens  "
          f"{len(pos)*len(cont_f)} point-samples  maxRSS {rss():.0f} MB",
          flush=True)
    for f in cont_f:
        print(f"    KS {f:12s} {ks[f]:.4f}")
    print(f"    ks_feat_max = {max(ks.values()):.4f}   (CR gate <= 0.095)")
