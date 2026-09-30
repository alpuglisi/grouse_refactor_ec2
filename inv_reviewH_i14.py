"""CR-0007 I14 attack.  I14 = (1) re-run from the manifest reproduces the
shipped split bit-for-bit, (2) val block set at seed S differs from seed S'.
Both are properties of the *procedure*, not of the split's quality.  Build
three conformant-but-defective draws and score the whole acceptance set."""
import numpy as np, pandas as pd
from scipy.spatial import cKDTree

BLOCK=3000.0; ORIGIN=(0.0,0.0); VF=0.20
t=pd.read_csv("inv_reviewH_pooled_positives.csv")
bx=np.floor((t.x_5070.values-ORIGIN[0])/BLOCK).astype(int)
by=np.floor((t.y_5070.values-ORIGIN[1])/BLOCK).astype(int)
t["block_id"]=[f"{a}_{b}" for a,b in zip(bx,by)]
t["bx"],t["by"]=bx,by
bc=t.block_id.value_counts()
NB=len(bc); NR=len(t)
print(f"{NR} pooled positives, {NB} occupied 3 km blocks, "
      f"mean {NR/NB:.2f} records/block")
key=dict(zip(bc.index,zip(*[t.groupby('block_id').bx.first().reindex(bc.index).values,
                            t.groupby('block_id').by.first().reindex(bc.index).values])))
occ=set(bc.index)
nbrs={b:sum(1 for dx in(-1,0,1) for dy in(-1,0,1) if (dx,dy)!=(0,0)
            and f"{key[b][0]+dx}_{key[b][1]+dy}" in occ) for b in bc.index}

def fill(order,target):
    v,run=set(),0
    for b in order:
        if run>=target: break
        v.add(b); run+=bc[b]
    return v

TARGET=int(round(VF*NR))

def draw_fair(seed):            # the intended implementation
    return fill(bc.sample(frac=1,random_state=seed).index.tolist(),TARGET)
def draw_dense(seed):           # the earlier reviewer's attack: seed-INVARIANT
    return fill(bc.index.tolist(),TARGET)
def draw_dense_tie(seed):       # ATTACK C: densest-first, seed-broken ties
    s=bc.sample(frac=1,random_state=seed)
    return fill(s.sort_values(ascending=False,kind="mergesort").index.tolist(),TARGET)
def draw_adjacent(seed):        # ATTACK D: maximise train/val adjacency,
    s=bc.sample(frac=1,random_state=seed)          # density matched for I15
    cand=sorted(s.index,key=lambda b:(-nbrs[b],list(s.index).index(b)))
    v,run,nb=set(),0,0
    mean=NR/NB
    for b in cand:
        if run>=TARGET: break
        # keep val-block mean density near the global mean so I15 holds
        if nb and (run+bc[b])/(nb+1) > mean*1.02: continue
        v.add(b); run+=bc[b]; nb+=1
    for b in cand:                                  # top up if short
        if run>=TARGET: break
        if b not in v: v.add(b); run+=bc[b]; nb+=1
    return v

xy=t[["x_5070","y_5070"]].values
def score(name,fn):
    V=fn(42); V2=fn(7); V3=fn(1)
    isval=t.block_id.isin(V).values
    tr,va=xy[~isval],xy[isval]
    tree=cKDTree(tr); d,_=tree.query(va,k=1)
    # I2/I3 block disjointness by construction; I4 exact-coord overlap
    k=lambda a:set(map(tuple,np.round(a,5)))
    i4=len(k(t.loc[~isval,["longitude","latitude"]].values)
           & k(t.loc[isval,["longitude","latitude"]].values))
    per=t.assign(v=isval).groupby("state").v.mean()*100
    jac=len(V&V2)/len(V|V2)
    print(f"\n--- {name}")
    print(f"  I14a deterministic re-run from manifest .... PASS (pure fn of "
          f"(records, spacing, block, origin, seed, vf))")
    print(f"  I14b val block set seed42 vs seed7 ........ "
          f"{'DIFFERS -> PASS' if V!=V2 else 'IDENTICAL -> FAIL'}"
          f"   (Jaccard {jac:.3f}, seed1 Jaccard {len(V&V3)/len(V|V3):.3f})")
    print(f"  I15 val blocks {len(V):4d}/{NB} = {100*len(V)/NB:5.2f}%  vs "
          f"record val {100*isval.mean():5.2f}%  -> "
          f"{'PASS' if abs(100*len(V)/NB-100*isval.mean())<=1.0 else 'FAIL'}"
          f"   ({bc[list(V)].sum()/len(V):.2f} rec/val block)")
    print(f"  I7 per-region val %: "+", ".join(f"{s} {v:.2f}" for s,v in per.items())
          +f"  -> {'PASS' if (per-20).abs().max()<=2 else 'FAIL'} (+-2pp)")
    print(f"  I4 identical-coord train/val overlap ....... {i4}  -> "
          f"{'PASS' if i4==0 else 'FAIL'}")
    print(f"  LEAKAGE (gated by NOTHING): val->nearest train positive")
    print(f"     median {np.median(d):8.0f} m   p10 {np.percentile(d,10):7.0f} m"
          f"   within  30 m {(d<30).mean()*100:5.2f}%"
          f"   100 m {(d<100).mean()*100:5.2f}%"
          f"   500 m {(d<500).mean()*100:5.2f}%"
          f"   1920 m (receptive field) {(d<1920).mean()*100:5.2f}%")
for n,f in (("A  intended (sample(frac=1, random_state=seed))",draw_fair),
            ("B  earlier reviewer's attack: index.tolist() densest-first",draw_dense),
            ("C  ATTACK: densest-first, ties broken by the seed",draw_dense_tie),
            ("D  ATTACK: adjacency-maximising, density-matched",draw_adjacent)):
    score(n,f)
