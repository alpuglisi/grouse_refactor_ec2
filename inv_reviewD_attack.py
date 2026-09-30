"""Reviewer D attack: build a CR-compliant-looking pipeline two ways and test
whether the four invariants distinguish them."""
import numpy as np, pandas as pd, hashlib
from pyproj import Transformer
from scipy.spatial import cKDTree

REG=["ME","NH","VT"]
BOXES={"ME":(-71.158,42.889,-66.852,47.555),"NH":(-72.626,42.605,-70.600,45.398),
       "VT":(-73.510,42.632,-71.422,45.112)}
BS=3000.0; VF=0.2; SEED=42

T=Transformer.from_crs("EPSG:4326","EPSG:5070",always_xy=True)
def origin(box):
    cx,cy=T.transform([box[0],box[2]],[box[1],box[3]])
    return min(cx),min(cy)

print("=== per-region grid origins and phases (mod 3000) ===")
for r in REG:
    x0,y0=origin(BOXES[r])
    print(f"  {r}: x0={x0:.2f} y0={y0:.2f}   phase x={x0%BS:.2f} y={y0%BS:.2f}")

# ---------- assemble the partitioned positive set (CR §2/§3) ----------
allpos=pd.concat([pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv").assign(src=r)
                  for r in REG], ignore_index=True)
# habitat-only, as prepare_training_data does
hab=allpos[~allpos['nonveg_landcover'].astype(bool)].copy()
# the record's habitat flag must come from its OWN state's grid (CR §3)
own=hab[hab.state==hab.src].copy()
own=own.drop_duplicates(subset=["longitude","latitude","year"]).reset_index(drop=True)
print(f"\npartitioned habitat positives (own-state grid, dedup lon/lat/year): {len(own)}"
      f"  {own.state.value_counts().to_dict()}")

def thin(df, m, seed):
    rng=np.random.default_rng(seed); order=rng.permutation(len(df))
    coords=df[['x_5070','y_5070']].values[order]
    keep=np.zeros(len(df),bool); kept=[]; tree=None
    for i,pt in enumerate(coords):
        ok=True if tree is None else tree.query(pt,k=1)[0]>=m
        if ok:
            kept.append(pt); keep[order[i]]=True; tree=cKDTree(np.array(kept))
    return df[keep].copy()

pooled=thin(own,30.0,SEED)
print(f"pooled 30 m thinning -> {len(pooled)} (CR expects ~6230)")

perregion=pd.concat([thin(own[own.state==r],30.0,SEED) for r in REG], ignore_index=True)
print(f"per-region 30 m thinning then pooled -> {len(perregion)}")

def blockids(df, mode):
    if mode=="global":
        bx=np.floor(df.x_5070.values/BS).astype(int); by=np.floor(df.y_5070.values/BS).astype(int)
        return pd.Series([f"{a}_{b}" for a,b in zip(bx,by)],index=df.index)
    ids=pd.Series(index=df.index,dtype=object)
    for r in REG:
        m=(df.state==r).values
        x0,y0=origin(BOXES[r])
        bx=np.floor((df.x_5070.values[m]-x0)/BS).astype(int)
        by=np.floor((df.y_5070.values[m]-y0)/BS).astype(int)
        ids.loc[df.index[m]]=[f"{a}_{b}" for a,b in zip(bx,by)]
    return ids

def assign(df, ids, seed=SEED):
    cnt=ids.value_counts()
    shuf=cnt.sample(frac=1,random_state=seed).index.tolist()
    target=int(round(VF*len(df))); val=set(); run=0
    for b in shuf:
        if run>=target: break
        val.add(b); run+=cnt[b]
    return ids.map(lambda b:'val' if b in val else 'train')

def gglobal(df):
    bx=np.floor(df.x_5070.values/BS).astype(int); by=np.floor(df.y_5070.values/BS).astype(int)
    return np.array([f"{a}_{b}" for a,b in zip(bx,by)])

def report(name, pos, ids, split, negs):
    print(f"\n########## {name} ##########")
    pos=pos.copy(); pos['block_id']=ids.values; pos['split']=split.values
    rec=pd.concat([pos.assign(cls='pos')[['x_5070','y_5070','block_id','split','cls','state']],
                   negs.assign(cls='neg')[['x_5070','y_5070','block_id','split','cls','state']]],
                  ignore_index=True)
    # I1
    xy=pos[['x_5070','y_5070']].values; t=cKDTree(xy)
    print(f"  I1 pooled positive pairs <30m .............. {len(t.query_pairs(30.0,output_type='ndarray'))}   (require 0)")
    # I2 on the block_id column
    g=rec.groupby('block_id')['split'].nunique()
    print(f"  I2 blocks w/ train AND val (id column) ..... {(g>1).sum()}   (require 0)")
    # I2 recomputed on a single GLOBAL grid
    rec['gb']=gglobal(rec)
    g2=rec.groupby('gb')['split'].nunique()
    print(f"  I2' same, recomputed on ONE global grid .... {(g2>1).sum()}   <-- geometric truth")
    # I3
    trk=set(rec.loc[rec.split=='train','block_id']); vn=rec[(rec.split=='val')&(rec.cls=='neg')]
    print(f"  I3 val negs in a train block (id column) ... {100*vn.block_id.isin(trk).mean():.2f}%  (require 0%)")
    trg=set(rec.loc[rec.split=='train','gb'])
    print(f"  I3' same, on ONE global grid ............... {100*vn.gb.isin(trg).mean():.2f}%")
    # I4 per class
    for c in ('pos','neg'):
        s=rec[rec.cls==c]
        ktr=set(map(tuple,np.round(s.loc[s.split=='train',['x_5070','y_5070']].values,3)))
        kva=list(map(tuple,np.round(s.loc[s.split=='val',['x_5070','y_5070']].values,3)))
        print(f"  I4 [{c}] train/val coord collisions ........ {sum(1 for k in kva if k in ktr)}   (require 0)")
    # val fraction
    print(f"  val fraction (pos) ......................... {100*(pos.split=='val').mean():.2f}%")
    # GEOMETRIC LEAK: cross-split pairs within D metres, either class
    for D in (30,100,300,1000):
        tt=cKDTree(rec[rec.split=='train'][['x_5070','y_5070']].values)
        vv=rec[rec.split=='val'][['x_5070','y_5070']].values
        d,_=tt.query(vv,k=1)
        print(f"  LEAK val records with a TRAIN record within {D:>4} m : {(d<D).sum()}  ({100*(d<D).mean():.2f}%)")
        break
    tt=cKDTree(rec[rec.split=='train'][['x_5070','y_5070']].values)
    vv=rec[rec.split=='val'][['x_5070','y_5070']].values
    d,_=tt.query(vv,k=1)
    for D in (30,100,300,1000,3000):
        print(f"      within {D:>5} m: {(d<D).sum():6d}  ({100*(d<D).mean():5.2f}%)")
    return rec

# negatives: reuse the existing selected negatives (already state-partitioned),
# re-blocked/re-split under each scheme so the negative side is consistent.
negsrc=pd.concat([pd.read_csv(f"data/negatives/negatives_{r}.csv") for r in REG],ignore_index=True)

def build(mode):
    ids=blockids(pooled,mode); split=assign(pooled,ids)
    table=dict(zip(ids,split))
    n=negsrc.copy(); nid=blockids(n,mode)
    vf=(split=='val').mean()
    def h(b): return 'val' if int(hashlib.md5(f"{SEED}:{b}".encode()).hexdigest(),16)%10000 < vf*10000 else 'train'
    n['block_id']=nid.values
    n['split']=[table.get(b) or h(b) for b in nid]
    return pooled, ids, split, n

for mode,label in (("global","A: CR-COMPLIANT (single global origin)"),
                   ("perregion","B: ATTACK (per-region origin, one pooled block table)")):
    p,i,s,n=build(mode)
    report(label,p,i,s,n)
