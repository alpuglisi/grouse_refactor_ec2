"""ATTACK: nothing in I1-I13 constrains positive-negative proximity.
If the 300 m buffer stays per-region (its current home) while `evaluated`
becomes state-clipped, negatives can sit next to FOREIGN-state positives."""
import pandas as pd, numpy as np
from pyproj import Transformer
from scipy.spatial import cKDTree
import prepare_training_data as P
T=Transformer.from_crs("EPSG:4326","EPSG:5070",always_xy=True); R=["ME","NH","VT"]
ev={r:pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv").assign(_reg=r) for r in R}
allrows=pd.concat(ev.values(),ignore_index=True)
own=allrows[allrows.state==allrows._reg].drop_duplicates(subset=['longitude','latitude'])
pos=P.thin_by_min_distance(own[~own['nonveg_landcover'].astype(bool)].copy(),30,42)
px,py=T.transform(pos.longitude.values,pos.latitude.values); pos_xy=np.c_[px,py]
tree_all=cKDTree(pos_xy)
print("post-partition pooled positives:",len(pos))
tot_in=0
for r in R:
    c=pd.read_csv(f"data/negatives/gbif_negatives_{r}.csv")
    k=c[['longitude','latitude']].round(5); c=c.loc[~k.duplicated()].copy()
    cx,cy=T.transform(c.longitude.values,c.latitude.values); cxy=np.c_[cx,cy]
    # per-region buffer against OWN-STATE positives only (the mistake)
    ownp=pos[pos.state==r]
    ox,oy=T.transform(ownp.longitude.values,ownp.latitude.values)
    d_own,_=cKDTree(np.c_[ox,oy]).query(cxy,k=1)
    surv=c[d_own>300]
    # of those survivors, how many are within 300 m of ANY pooled positive?
    sx,sy=T.transform(surv.longitude.values,surv.latitude.values)
    d_all,_=tree_all.query(np.c_[sx,sy],k=1)
    viol=int((d_all<=300).sum())
    tot_in+=viol
    print(f"  {r}: candidates {len(c)} -> per-region-buffer survivors {len(surv)}; "
          f"of those {viol} lie within 300 m of a FOREIGN-state positive (min dist {d_all.min():.1f} m)")
    # how many within 30 m == same pixel, opposite label
    print(f"      within 30 m of a foreign-state positive: {int((d_all<=30).sum())}")
print("TOTAL undetected positive/negative proximity violations available:",tot_in)
print("  (I1 is positives-only; I2/I3 are 3 km blocks; I10 is 30 km; none of I1-I13 measures this)")
