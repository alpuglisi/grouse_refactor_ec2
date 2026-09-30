import pandas as pd, numpy as np
from pyproj import Transformer
from scipy.spatial import cKDTree
import prepare_training_data as P
T=Transformer.from_crs("EPSG:4326","EPSG:5070",always_xy=True); R=["ME","NH","VT"]; B=30000.0
ev={r:pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv").assign(_reg=r) for r in R}
allrows=pd.concat(ev.values(),ignore_index=True)
own=allrows[allrows.state==allrows._reg].drop_duplicates(subset=['longitude','latitude'])
pos_all=P.thin_by_min_distance(own[~own['nonveg_landcover'].astype(bool)].copy(),30,42)
cand=pd.concat([pd.read_csv(f"data/negatives/gbif_negatives_{r}.csv") for r in R],ignore_index=True)
k=cand[['longitude','latitude']].round(5); cand=cand.loc[~k.duplicated()].copy()
cand['x_5070'],cand['y_5070']=T.transform(cand.longitude.values,cand.latitude.values)
gx,gy=T.transform(pos_all.longitude.values,pos_all.latitude.values)
d,_=cKDTree(np.c_[gx,gy]).query(cand[['x_5070','y_5070']].values,k=1)
cand=cand[d>300].copy()
print("region  fair (d) over 12 seeds: min / median / max")
for r in R:
    pos=pos_all[pos_all.state==r]; c=cand[cand.state==r]
    px,py=T.transform(pos.longitude.values,pos.latitude.values)
    posblk=set(zip(np.floor(px/B).astype(int),np.floor(py/B).astype(int)))
    vals=[]
    for s in range(12):
        sel=c.sample(n=min(len(pos),len(c)),random_state=s)
        nb=set(zip(np.floor(sel.x_5070.values/B).astype(int),np.floor(sel.y_5070.values/B).astype(int)))
        vals.append(len(posblk-nb)/len(posblk))
    print(f"  {r}: {min(vals):.4f} / {np.median(vals):.4f} / {max(vals):.4f}   (n_pos={len(pos)}, n_cand={len(c)}, pos blocks={len(posblk)})")
