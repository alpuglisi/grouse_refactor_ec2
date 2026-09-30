"""Calibrate the replacement support gate for CR-0007 assertion (d).
Measures the per-region 30 km occupied-block pos-only fraction under a
FAIR negative draw and a SPATIALLY SKEWED one, across seeds, so the
threshold is set against a sampling distribution rather than one
realisation. Read-only."""
import numpy as np, pandas as pd
from pyproj import Transformer
from grouse_data import GrouseData
from prepare_training_data import thin_by_min_distance

R=["ME","NH","VT"]; BLK=30000; data=GrouseData()
t=Transformer.from_crs("EPSG:4326","EPSG:5070",always_xy=True)
def xy(df):
    x,y=t.transform(df.longitude.values,df.latitude.values); return x,y
def blocks(df):
    x,y=xy(df); return set(zip(np.floor(x/BLK).astype(int),np.floor(y/BLK).astype(int)))
def posonly(p,n):
    P,N=blocks(p),blocks(n); return len(P-N)/max(len(P),1)

# positives: state-partitioned, pooled 30 m thin
pos=[]
for r in R:
    d=data[r].thinned
    d=d[d.state==r][["longitude","latitude","state"]]
    pos.append(d)
pos=pd.concat(pos,ignore_index=True).drop_duplicates(["longitude","latitude"])
pos["x_5070"],pos["y_5070"]=xy(pos)
pos=thin_by_min_distance(pos,30,42)
print("pooled positives after state partition + 30 m thin:",len(pos))

# negative candidate pool, pooled, light hygiene
cand=[]
for r in R:
    c=pd.read_csv(f"data/negatives/gbif_negatives_{r}.csv",low_memory=False)
    c=c[c.coord_uncertainty_m.fillna(0)<=1000]
    cand.append(c[["longitude","latitude","state"]])
cand=pd.concat(cand,ignore_index=True).drop_duplicates(["longitude","latitude"])
print("pooled negative candidates:",len(cand))

print(f"\n{'seed':>4} {'draw':<10} "+" ".join(f"{r:>8}" for r in R))
rows={"fair":[], "skew":[]}
for seed in (42,1,7,2024,99):
    rng=np.random.default_rng(seed)
    for mode in ("fair","skew"):
        vals=[]
        for r in R:
            p=pos[pos.state==r]; pool=cand[cand.state==r]
            if mode=="skew":                      # southern half only
                pool=pool[pool.latitude<=pool.latitude.median()]
            n=min(len(p),len(pool))
            take=pool.iloc[rng.choice(len(pool),size=n,replace=False)]
            vals.append(posonly(p,take))
        rows[mode].append(vals)
        print(f"{seed:>4} {mode:<10} "+" ".join(f"{v:8.4f}" for v in vals))
print()
for mode in ("fair","skew"):
    a=np.array(rows[mode])
    print(f"{mode:<5} per-region  min {a.min(0).round(4)}  max {a.max(0).round(4)}  overall max {a.max():.4f} min {a.min():.4f}")
fa,sk=np.array(rows["fair"]),np.array(rows["skew"])
# pre-CR, today's per-region files
pre=[posonly(data[r].thinned, data[r].negatives("all")) for r in R]
print(f"\npre-CR (today's per-region files): {[round(v,4) for v in pre]}")
print(f"\nusable gate window: > fair max ({fa.max():.4f})  and  < min(skew min {sk.min():.4f}, pre-CR min {min(pre):.4f})")
