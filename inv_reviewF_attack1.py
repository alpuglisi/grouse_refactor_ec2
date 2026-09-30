"""ATTACK 1: pooled block draw with the shuffle dropped (an easy regression
while rewriting assign_spatial_blocks).  Does the I1-I9 + (a)-(d) set catch it?"""
import pandas as pd, numpy as np
from pyproj import Transformer
from scipy.spatial import cKDTree
import prepare_training_data as P
T=Transformer.from_crs("EPSG:4326","EPSG:5070",always_xy=True)
R=["ME","NH","VT"]
ev={r:pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv") for r in R}
# emulate the post-partition per-region inputs: own-state rows only
allrows=pd.concat([ev[r].assign(_reg=r) for r in R],ignore_index=True)
own=allrows[allrows.state==allrows._reg]
own=own.drop_duplicates(subset=['longitude','latitude'])
hab=own[~own['nonveg_landcover'].astype(bool)].copy()
pool=P.thin_by_min_distance(hab,30,42)
print("pooled positives after partition+thin:",len(pool),pool['state'].value_counts().to_dict())
def draw(df,shuffle=True,size=3000.0,vf=0.2,seed=42):
    bx=np.floor(df['x_5070'].values/size).astype(int); by=np.floor(df['y_5070'].values/size).astype(int)
    bid=pd.Series([f"{a}_{b}" for a,b in zip(bx,by)],index=df.index)
    bc=bid.value_counts()
    blocks = bc.sample(frac=1,random_state=seed).index.tolist() if shuffle else bc.index.tolist()
    t=int(round(vf*len(df))); vb=set(); run=0
    for b in blocks:
        if run>=t: break
        vb.add(b); run+=bc[b]
    return bid, bid.map(lambda b:'val' if b in vb else 'train')
for shuffle in (True,False):
    bid,split=draw(pool,shuffle)
    d=pool.copy(); d['block_id']=bid; d['split']=split
    lbl="CORRECT (shuffled)" if shuffle else "ATTACK (shuffle dropped)"
    print(f"\n=== {lbl} ===")
    print(f"  I6 pooled positive count: {len(d)}   (required 6230 +/- 2% = 6105..6355)")
    print(f"  I7 positive val fraction: {100*(d.split=='val').mean():.2f}%  (required 20 +/- 1)")
    print(f"  I1 pairs<30m: {len(cKDTree(d[['x_5070','y_5070']].values).query_pairs(30))}")
    kt=set(zip(d[d.split=='train'].longitude.round(5),d[d.split=='train'].latitude.round(5)))
    kv=set(zip(d[d.split=='val'].longitude.round(5),d[d.split=='val'].latitude.round(5)))
    print(f"  I4 pos train∩val: {len(kt&kv)}")
    g=d.groupby('block_id')['split'].nunique(); print(f"  I2 blocks with both: {int((g>1).sum())}")
    print("  PER-REGION validation fraction (NOT in the acceptance set):")
    for s in R:
        sub=d[d.state==s]
        print(f"     {s}: n={len(sub):5} val={int((sub.split=='val').sum()):5} ({100*(sub.split=='val').mean():6.2f}%)  val blocks={sub[sub.split=='val'].block_id.nunique()}")
    # spatial spread of the val set
    v=d[d.split=='val']
    print(f"  val-set 3km blocks: {v.block_id.nunique()};  mean records/val block {len(v)/v.block_id.nunique():.2f}"
          f" vs train {len(d)-len(v)} / {d[d.split=='train'].block_id.nunique()} = {(len(d)-len(v))/d[d.split=='train'].block_id.nunique():.2f}")
