"""Calibrate replacements for CR-0007's two broken gates.
Break 1: I19 (pooled) defeated by a single-region negative skew.
Break 2: negative-split geography ungated; I15-I19 never name their record set.
Read-only."""
import numpy as np, pandas as pd
from pyproj import Transformer
from scipy.spatial import cKDTree
from grouse_data import GrouseData
from prepare_training_data import thin_by_min_distance

R=["ME","NH","VT"]; BLK=3000; RF=1920.0; SEEDS=120
t=Transformer.from_crs("EPSG:4326","EPSG:5070",always_xy=True)
def xy(d):
    x,y=t.transform(d.longitude.values,d.latitude.values); return np.c_[x,y]

# ---- positives: partition, pool, thin once
rows=[]
for r in R:
    e=pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv",low_memory=False)
    if 'nonveg_landcover' in e: e=e[~e.nonveg_landcover.astype(bool)]
    rows.append(e[e.state==r][["longitude","latitude","state"]])
P=pd.concat(rows,ignore_index=True).drop_duplicates(["longitude","latitude"])
P["x_5070"],P["y_5070"]=t.transform(P.longitude.values,P.latitude.values)
P=thin_by_min_distance(P,30,42).reset_index(drop=True)
P["blk"]=(np.floor(P.x_5070/BLK).astype(int).astype(str)+"_"+np.floor(P.y_5070/BLK).astype(int).astype(str))
print(f"positives {len(P)}  positive-occupied blocks {P.blk.nunique()}")

# ---- negative candidate pool (hygiene + pooled thin + 300m buffer)
import os
if os.path.exists("inv_fix_breaks_pool.csv"):
    C=pd.read_csv("inv_fix_breaks_pool.csv")
else:
  c=[]
  for r in R:
    d=pd.read_csv(f"data/negatives/gbif_negatives_{r}.csv",low_memory=False)
    d=d[d.coord_uncertainty_m.fillna(0)<=1000]
    c.append(d[["longitude","latitude","state"]])
  C=pd.concat(c,ignore_index=True)
  C=C.loc[~C[["longitude","latitude"]].round(5).duplicated()].copy()
  C["x_5070"],C["y_5070"]=t.transform(C.longitude.values,C.latitude.values)
  C=thin_by_min_distance(C,30,42)
  d,_=cKDTree(xy(P)).query(xy(C),k=1)
  C=C[d>300].reset_index(drop=True)
  C.to_csv("inv_fix_breaks_pool.csv",index=False)
C["blk"]=(np.floor(C.x_5070/BLK).astype(int).astype(str)+"_"+np.floor(C.y_5070/BLK).astype(int).astype(str))
allblk=sorted(set(P.blk)|set(C.blk))
print(f"candidates {len(C)}  all-record-occupied blocks {len(allblk)}  "
      f"positive-free {len(allblk)-P.blk.nunique()}")

pxy={r:xy(P[P.state==r]) for r in R}
def i19(nsub):
    out={}
    for r in R:
        n=nsub[nsub.state==r]
        if len(n)==0: out[r]=np.nan; continue
        dd,_=cKDTree(xy(n)).query(pxy[r],k=1)
        out[r]=float((dd>RF).mean())
    dd,_=cKDTree(xy(nsub)).query(np.vstack([pxy[r] for r in R]),k=1)
    out["pooled"]=float((dd>RF).mean()); return out

# Moran's I of the val indicator over a given block set
def moran(blocks,valset,k=8):
    ctr=np.array([[int(b.split("_")[0])*BLK+BLK/2, int(b.split("_")[1])*BLK+BLK/2] for b in blocks])
    z=np.array([1.0 if b in valset else 0.0 for b in blocks]); z=z-z.mean()
    if z.std()==0: return 0.0
    _,idx=cKDTree(ctr).query(ctr,k=k+1); idx=idx[:,1:]
    num=(z[:,None]*z[idx]).sum()/k; den=(z**2).sum()
    return float(len(blocks)*num/(den*len(blocks)))

rng0=np.random.default_rng(0)
fair={"pooled":[],"per":[] }; att={"pooled":[],"per":[]}
mor_pos_f=[]; mor_all_f=[]; mor_all_a=[]
i18_pos=[]; i18_all=[]
for sd in range(SEEDS):
    rg=np.random.default_rng(sd)
    # val block draw over positive-occupied blocks
    cnt=P.blk.value_counts(); order=cnt.sample(frac=1,random_state=sd).index.tolist()
    tgt,vb,run=int(round(0.2*len(P))),set(),0
    for b in order:
        if run>=tgt: break
        vb.add(b); run+=cnt[b]
    # FAIR negatives: 1:1 per region, uniform from that region's candidates
    fs=[]; ats=[]
    for r in R:
        pool=C[C.state==r]; n=min((P.state==r).sum(),len(pool))
        fs.append(pool.iloc[rg.choice(len(pool),n,replace=False)])
        if r=="NH":   # ATTACK: southern half of each 30km cell, NH only
            cell=np.floor(pool.y_5070/30000).astype(int)
            keep=pool[pool.y_5070<=pool.groupby(cell).y_5070.transform("median")]
            m=min(n,len(keep)); ats.append(keep.iloc[rg.choice(len(keep),m,replace=False)])
        else: ats.append(fs[-1])
    F=pd.concat(fs,ignore_index=True); A=pd.concat(ats,ignore_index=True)
    vf,va=i19(F),i19(A)
    fair["pooled"].append(vf["pooled"]); fair["per"].append(max(vf[r] for r in R))
    att["pooled"].append(va["pooled"]);  att["per"].append(max(va[r] for r in R))
    if sd<40:
        mor_pos_f.append(moran(sorted(P.blk.unique()),vb))
        # Break 2 attack: positive-free blocks split east-first instead of hashed
        free=[b for b in allblk if b not in set(P.blk)]
        east=sorted(free,key=lambda b:int(b.split("_")[0]),reverse=True)
        vb_att=vb|set(east[:int(0.2*len(free))])
        vb_fair=vb|set(rg.choice(free,int(0.2*len(free)),replace=False))
        mor_all_f.append(moran(allblk,vb_fair)); mor_all_a.append(moran(allblk,vb_att))
def q(a):
    a=np.array(a); return f"min {a.min():.4f} p50 {np.median(a):.4f} p99 {np.percentile(a,99):.4f} max {a.max():.4f}"
print(f"\n=== Break 1: I19, {SEEDS} seeds, NH-only southern-half attack ===")
print(f"  POOLED  fair   {q(fair['pooled'])}")
print(f"  POOLED  attack {q(att['pooled'])}   <- overlap = the break")
print(f"  PER-REGION worst  fair   {q(fair['per'])}")
print(f"  PER-REGION worst  attack {q(att['per'])}")
fm,am=np.array(fair['per']).max(),np.array(att['per']).min()
print(f"  per-region separation: fair max {fm:.4f} | attack min {am:.4f} -> "
      f"{'SEPARATES' if am>fm else 'OVERLAPS'}")
print(f"\n=== Break 2: Moran on which block set (40 seeds) ===")
f_,a_=np.array(mor_all_f),np.array(mor_all_a)
print(f"  positives-only blocks, fair : {q(mor_pos_f)}")
print(f"  ALL-record blocks, fair     : {q(mor_all_f)}")
print(f"  ALL-record blocks, attack   : {q(mor_all_a)}")
print(f"  z of attack vs all-record null: {(a_.mean()-f_.mean())/f_.std():.1f}")
