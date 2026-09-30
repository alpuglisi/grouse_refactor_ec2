import pandas as pd, numpy as np
from scipy.stats import ks_2samp
import prepare_training_data as P
R=["ME","NH","VT"]
a=pd.concat([pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv").assign(_reg=r) for r in R],ignore_index=True)
own=a[(~a['nonveg_landcover'].astype(bool))&(a.state==a._reg)].drop_duplicates(subset=['longitude','latitude'])
base=P.thin_by_min_distance(own,30,42).reset_index(drop=True)
SZ=3000.0
base['blk']=[f"{x}_{y}" for x,y in zip(np.floor(base.x_5070/SZ).astype(int),np.floor(base.y_5070/SZ).astype(int))]
def correct(seed,vf=0.2):
    bc=base['blk'].value_counts(); order=bc.sample(frac=1,random_state=seed).index.tolist()
    t=int(round(vf*len(base))); vb=set(); run=0
    for b in order:
        if run>=t: break
        vb.add(b); run+=bc[b]
    return vb
def attack_east(seed,vf=0.2):
    vb=set(); rng=np.random.default_rng(seed)
    for r in R:
        sub=base[base.state==r]; bc=sub['blk'].value_counts()
        bx=pd.Series({b:int(b.split('_')[0]) for b in bc.index}); cut=bx.median()
        elig=[b for b in bc.index if bx[b]>=cut]; rng.shuffle(elig)
        t=int(round(vf*len(sub))); run=0
        for b in elig:
            if run>=t: break
            vb.add(b); run+=bc[b]
    return vb
print("=== I7's new hard +/-2pp per-region gate: CORRECT draw over 50 seeds ===")
w=[]
for s in range(50):
    vb=correct(s); sp=base['blk'].map(lambda b:'val' if b in vb else 'train')
    w.append(max(abs(100*(sp[base.state==r]=='val').mean()-20) for r in R))
w=np.array(w)
print(f"  worst per-region deviation: min {w.min():.2f} median {np.median(w):.2f} p95 {np.percentile(w,95):.2f} max {w.max():.2f} pp")
print(f"  legitimate seeds a HARD 2 pp gate would REJECT: {int((w>2).sum())}/50 = {100*(w>2).mean():.0f}%")
print(f"  ... a 3 pp gate: {int((w>3).sum())}/50   a 4 pp gate: {int((w>4).sum())}/50")
print("\n=== covariate shift the acceptance set does not measure (KS val vs train) ===")
feats=['evh','evc','slope' if 'slope' in base.columns else 'evt','spatial_density','longitude']
feats=[f for f in feats if f in base.columns]
for tag,fn in [("CORRECT",correct),("ATTACK east",attack_east)]:
    vb=fn(42); sp=base['blk'].map(lambda b:'val' if b in vb else 'train')
    out=[]
    for f in feats:
        v=base.loc[sp=='val',f].dropna(); t=base.loc[sp=='train',f].dropna()
        if len(v)>10 and len(t)>10: out.append(f"{f} D={ks_2samp(v,t).statistic:.3f}")
    print(f"  {tag:12} " + "  ".join(out))
