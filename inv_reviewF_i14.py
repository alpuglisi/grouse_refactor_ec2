"""Round 3: does I14/I15 kill Break 1, and is I14 closed by construction?"""
import pandas as pd, numpy as np
import prepare_training_data as P
R=["ME","NH","VT"]
ev={r:pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv").assign(_reg=r) for r in R}
def pool(order):
    a=pd.concat([ev[r] for r in order],ignore_index=True)
    own=a[(~a['nonveg_landcover'].astype(bool))&(a.state==a._reg)].drop_duplicates(subset=['longitude','latitude'])
    return P.thin_by_min_distance(own,30,42)
base=pool(R)
print("pooled positives:",len(base))

def draw(df,seed,shuffle=True,size=3000.0,vf=0.2):
    bx=np.floor(df['x_5070'].values/size).astype(int); by=np.floor(df['y_5070'].values/size).astype(int)
    bid=pd.Series([f"{a}_{b}" for a,b in zip(bx,by)],index=df.index)
    bc=bid.value_counts()
    blocks = bc.sample(frac=1,random_state=seed).index.tolist() if shuffle else bc.index.tolist()
    t=int(round(vf*len(df))); vb=set(); run=0
    for b in blocks:
        if run>=t: break
        vb.add(b); run+=bc[b]
    return bid, bid.map(lambda b:'val' if b in vb else 'train'), vb, bc

def report(tag,df,bid,split,vb,bc):
    nrec=100*(split=='val').mean(); nblk=100*len(vb)/bc.size
    print(f"  {tag:34} val blocks {len(vb):4}/{bc.size}  block-frac {nblk:6.2f}%  "
          f"record-frac {nrec:6.2f}%  I15 delta {abs(nblk-nrec):5.2f} pp  "
          f"{'PASS' if abs(nblk-nrec)<=1.0 else 'FAIL'}   rec/valblk {(split=='val').sum()/len(vb):.2f}")

print("\n=== I15 vs Break 1 ===")
for sh,tag in [(True,"CORRECT (shuffled)"),(False,"BREAK 1 (shuffle deleted)")]:
    bid,sp,vb,bc=draw(base,42,sh); report(tag,base,bid,sp,vb,bc)

print("\n=== I14(ii) seed-variance vs Break 1 ===")
for sh,tag in [(True,"CORRECT"),(False,"BREAK 1")]:
    sets=[draw(base,s,sh)[2] for s in (42,7)]
    same = sets[0]==sets[1]
    print(f"  {tag:10} val block set seed42 == seed7 ? {same}   -> I14(ii) {'FAIL (caught)' if same else 'PASS'}")

print("\n=== I15 false-positive calibration: CORRECT draw over 50 seeds ===")
d=[]
for s in range(50):
    bid,sp,vb,bc=draw(base,s,True)
    d.append(abs(100*len(vb)/bc.size - 100*(sp=='val').mean()))
d=np.array(d)
print(f"  |block-frac - record-frac| over 50 seeds: min {d.min():.2f}  median {np.median(d):.2f}  "
      f"p95 {np.percentile(d,95):.2f}  max {d.max():.2f} pp")
print(f"  seeds a 1 pp I15 gate would REJECT as defective: {int((d>1.0).sum())}/50 = {100*(d>1.0).mean():.0f}%")

print("\n=== I14(i): is the manifest sufficient to reproduce the split? ===")
import itertools
for order in itertools.permutations(R):
    p=pool(list(order))
    bid,sp,vb,bc=draw(p,42,True)
    print(f"  concat order {order}: n={len(p)} val blocks={len(vb)} "
          f"first5={sorted(vb)[:3]} record-frac={100*(sp=='val').mean():.2f}%")
sets={}
for order in itertools.permutations(R):
    p=pool(list(order)); sets[order]=draw(p,42,True)[2]
u={frozenset(v) for v in sets.values()}
print(f"  distinct val block sets across the 6 region orders, SAME manifest: {len(u)}")
