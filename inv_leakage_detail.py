"""Step 8 detail: which region pairs, and how many rows are affected."""
import numpy as np, pandas as pd, itertools
from grouse_data import GrouseData
REGIONS = ["ME", "NH", "VT"]
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
allr["key"] = allr.longitude.round(5).astype(str) + "," + allr.latitude.round(5).astype(str)
p = allr[allr.kind == "pos"]
print("pooled positive rows:", len(p), " unique coords:", p.key.nunique())
g = p.groupby("key").region.agg(lambda s: tuple(sorted(set(s))))
print("\ncoordinate membership by region set (unique coords):")
print(g.value_counts().to_string())
# rows affected by train+val collision
tr = set(p[p.split=="train"].key); va = set(p[p.split=="val"].key); both = tr & va
print(f"\ncolliding coords: {len(both)}")
print("val ROWS whose coord is also a pooled train coord:",
      int(p[(p.split=='val')].key.isin(both).sum()), "of", int((p.split=='val').sum()))
sub = p[p.key.isin(both)]
print("\ncollision coords, region+split combos:")
print(sub.groupby("key").apply(lambda d: tuple(sorted(zip(d.region, d.split))), include_groups=False).value_counts().head(12).to_string())
