"""Round-2: do v2's acceptance invariants have any teeth on the negative
side, and does the 30 km occupied-block check discriminate? Read-only."""
import numpy as np, pandas as pd, hashlib
from pyproj import Transformer
from scipy.spatial import cKDTree
R=["ME","NH","VT"]; t=Transformer.from_crs("EPSG:4326","EPSG:5070",always_xy=True)
def xy(d): return np.column_stack(t.transform(d.longitude.values,d.latitude.values))
def gid(a,bs): 
    b=np.floor(a/bs).astype(int)
    return np.array([f"{p}_{q}" for p,q in zip(b[:,0],b[:,1])])
load=lambda k,s,r: pd.read_csv(f"data/{'pipeline' if k=='pos' else 'negatives'}/{s}_{'positives' if k=='pos' else 'negatives'}_{r}.csv")
P={s:pd.concat([load('pos',s,r).assign(region=r) for r in R],ignore_index=True) for s in ("train","val")}
N={s:pd.concat([load('neg',s,r).assign(region=r) for r in R],ignore_index=True) for s in ("train","val")}

print("=== 1. CROSS-CLASS leakage on CURRENT data (no invariant covers it) ===")
trp=xy(P['train']); vap=xy(P['val']); trn=xy(N['train']); van=xy(N['val'])
for lbl,a,b in (("val NEG vs train POS",van,trp),("val POS vs train NEG",vap,trn),
                ("val NEG vs train NEG",van,trn)):
    d,_=cKDTree(b).query(a,k=1)
    same=(gid(a,3000)[:,None]==None)
    bs=set(gid(b,3000).tolist()); sb=np.isin(gid(a,3000),list(bs))
    print(f"  {lbl}: <=30 m {(d<=30).mean():.2%}  <=300 m {(d<=300).mean():.2%} "
          f"| in the SAME 3 km block as an opposite-split record: {sb.mean():.1%}")

print("\n=== 2. would a HASH-SPLIT (stale block file) negatives set violate "
      "any listed invariant? ===")
# simulate: negatives split purely by md5 hash of their global block id
allN=pd.concat([N['train'],N['val']],ignore_index=True)
a=xy(allN); allN['block_id']=gid(a,3000)
def hs(b,vf=0.19,seed=42):
    h=int(hashlib.md5(f"{seed}:{b}".encode()).hexdigest(),16)
    return 'val' if (h%10000)<vf*10000 else 'train'
allN['hsplit']=[hs(b) for b in allN.block_id]
htr=allN[allN.hsplit=='train']; hva=allN[allN.hsplit=='val']
k=lambda d:(d.longitude.round(5).astype(str)+","+d.latitude.round(5).astype(str))
print(f"  hash-split negatives: train {len(htr)} val {len(hva)}")
print(f"  invariant 'no coordinate in both pooled splits, per class': "
      f"{len(set(k(htr))&set(k(hva)))} collisions -> "
      f"{'VIOLATED' if len(set(k(htr))&set(k(hva))) else 'PASSES'}")
d,_=cKDTree(trp).query(xy(hva),k=1)
print(f"  invariant '0.0% of val POSITIVES within 30 m of a train positive': "
      f"unaffected by the negative side -> PASSES")
print(f"  (meanwhile {(d<=30).mean():.2%} of these val negatives sit within "
      f"30 m of a train positive and "
      f"{np.isin(gid(xy(hva),3000),list(set(gid(trp,3000).tolist()))).mean():.1%} "
      f"share a 3 km block with one)")

print("\n=== 3. does the 30 km occupied-block check discriminate? ===")
for bs in (3000,10000,30000):
    for lbl,pp,nn in (("CURRENT",np.vstack([trp,vap]),np.vstack([trn,van])),):
        sp=set(gid(pp,bs).tolist()); sn=set(gid(nn,bs).tolist())
        print(f"  {lbl} grid {bs:>6}: jaccard {len(sp&sn)/len(sp|sn):.3f} "
              f"pos-only {len(sp-sn)/len(sp):.1%}  (post-fix simulated: "
              f"{ {3000:'0.245/57.3%',10000:'0.805/9.4%',30000:'0.927/1.1%'}[bs] })")
