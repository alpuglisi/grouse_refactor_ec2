"""ATTACK 4: v2's assertion (d) is a 30 km occupied-block support test.
Displace every negative to the southern third of its OWN 30 km block:
support collapses at the 3-30 km scale while (d) reads ~0."""
import pandas as pd, numpy as np
from pyproj import Transformer
from scipy.spatial import cKDTree
import prepare_training_data as P
T=Transformer.from_crs("EPSG:4326","EPSG:5070",always_xy=True)
R=["ME","NH","VT"]
B=30000.0
def blocks(x,y,size): return np.floor(x/size).astype(int), np.floor(y/size).astype(int)
for r in R:
    pos=pd.read_csv(f"data/pipeline/thinned_positives_{r}.csv")
    px,py=T.transform(pos.longitude.values,pos.latitude.values)
    cand=pd.read_csv(f"data/negatives/gbif_negatives_{r}.csv")
    k=cand[['longitude','latitude']].round(5); cand=cand.loc[~k.duplicated()].copy()
    cand['x'],cand['y']=T.transform(cand.longitude.values,cand.latitude.values)
    cand=P.thin_by_min_distance(cand.rename(columns={'x':'x_5070','y':'y_5070'}),30,42)
    cand['x'],cand['y']=cand.x_5070,cand.y_5070
    d,_=cKDTree(np.c_[px,py]).query(cand[['x','y']].values,k=1)
    cand=cand[d>300].copy()
    n_target=len(pos)
    pbx,pby=blocks(px,py,B); posblk=set(zip(pbx,pby))
    cbx,cby=blocks(cand.x.values,cand.y.values,B)
    cand['blk']=list(zip(cbx,cby))
    # FAIR draw: uniform random
    rng=np.random.default_rng(0)
    fair=cand.sample(n=min(n_target,len(cand)),random_state=0)
    # SKEWED draw: only candidates in the southern third of their own 30km block
    off_y=cand.y.values - cby*B
    skew_pool=cand[off_y < B/3.0]
    # restrict further to positive-occupied blocks so (d) stays 0
    skew_pool=skew_pool[skew_pool.blk.isin(posblk)]
    skew=skew_pool.sample(n=min(n_target,len(skew_pool)),random_state=0)
    for lbl,sel in [("fair",fair),("skew(S third of each 30km block)",skew)]:
        sbx,sby=blocks(sel.x.values,sel.y.values,B); negblk=set(zip(sbx,sby))
        dmiss=len(posblk-negblk)/len(posblk)
        dd,_=cKDTree(np.c_[sel.x.values,sel.y.values]).query(np.c_[px,py],k=1)
        print(f"{r:3} {lbl:34} n={len(sel):5} (d)={dmiss:.4f}  "
              f"median dist pos->nearest neg {np.median(dd)/1000:6.2f} km  p90 {np.percentile(dd,90)/1000:6.2f} km")
    print()
