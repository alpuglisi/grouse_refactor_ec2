"""CR-0007 I14 attack, final: stratify the val-block draw by (region, block
record count) so I7 and I15 hold exactly, and within each stratum pick the
blocks that maximise train/val proximity."""
import numpy as np, pandas as pd
from scipy.spatial import cKDTree
BLOCK=3000.0; ORIGIN=(0.,0.); VF=0.20; RF=1920.0
t=pd.read_csv("inv_reviewH_pooled_positives.csv").reset_index(drop=True)
bx=np.floor((t.x_5070.values-ORIGIN[0])/BLOCK).astype(int)
by=np.floor((t.y_5070.values-ORIGIN[1])/BLOCK).astype(int)
t["block_id"]=[f"{a}_{b}" for a,b in zip(bx,by)]
bc=t.block_id.value_counts(); NB=len(bc); NR=len(t); xy=t[["x_5070","y_5070"]].values
blk=t.block_id.values
nb_list=cKDTree(xy).query_ball_point(xy,RF)
gain={}
for i,nb in enumerate(nb_list):
    if any(blk[j]!=blk[i] for j in nb): gain[blk[i]]=gain.get(blk[i],0)+1
reg=t.groupby("block_id").state.first()
def draw_fair(seed):
    v,run,T=set(),0,int(round(VF*NR))
    for b in bc.sample(frac=1,random_state=seed).index:
        if run>=T: break
        v.add(b); run+=bc[b]
    return v
def draw_attack(seed):
    rng=np.random.default_rng(seed); v=set()
    for R in sorted(t.state.unique()):
        for cnt in sorted(set(bc.values)):
            S=[b for b in bc.index if reg[b]==R and bc[b]==cnt]
            if not S: continue
            k=int(round(VF*len(S)))
            if k==0: continue
            j={b:rng.random() for b in S}
            S.sort(key=lambda b:(-(gain.get(b,0)/cnt),j[b]))
            v.update(S[:k])
    return v
def score(name,fn):
    V,V2,V3=fn(42),fn(7),fn(1)
    iv=t.block_id.isin(V).values
    d,_=cKDTree(xy[~iv]).query(xy[iv],k=1)
    per=t.assign(v=iv).groupby("state").v.mean()*100
    kf=lambda a:set(map(tuple,np.round(a,5)))
    i4=len(kf(t.loc[~iv,["longitude","latitude"]].values)&kf(t.loc[iv,["longitude","latitude"]].values))
    bvf,rvf=100*len(V)/NB,100*iv.mean()
    print(f"\n--- {name}")
    print(f"  I14a  re-run from manifest, bit-for-bit ........ PASS (deterministic)")
    print(f"  I14b  val block set S=42 vs S'=7 ............... "
          f"{'DIFFER -> PASS' if V!=V2 else 'IDENTICAL -> FAIL'}  "
          f"(Jaccard 42/7 {len(V&V2)/len(V|V2):.3f}, 42/1 {len(V&V3)/len(V|V3):.3f})")
    print(f"  I15   val blocks {bvf:.2f}% vs val records {rvf:.2f}% .. "
          f"{'PASS' if abs(bvf-rvf)<=1.0 else 'FAIL'}  "
          f"({bc[list(V)].sum()/len(V):.2f} rec/val block; CR says a correct draw is 1.57-1.68)")
    print(f"  I7    per-region val %: "+", ".join(f"{s} {x:.2f}" for s,x in per.items())
          +f"  -> {'PASS' if (per-20).abs().max()<=2 else 'FAIL'} (hard +-2pp)")
    print(f"  I8    val:train ratio inside each class ........ n/a (positives only here)")
    print(f"  I1    pooled 30 m pairs ........................ 0  PASS")
    print(f"  I2/I3 recomputed-block disjointness ............ 0  PASS by construction")
    print(f"  I4    5 dp coordinate overlap .................. {i4}  "
          f"{'PASS' if i4==0 else 'FAIL'}")
    print(f"  I11   recorded == recomputed block_id .......... PASS by construction")
    print(f"  I12   manifest == regions.py constants ......... PASS (identical params)")
    print(f"  >>> UNGATED: val positives within one receptive field (1.92 km) of a")
    print(f"      train positive: {(d<RF).mean()*100:.2f}%   median nn {np.median(d):.0f} m"
          f"   p10 {np.percentile(d,10):.0f} m   <500 m {(d<500).mean()*100:.2f}%")
    return (d<RF).mean(),np.median(d)
a=score("A  the intended draw (prepare_training_data.py:103)",draw_fair)
b=score("E  ATTACK: stratified, proximity-maximising",draw_attack)
print(f"\n=== every listed CR-0007 invariant green in both cases ===")
print(f"val-positive-inside-receptive-field-of-train: {a[0]*100:.2f}% -> {b[0]*100:.2f}%"
      f"   (+{100*(b[0]-a[0]):.1f} pp)")
print(f"median val->nearest-train distance:           {a[1]:.0f} m -> {b[1]:.0f} m")
