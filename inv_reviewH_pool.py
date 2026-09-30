"""Build the pooled positive set CR-0007 specifies (I6 recipe) and check I6."""
import numpy as np, pandas as pd
from prepare_training_data import thin_by_min_distance
fr=[]
for r in ("ME","NH","VT"):
    d=pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv")
    d["filed"]=r
    fr.append(d[d["state"]==r])
p=pd.concat(fr,ignore_index=True)
print("own-state rows pooled:",len(p))
h=p[~p["nonveg_landcover"].astype(bool)].copy()
print("after habitat filter :",len(h),"   (CR: 6,411)")
d2=h.drop_duplicates(subset=["longitude","latitude","year"])
print("after (lon,lat,year) dedup:",len(d2))
for seed in (42,):
    t=thin_by_min_distance(d2.reset_index(drop=True),30,seed)
    print(f"after pooled 30m thin (seed {seed}): {len(t)}   (CR I6: 6,230 +-2%)")
t=thin_by_min_distance(d2.reset_index(drop=True),30,42)
t.to_csv("inv_reviewH_pooled_positives.csv",index=False)
print("per-region (state) counts:",t["state"].value_counts().to_dict(),
      "   (CR Corrections: ME 3,659 NH 1,079 VT 1,492)")
# also the withdrawn wrong recipe, for the record
allh=p if False else None
p2=[]
for r in ("ME","NH","VT"):
    d=pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv"); p2.append(d)
q=pd.concat(p2,ignore_index=True)
qh=q[~q["nonveg_landcover"].astype(bool)]
qu=qh.drop_duplicates(subset=["longitude","latitude"])
print("\nwithdrawn recipe: 8,422 habitat rows ->",len(qu),
      "unique coords -> thin:",len(thin_by_min_distance(qu.reset_index(drop=True),30,42)),
      "  (CR calls ~6,508 the wrong-grid diagnostic)")
