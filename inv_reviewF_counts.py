import pandas as pd, numpy as np, glob
from pyproj import Transformer
from scipy.spatial import cKDTree
R=["ME","NH","VT"]
def rd(p): return pd.read_csv(p)
tp={r:rd(f"data/pipeline/thinned_positives_{r}.csv") for r in R}
trp={r:rd(f"data/pipeline/train_positives_{r}.csv") for r in R}
vap={r:rd(f"data/pipeline/val_positives_{r}.csv") for r in R}
ev={r:rd(f"data/pipeline/evaluated_sightings_{r}.csv") for r in R}
ng={r:rd(f"data/negatives/negatives_{r}.csv") for r in R}
trn={r:rd(f"data/negatives/train_negatives_{r}.csv") for r in R}
van={r:rd(f"data/negatives/val_negatives_{r}.csv") for r in R}
print("region  eval  eval_habitat  thinned  train  val   neg  trneg  vaneg")
for r in R:
    hab = ev[r][~ev[r]['nonveg_landcover'].astype(bool)]
    print(f"{r:6} {len(ev[r]):5} {len(hab):12} {len(tp[r]):8} {len(trp[r]):6} {len(vap[r]):4} {len(ng[r]):5} {len(trn[r]):6} {len(van[r]):6}")
tot_ev=sum(len(ev[r]) for r in R); tot_hab=sum(len(ev[r][~ev[r]['nonveg_landcover'].astype(bool)]) for r in R)
print("TOTAL eval rows", tot_ev, " habitat rows", tot_hab)
print("TOTAL thinned", sum(len(tp[r]) for r in R), "train", sum(len(trp[r]) for r in R), "val", sum(len(vap[r]) for r in R))
print("TOTAL neg", sum(len(ng[r]) for r in R), "trneg", sum(len(trn[r]) for r in R), "vaneg", sum(len(van[r]) for r in R))
# unique coords over habitat rows
allhab = pd.concat([ev[r][~ev[r]['nonveg_landcover'].astype(bool)].assign(_reg=r) for r in R], ignore_index=True)
k = allhab['longitude'].round(6).astype(str)+","+allhab['latitude'].round(6).astype(str)
allhab['_k']=k
print("habitat unique coords (6dp):", allhab['_k'].nunique())
for d in (5,7):
    kk = allhab['longitude'].round(d).astype(str)+","+allhab['latitude'].round(d).astype(str)
    print(f"  unique at {d}dp:", kk.nunique())
g = allhab.groupby('_k')['_reg'].nunique()
print("unique coords in >1 region file:", int((g>1).sum()))
# only in a foreign region file
own = allhab.groupby('_k').apply(lambda d: bool((d['state']==d['_reg']).any()), include_groups=False)
print("unique coords appearing ONLY in a foreign region file (state!=reg everywhere):", int((~own).sum()))
print("habitat rows whose filing region != state:", int((allhab['state']!=allhab['_reg']).sum()))
