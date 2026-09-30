"""I6 cost: pooled positive count = own-state habitat rows, dedup on
(lon,lat,year), then one pooled 30 m thin using the live thinner."""
import time, resource, sys
import numpy as np, pandas as pd
sys.path.insert(0,"/home/ec2-user/grouse2")
from prepare_training_data import thin_by_min_distance
def rss(): return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024.0
t=time.perf_counter()
fr=[]
for r in ("ME","NH","VT"):
    d=pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv"); d["file_region"]=r; fr.append(d)
ev=pd.concat(fr,ignore_index=True)
print(f"load+pool evaluated: {1000*(time.perf_counter()-t):.0f} ms  rows={len(ev)}")
own = ev[ev["state"]==ev["file_region"]].copy()
hab = own[~own["nonveg_landcover"].astype(bool)].copy()
hab = hab.loc[~hab[["longitude","latitude","year"]].duplicated()].copy()
print(f"own-state {len(own)}  habitat {len(hab)} after (lon,lat,year) dedup")
for n_in, sub in (("full pooled habitat", hab),):
    t=time.perf_counter()
    kept = thin_by_min_distance(sub, 30.0, 42)
    dt=time.perf_counter()-t
    print(f"I6 thin_by_min_distance(30 m) on {len(sub)} -> {len(kept)} kept : "
          f"{dt:.1f}s  maxRSS {rss():.0f} MB")
# scaling probe: how the greedy thinner scales (rebuilds cKDTree per kept pt)
for n in (2000,4000,8000):
    s=hab.iloc[:n]
    t=time.perf_counter(); k=thin_by_min_distance(s,30.0,42)
    print(f"   n={n:5d} -> kept {len(k):5d}  {time.perf_counter()-t:6.2f}s")
