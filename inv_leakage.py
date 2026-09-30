"""Step 8 of INVESTIGATION_PLAN_errol_map.md: cross-region train/val
leakage count (BUG-0027). Read-only; writes nothing but stdout."""
import numpy as np, pandas as pd
from pyproj import Transformer
from scipy.spatial import cKDTree
from grouse_data import GrouseData

REGIONS, BLOCK_M, NEAR_M = ["ME", "NH", "VT"], 3000, (30, 300, 3000)
data = GrouseData()
rows = []
for reg in REGIONS:
    rd = data[reg]
    for kind, get in (("pos", rd.positives), ("neg", rd.negatives)):
        for split in ("train", "val"):
            df = get(split)[["longitude", "latitude"]].copy()
            df["region"], df["kind"], df["split"] = reg, kind, split
            rows.append(df)
allr = pd.concat(rows, ignore_index=True)
x, y = Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True).transform(
    allr.longitude.values, allr.latitude.values)
allr["x"], allr["y"] = x, y
allr["key"] = allr.longitude.round(5).astype(str) + "," + allr.latitude.round(5).astype(str)
print(allr.groupby(["region", "kind", "split"]).size().unstack(), "\n")

# 1. The same coordinate in more than one region
multi = allr.groupby(["kind", "key"]).region.nunique()
for kind in ("pos", "neg"):
    m = multi.loc[kind]
    print(f"{kind}: {int((m > 1).sum()):,} coordinates appear in >1 region "
          f"({(m > 1).mean():.1%} of {len(m):,} unique)")

# 2. The same coordinate as TRAIN in one region and VAL in another
for kind in ("pos", "neg"):
    k = allr[allr.kind == kind]
    tr = set(k[k.split == "train"].key); va = set(k[k.split == "val"].key)
    both = tr & va
    print(f"{kind}: {len(both):,} coordinates are TRAIN and VAL at once "
          f"({len(both) / max(len(va), 1):.1%} of val coordinates)")

# 3. Pooled proximity
for kind in ("pos", "neg"):
    k = allr[allr.kind == kind]
    tr, va = k[k.split == "train"], k[k.split == "val"]
    d_pool, _ = cKDTree(tr[["x", "y"]].values).query(va[["x", "y"]].values, k=1)
    d_own = np.full(len(va), np.inf)
    for reg in REGIONS:
        t, v = tr[tr.region == reg], va.region.values == reg
        if len(t) and v.any():
            d_own[v], _ = cKDTree(t[["x", "y"]].values).query(va[v][["x", "y"]].values, k=1)
    for d in NEAR_M:
        print(f"{kind}: val with a TRAIN point within {d:>4} m - pooled "
              f"{(d_pool <= d).mean():6.1%} | same-region only {(d_own <= d).mean():6.1%}")
