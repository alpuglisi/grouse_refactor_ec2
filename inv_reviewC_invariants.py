"""Reviewer C: can every CR-0006 acceptance invariant pass while a real
train/val leak survives?  Concretely: simulate the negative split falling
through to hash assignment (the failure mode the CR itself describes for
legacy/gen_negs.py) and evaluate each listed invariant."""
import pandas as pd, numpy as np, hashlib
from scipy.spatial import cKDTree
R=["ME","NH","VT"]
def load(kind,split,r):
    p=(f"data/pipeline/{split}_positives_{r}.csv" if kind=="pos"
       else f"data/negatives/{split}_negatives_{r}.csv")
    return pd.read_csv(p)
pos_tr=pd.concat([load("pos","train",r).assign(region=r) for r in R],ignore_index=True)
pos_va=pd.concat([load("pos","val",r).assign(region=r) for r in R],ignore_index=True)
neg_tr=pd.concat([load("neg","train",r).assign(region=r) for r in R],ignore_index=True)
neg_va=pd.concat([load("neg","val",r).assign(region=r) for r in R],ignore_index=True)
print("pooled sizes  pos:",len(pos_tr),len(pos_va)," neg:",len(neg_tr),len(neg_va))

def key(df): return set(zip(df.longitude.round(5),df.latitude.round(5)))
print("\nINVARIANT 1 (0 pooled train/val coord collisions @5dp, per class):")
print("   positives collisions:",len(key(pos_tr)&key(pos_va)),
      " negatives collisions:",len(key(neg_tr)&key(neg_va)))
print("   -> this is BUG-0027 today for positives")

def nn(a,b):
    t=cKDTree(np.c_[a.x_5070,a.y_5070]); d,_=t.query(np.c_[b.x_5070,b.y_5070],k=1); return d
dpos=nn(pos_tr,pos_va)
print("\nINVARIANT 2/3 (val positives near a pooled train positive):")
for thr in (0.001,30,300,3000):
    print(f"   <{thr:>6} m : {100*(dpos<=thr).mean():5.2f}%  ({(dpos<=thr).sum()})")

dneg=nn(neg_tr,neg_va)
print("\nSAME METRIC FOR NEGATIVES (NOT in the CR's invariant list):")
for thr in (0.001,30,300,3000):
    print(f"   <{thr:>6} m : {100*(dneg<=thr).mean():5.2f}%  ({(dneg<=thr).sum()})")

print("\nINVARIANT 4 (val fraction 20% +-1pp):")
print(f"   positives {100*len(pos_va)/(len(pos_va)+len(pos_tr)):.2f}%  "
      f"negatives {100*len(neg_va)/(len(neg_va)+len(neg_tr)):.2f}%")

# --- simulate 100% hash fallthrough for negatives (the silent BUG-0027 relapse)
print("\n=== SIMULATION: negatives split by hash only (block ids never matched) ===")
allneg=pd.concat([neg_tr,neg_va],ignore_index=True)
def split_for_unassigned(bid,vf,seed):
    h=int(hashlib.md5(f"{seed}:{bid}".encode()).hexdigest(),16)
    return 'val' if (h%10000) < vf*10000 else 'train'
# block ids computed on a DIFFERENT origin (the failure mode): shift by 1234 m
BS=3000.
bx=np.floor((allneg.x_5070.values-1234)/BS).astype(int)
by=np.floor((allneg.y_5070.values-1234)/BS).astype(int)
bid=[f"{a}_{b}" for a,b in zip(bx,by)]
sp=np.array([split_for_unassigned(b,0.2,42) for b in bid])
h_tr=allneg[sp=='train']; h_va=allneg[sp=='val']
print(f"   sizes train {len(h_tr)} val {len(h_va)}  val frac {100*len(h_va)/len(allneg):.2f}%  (invariant 4: "
      f"{'PASS' if abs(100*len(h_va)/len(allneg)-20)<=1 else 'FAIL'})")
print("   INVARIANT 1 negatives coord collisions:",len(key(h_tr)&key(h_va)),
      "(PASS - thinning guarantees 30 m separation)")
d=nn(h_tr,h_va)
for thr in (30,300,3000):
    print(f"   val negatives within {thr:>5} m of a train negative: {100*(d<=thr).mean():5.2f}%")
# and the real leak: same 3 km block as a train record?
tb=set(zip(np.floor(h_tr.x_5070/BS).astype(int),np.floor(h_tr.y_5070/BS).astype(int)))
vb=set(zip(np.floor(h_va.x_5070/BS).astype(int),np.floor(h_va.y_5070/BS).astype(int)))
print(f"   3 km blocks holding BOTH train and val negatives: {len(tb&vb)} of {len(vb)} val blocks")
# baseline with the real inherited split
tb0=set(zip(np.floor(neg_tr.x_5070/BS).astype(int),np.floor(neg_tr.y_5070/BS).astype(int)))
vb0=set(zip(np.floor(neg_va.x_5070/BS).astype(int),np.floor(neg_va.y_5070/BS).astype(int)))
print(f"   (baseline, today's inherited split: {len(tb0&vb0)} of {len(vb0)} shared)")
