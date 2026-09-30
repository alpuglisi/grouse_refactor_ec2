"""ATTACK 4 (post-partition footing): can a negative draw pass (d)<=0.15
while systematically displacing negatives from positives?"""
import pandas as pd, numpy as np
from pyproj import Transformer
from scipy.spatial import cKDTree
import prepare_training_data as P
T=Transformer.from_crs("EPSG:4326","EPSG:5070",always_xy=True)
R=["ME","NH","VT"]; B=30000.0
ev={r:pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv").assign(_reg=r) for r in R}
allrows=pd.concat(ev.values(),ignore_index=True)
own=allrows[allrows.state==allrows._reg].drop_duplicates(subset=['longitude','latitude'])
hab=own[~own['nonveg_landcover'].astype(bool)].copy()
pos_all=P.thin_by_min_distance(hab,30,42)
cand_all=pd.concat([pd.read_csv(f"data/negatives/gbif_negatives_{r}.csv") for r in R],ignore_index=True)
k=cand_all[['longitude','latitude']].round(5); cand_all=cand_all.loc[~k.duplicated()].copy()
cand_all['x_5070'],cand_all['y_5070']=T.transform(cand_all.longitude.values,cand_all.latitude.values)
#SKIPPED for speed
gx,gy=T.transform(pos_all.longitude.values,pos_all.latitude.values)
dd,_=cKDTree(np.c_[gx,gy]).query(cand_all[['x_5070','y_5070']].values,k=1)
cand_all=cand_all[dd>300].copy()
print("post-partition pooled positives",len(pos_all),"eligible candidates",len(cand_all))
for r in R:
    pos=pos_all[pos_all.state==r]
    cand=cand_all[cand_all.state==r].copy()
    px,py=T.transform(pos.longitude.values,pos.latitude.values)
    pbx,pby=np.floor(px/B).astype(int),np.floor(py/B).astype(int); posblk=set(zip(pbx,pby))
    cbx,cby=np.floor(cand.x_5070.values/B).astype(int),np.floor(cand.y_5070.values/B).astype(int)
    cand['blk']=list(zip(cbx,cby)); off=cand.y_5070.values-cby*B
    n=len(pos)
    variants=[("fair (uniform)",cand)]
    for frac,nm in [(1/2,"S half"),(1/3,"S third"),(1/4,"S quarter"),(1/6,"S sixth")]:
        sub=cand[(off<B*frac)&(cand.blk.isin(posblk))]
        variants.append((f"skew {nm} of each 30km block",sub))
    for lbl,pool in variants:
        if len(pool)==0: continue
        sel=pool.sample(n=min(n,len(pool)),random_state=0)
        sbx,sby=np.floor(sel.x_5070.values/B).astype(int),np.floor(sel.y_5070.values/B).astype(int)
        negblk=set(zip(sbx,sby)); dmiss=len(posblk-negblk)/len(posblk)
        q,_=cKDTree(np.c_[sel.x_5070.values,sel.y_5070.values]).query(np.c_[px,py],k=1)
        flag="PASS" if dmiss<=0.15 else "FAIL"
        print(f"  {r} {lbl:36} n={len(sel):5} (d)={dmiss:.4f} [{flag}]  median pos->neg {np.median(q)/1000:6.2f} km  p90 {np.percentile(q,90)/1000:6.2f} km")
    print()
