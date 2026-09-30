"""R3-JOB3: reproduce v3's I1-I4 'CURRENT' numbers, and probe the new set for holes."""
import pandas as pd, numpy as np, hashlib
from scipy.spatial import cKDTree
R=["ME","NH","VT"]; BS=3000.0
def cat(kind,split):
    f=(lambda r:f"data/pipeline/{split}_positives_{r}.csv") if kind=="pos" else (lambda r:f"data/negatives/{split}_negatives_{r}.csv")
    return pd.concat([pd.read_csv(f(r)).assign(region=r) for r in R],ignore_index=True)
ptr,pva,ntr,nva=cat("pos","train"),cat("pos","val"),cat("neg","train"),cat("neg","val")
pool=pd.concat([ptr.assign(split="train"),pva.assign(split="val")],ignore_index=True)
npool=pd.concat([ntr.assign(split="train"),nva.assign(split="val")],ignore_index=True)
# I1: pooled positive pairs < 30 m
t=cKDTree(np.c_[pool.x_5070,pool.y_5070]); pairs=t.query_pairs(30.0)
print(f"I1 pooled positive pairs <30m  CURRENT = {len(pairs)}")
# I4
key=lambda d:set(zip(d.longitude.round(5),d.latitude.round(5)))
print(f"I4 train/val coord collisions   pos={len(key(ptr)&key(pva))} neg={len(key(ntr)&key(nva))}")
# global-origin 3 km blocks
def gb(d): return list(zip(np.floor(d.x_5070/BS).astype(int),np.floor(d.y_5070/BS).astype(int)))
for label,dd in (("positives only",pool),("negatives only",npool),("both classes",pd.concat([pool,npool]))):
    d=dd.copy(); d["gb"]=gb(d)
    g=d.groupby("gb")["split"].nunique()
    print(f"I2 blocks holding train AND val ({label:14s}) CURRENT = {int((g>1).sum())} of {len(g)}")
d=pd.concat([pool,npool]); d["gb"]=gb(d)
trb=set(d.loc[d.split=="train","gb"]); nv=npool.copy(); nv["gb"]=gb(nv); nv=nv[nv.split=="val"]
print(f"I3 val negatives sharing a global block with ANY train record CURRENT = {100*nv.gb.isin(trb).mean():.1f}% ({int(nv.gb.isin(trb).sum())} of {len(nv)})")
# --- HOLE PROBE: degenerate block size.  Pooled+thinned, but blocks of 300 m.
print("\n=== HOLE PROBE: a compliant-looking pipeline with a DEGENERATE block size ===")
allp=pool.copy()
k=allp.longitude.round(5).astype(str)+","+allp.latitude.round(5).astype(str)
allp=allp.loc[~k.duplicated()].copy()
# pooled thin at 30 m (greedy, order-shuffled) -> guarantees I1=0
rng=np.random.default_rng(42); order=rng.permutation(len(allp))
co=allp[["x_5070","y_5070"]].values[order]; keep=np.zeros(len(allp),bool); kept=[]; tree=None
for i,pt in enumerate(co):
    if tree is None or not kept: ok=True
    else:
        dd,_=tree.query(pt,k=1); ok=dd>=30
    if ok: kept.append(pt); keep[order[i]]=True; tree=cKDTree(np.array(kept))
thin=allp[keep].copy()
def run(bs,seed=42):
    bx=np.floor(thin.x_5070/bs).astype(int); by=np.floor(thin.y_5070/bs).astype(int)
    bid=pd.Series([f"{a}_{b}" for a,b in zip(bx,by)],index=thin.index)
    vc=bid.value_counts(); sh=vc.sample(frac=1,random_state=seed).index.tolist()
    tgt=int(round(0.2*len(thin))); vb=set(); run_=0
    for b in sh:
        if run_>=tgt: break
        vb.add(b); run_+=vc[b]
    sp=bid.map(lambda b:'val' if b in vb else 'train')
    tr=thin[sp=='train']; va=thin[sp=='val']
    t=cKDTree(np.c_[tr.x_5070,tr.y_5070]); dd,_=t.query(np.c_[va.x_5070,va.y_5070],k=1)
    t2=cKDTree(np.c_[thin.x_5070,thin.y_5070]); np_=len(t2.query_pairs(30.0))
    g=pd.DataFrame({"b":bid,"s":sp}).groupby("b")["s"].nunique()
    return dict(bs=bs,n=len(thin),blocks=len(vc),recs_per_block=len(thin)/len(vc),
        valfrac=100*len(va)/len(thin), I1=np_, I2=int((g>1).sum()),
        d30=100*(dd<=30).mean(), d300=100*(dd<=300).mean(), d3k=100*(dd<=3000).mean())
for bs in (3000.,1000.,300.,60.):
    r=run(bs)
    print(f"  block={r['bs']:7.0f}m  n={r['n']}  blocks={r['blocks']:5d}  rec/block={r['recs_per_block']:.2f}  "
          f"valfrac={r['valfrac']:.2f}%  I1={r['I1']}  I2={r['I2']}  "
          f"val-pos<=30m={r['d30']:.2f}%  <=300m={r['d300']:5.2f}%  <=3km={r['d3k']:5.2f}%")
