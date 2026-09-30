"""Baseline the invariant set proposed for v3, so the CR can state real
fail-today / pass-after numbers instead of asserting them. Read-only."""
import numpy as np, pandas as pd
from pyproj import Transformer
from scipy.spatial import cKDTree
from grouse_data import GrouseData
from prepare_training_data import thin_by_min_distance

R, BLK, MIN_SP, SEED, VF = ["ME","NH","VT"], 3000, 30, 42, 0.2
t = Transformer.from_crs("EPSG:4326","EPSG:5070",always_xy=True)
data = GrouseData()

def load(compliant):
    rows=[]
    for r in R:
        for kind,get in (("pos",data[r].positives),("neg",data[r].negatives)):
            for sp in ("train","val"):
                d=get(sp)[["longitude","latitude"]].copy()
                d["kind"],d["src"],d["split"]=kind,r,sp
                rows.append(d)
    a=pd.concat(rows,ignore_index=True)
    a["x"],a["y"]=t.transform(a.longitude.values,a.latitude.values)
    a["key"]=a.longitude.round(5).astype(str)+","+a.latitude.round(5).astype(str)
    if not compliant:                      # CURRENT: per-region grids & draws
        return a
    # COMPLIANT: dedup, pooled 30 m thin on positives, ONE global grid, ONE draw
    a=a.drop_duplicates(["kind","key"]).copy()
    pos=a[a.kind=="pos"].copy(); neg=a[a.kind=="neg"].copy()
    pos=thin_by_min_distance(pos.rename(columns={"x":"x_5070","y":"y_5070"}),
                             MIN_SP,SEED).rename(columns={"x_5070":"x","y_5070":"y"})
    a=pd.concat([pos,neg],ignore_index=True)
    a["blk"]=(np.floor(a.x/BLK).astype(int).astype(str)+"_"+
              np.floor(a.y/BLK).astype(int).astype(str))
    cnt=a[a.kind=="pos"].blk.value_counts()
    order=cnt.sample(frac=1,random_state=SEED).index.tolist()
    tgt,vb,run=int(round(VF*cnt.sum())),set(),0
    for b in order:
        if run>=tgt: break
        vb.add(b); run+=cnt[b]
    a["split"]=np.where(a.blk.isin(vb),"val","train")
    return a

for label,compliant in (("CURRENT (on-disk)",False),("COMPLIANT (v3 pipeline)",True)):
    a=load(compliant)
    if "blk" not in a:
        a["blk"]=(np.floor(a.x/BLK).astype(int).astype(str)+"_"+
                  np.floor(a.y/BLK).astype(int).astype(str))
    tr,va=a[a.split=="train"],a[a.split=="val"]
    print(f"\n=== {label}  (n={len(a)}) ===")
    # I1 min-spacing among pooled positives  (A's R2-1)
    p=a[a.kind=="pos"]
    pr=cKDTree(p[["x","y"]].values).query_pairs(MIN_SP,output_type='ndarray')
    print(f"  I1 pooled positive pairs < {MIN_SP} m .............. {len(pr):5d}   [require 0]")
    # I2 blocks holding BOTH a train and a val record, EITHER class (B/C)
    both=set(tr.blk)&set(va.blk)
    print(f"  I2 blocks holding train AND val (both classes) ... {len(both):5d}   [require 0]")
    # I3 val negatives sharing a block with any train record (C)
    vn=va[va.kind=="neg"]
    share=vn.blk.isin(set(tr.blk)).mean() if len(vn) else float('nan')
    print(f"  I3 val negatives sharing a block w/ train ........ {share:5.1%}   [require 0%]")
    # I4 exact coordinate collisions per class
    c=sum(len(set(tr[tr.kind==k].key)&set(va[va.kind==k].key)) for k in ("pos","neg"))
    print(f"  I4 train/val coordinate collisions (per class) ... {c:5d}   [require 0]")
