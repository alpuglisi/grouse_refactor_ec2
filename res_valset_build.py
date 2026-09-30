"""Build the CR-0007 pooled positive base set exactly as the CR specifies:
habitat positives whose `state` == filing region, pooled, deduped on
(lon,lat), thinned ONCE at 30 m with the real
prepare_training_data.thin_by_min_distance, 3 km blocks on the global
EPSG:5070 origin (0,0).  Writes a scratch parquet for reuse.  READ-ONLY
with respect to the project tree.
"""
import sys, os
import numpy as np, pandas as pd
sys.path.insert(0, "/home/ec2-user/grouse2")
os.chdir("/home/ec2-user/grouse2")
import prepare_training_data as P
from regions import BOXES

OUT = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad/base.csv"
R = ["ME", "NH", "VT"]
SZ = 3000.0

ev = {r: pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv").assign(_reg=r) for r in R}
a = pd.concat([ev[r] for r in R], ignore_index=True)
print("raw pooled rows:", len(a))
own = a[(~a['nonveg_landcover'].astype(bool)) & (a.state == a._reg)]
print("habitat & state==region:", len(own))
own = own.drop_duplicates(subset=['longitude', 'latitude'])
print("deduped on (lon,lat):", len(own))
base = P.thin_by_min_distance(own, 30, 42).reset_index(drop=True)
print("after one pooled 30 m thin:", len(base), "(CR I6 expects 6,230 +/- 2%)")
base['bx'] = np.floor(base.x_5070 / SZ).astype(int)
base['by'] = np.floor(base.y_5070 / SZ).astype(int)
base['blk'] = base.bx.astype(str) + "_" + base.by.astype(str)
print("occupied 3 km blocks:", base.blk.nunique())
print(base.groupby('state').size())
# blocks holding records from more than one state -- the stratification hazard
mix = base.groupby('blk')['state'].nunique()
print("blocks with records from >1 state:", int((mix > 1).sum()),
      " records in them:", int(base.blk.isin(mix[mix > 1].index).sum()))
for r in R:
    print(f"  {r}: blocks {base[base.state==r].blk.nunique()}")
base.to_csv(OUT, index=False)
print("wrote", OUT)
