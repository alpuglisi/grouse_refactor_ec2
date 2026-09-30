"""Resolve a contradiction between reviewers A and B on the 30 km
occupied-block support check. A measured PER REGION and reported clean
separation; B measured POOLED and reported none. Read-only."""
import numpy as np, pandas as pd
from pyproj import Transformer
from grouse_data import GrouseData
R = ["ME", "NH", "VT"]
data = GrouseData()
t = Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True)

def blocks(df, size):
    x, y = t.transform(df.longitude.values, df.latitude.values)
    return set(zip((np.floor(x/size)).astype(int), (np.floor(y/size)).astype(int)))

def stats(pos, neg, size):
    P, N = blocks(pos, size), blocks(neg, size)
    return (len(P & N)/max(len(P | N),1), len(P - N)/max(len(P),1))

# CURRENT: region files as they are on disk (defective, box-clipped positives)
cur = {r: (data[r].thinned, data[r].negatives("all")) for r in R}
# POST-FIX: positives re-partitioned by the `state` column; negatives unchanged
allpos = pd.concat([data[r].thinned.assign(src=r) for r in R], ignore_index=True)
allpos = allpos.drop_duplicates(subset=["longitude","latitude"])
fix = {r: (allpos[allpos.state == r], data[r].negatives("all")) for r in R}

for size in (3000, 10000, 30000):
    print(f"\n=== block size {size//1000} km ===")
    print(f"{'scope':10s} {'jaccard cur':>12s} {'jacc fix':>9s} "
          f"{'pos-only cur':>13s} {'pos-only fix':>13s}")
    for r in R:
        jc, pc = stats(*cur[r], size); jf, pf = stats(*fix[r], size)
        print(f"{r:10s} {jc:12.3f} {jf:9.3f} {pc:13.3f} {pf:13.3f}")
    pc_all = pd.concat([cur[r][0] for r in R]); nc_all = pd.concat([cur[r][1] for r in R])
    pf_all = pd.concat([fix[r][0] for r in R]); nf_all = pd.concat([fix[r][1] for r in R])
    jc, pc = stats(pc_all, nc_all, size); jf, pf = stats(pf_all, nf_all, size)
    print(f"{'POOLED':10s} {jc:12.3f} {jf:9.3f} {pc:13.3f} {pf:13.3f}")
