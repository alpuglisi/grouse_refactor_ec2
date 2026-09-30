"""How cheap can the I5 window predicate get?  READ-ONLY."""
import os, time, sys
os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("GDAL_PAM_ENABLED", "NO")
import numpy as np, pandas as pd, rasterio
from pyproj import Transformer
sys.path.insert(0, "/home/ec2-user/grouse2")
from grouse_data import GrouseData
from models import FEATURE_SPEC

regions = ["ME", "NH", "VT"]
data = GrouseData()
feats = sorted(set.intersection(
    *[set(data[r].available_features()) & set(FEATURE_SPEC) for r in regions]))

PATHS=GEOM=TRS=None
for tag, years in (("PRE-filter years 2016-2024", list(range(2016, 2025))),
                   ("POST-filter years 2020-2024", list(range(2020, 2025)))):
    t = time.perf_counter()
    paths = {}
    for r in regions:
        for f in feats:
            for y in years:
                paths[(r, f, y)] = data[r].raster_path(f, y, validate=False)
    tp = time.perf_counter() - t
    files = sorted(set(paths.values()))
    t = time.perf_counter()
    geom = {}
    for p in files:
        with rasterio.open(p) as s:
            geom[p] = (s.crs, s.transform, s.width, s.height)
    to = time.perf_counter() - t
    t = time.perf_counter()
    trs = {}
    for crs in {g[0] for g in geom.values()}:
        trs[crs] = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    ttr = time.perf_counter() - t
    print(f"{tag}: paths {tp:.2f}s | open {len(files)} distinct rasters "
          f"{to:.2f}s | {len(trs)} distinct CRS, transformers {ttr:.2f}s",
          flush=True)
    PATHS, GEOM, TRS = paths, geom, trs

# the predicate itself, geometry already in hand
rows = []
for r in regions:
    for p in (f"data/pipeline/train_positives_{r}.csv",
              f"data/pipeline/val_positives_{r}.csv",
              f"data/negatives/train_negatives_{r}.csv",
              f"data/negatives/val_negatives_{r}.csv"):
        d = pd.read_csv(p)[["longitude", "latitude", "year"]]
        d["region"] = r
        rows.append(d)
A = pd.concat(rows, ignore_index=True)
A["year"] = A["year"].fillna(2024).astype(int)
t = time.perf_counter()
bad = np.zeros(len(A), bool)
for r in regions:
    sel = A.region.values == r
    for f in feats:
        for y in sorted(A.loc[sel, "year"].unique()):
            m = sel & (A.year.values == int(y))
            pth = data[r].raster_path(f, int(y), validate=False)
            if pth not in GEOM:
                with rasterio.open(pth) as s2:
                    GEOM[pth] = (s2.crs, s2.transform, s2.width, s2.height)
            crs, tf, w, h = GEOM[pth]
            if crs not in TRS:
                TRS[crs] = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
            xs, ys = TRS[crs].transform(A.loc[m, "longitude"].values,
                                        A.loc[m, "latitude"].values)
            fc, fr = (~tf) * (np.asarray(xs), np.asarray(ys))
            r0 = np.floor(fr).astype(np.int64) - 32
            c0 = np.floor(fc).astype(np.int64) - 32
            bad[m] |= ~((r0 >= 0) & (c0 >= 0) & (r0 + 64 <= h) & (c0 + 64 <= w))
print(f"predicate arithmetic only (geometry cached): "
      f"{1000*(time.perf_counter()-t):.0f} ms  violations={int(bad.sum())}")
