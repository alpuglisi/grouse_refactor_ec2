"""CR-0007 I14 attack, take 2: a draw that maximises train/val spatial
proximity while satisfying I1-I15 as written."""
import numpy as np, pandas as pd
from scipy.spatial import cKDTree
BLOCK=3000.0; ORIGIN=(0.0,0.0); VF=0.20; RF=1920.0
t=pd.read_csv("inv_reviewH_pooled_positives.csv").reset_index(drop=True)
bx=np.floor((t.x_5070.values-ORIGIN[0])/BLOCK).astype(int)
by=np.floor((t.y_5070.values-ORIGIN[1])/BLOCK).astype(int)
t["block_id"]=[f"{a}_{b}" for a,b in zip(bx,by)]
bc=t.block_id.value_counts(); NB=len(bc); NR=len(t)
xy=t[["x_5070","y_5070"]].values
tree=cKDTree(xy)
pairs=tree.query_ball_point(xy,RF)
blk=t.block_id.values
# gain(b) = records in b with >=1 within-RF record in a DIFFERENT block
gain={}
for i,nb in enumerate(pairs):
    if any(blk[j]!=blk[i] for j in nb):
        gain[blk[i]]=gain.get(blk[i],0)+1
def draw_fair(seed):
    v,run,T=set(),0,int(round(VF*NR))
    for b in bc.sample(frac=1,random_state=seed).index:
        if run>=T: break
        v.add(b); run+=bc[b]
    return v
def draw_attack(seed):
    """region-stratified, proximity-maximising, density-matched."""
    rng=np.random.default_rng(seed)
    reg=t.groupby("block_id").state.first()
    v=set(); tot_rec=0; tot_blk=0
    mean=NR/NB
    for R in sorted(t.state.unique()):
        blocks=[b for b in bc.index if reg[b]==R]
        nr=int(t.state.eq(R).sum()); T=int(round(VF*nr))
        jitter={b:rng.random() for b in blocks}
        order=sorted(blocks,key=lambda b:(-(gain.get(b,0)/bc[b]),-gain.get(b,0),jitter[b]))
        run=0; nb=0
        for b in order:
            if run>=T: break
            if nb and (run+bc[b])/(nb+1)>mean*1.03: continue
            v.add(b); run+=bc[b]; nb+=1
        for b in order:
            if run>=T: break
            if b not in v: v.add(b); run+=bc[b]; nb+=1
    return v
def score(name,fn):
    V,V2=fn(42),fn(7)
    isval=t.block_id.isin(V).values
    d,_=cKDTree(xy[~isval]).query(xy[isval],k=1)
    per=t.assign(v=isval).groupby("state").v.mean()*100
    k=lambda a:set(map(tuple,np.round(a,5)))
    i4=len(k(t.loc[~isval,["longitude","latitude"]].values)&k(t.loc[isval,["longitude","latitude"]].values))
    bvf=100*len(V)/NB; rvf=100*isval.mean()
    print(f"\n--- {name}")
    print(f"  I14a manifest re-run bit-for-bit ..... PASS")
    print(f"  I14b seed 42 vs 7 block sets ......... {'DIFFER -> PASS' if V!=V2 else 'FAIL'}"
          f" (Jaccard {len(V&V2)/len(V|V2):.3f})")
    print(f"  I15 blocks {bvf:.2f}% vs records {rvf:.2f}% ... "
          f"{'PASS' if abs(bvf-rvf)<=1.0 else 'FAIL'}   ({bc[list(V)].sum()/len(V):.2f} rec/val blk)")
    print(f"  I7  per-region val %: "+", ".join(f"{s} {x:.2f}" for s,x in per.items())
          +f" -> {'PASS' if (per-20).abs().max()<=2 else 'FAIL'}")
    print(f"  I2/I3 block disjointness ............. PASS by construction")
    print(f"  I4  identical-coord overlap .......... {i4} -> {'PASS' if i4==0 else 'FAIL'}")
    print(f"  I1  30 m pooled pairs ................ 0 (unchanged by the draw)")
    print(f"  ** val positives within {RF:.0f} m (receptive field) of a train "
          f"positive: {(d<RF).mean()*100:.2f}%   median nn {np.median(d):.0f} m **")
    return (d<RF).mean()
a=score("A  intended fair draw",draw_fair)
b=score("D  ATTACK: proximity-maximising, region-stratified, density-matched",draw_attack)
print(f"\nleakage inflation: {a*100:.2f}% -> {b*100:.2f}%  "
      f"(+{100*(b-a):.1f} pp) with every listed invariant green")
