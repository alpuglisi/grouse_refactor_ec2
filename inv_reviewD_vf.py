import numpy as np, pandas as pd, hashlib
from scipy.spatial import cKDTree
REG=["ME","NH","VT"]; BS=3000.0; VF=0.2; SEED=42
allp=pd.concat([pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv").assign(src=r) for r in REG],ignore_index=True)
hab=allp[~allp['nonveg_landcover'].astype(bool)]
own=hab[hab.state==hab.src].drop_duplicates(subset=["longitude","latitude","year"]).reset_index(drop=True)
def thin(df,m,seed):
    rng=np.random.default_rng(seed); o=rng.permutation(len(df)); c=df[['x_5070','y_5070']].values[o]
    k=np.zeros(len(df),bool); kept=[]; t=None
    for i,pt in enumerate(c):
        if t is None or t.query(pt,k=1)[0]>=m: kept.append(pt); k[o[i]]=True; t=cKDTree(np.array(kept))
    return df[k].copy()
pos=thin(own,30.0,SEED)
ids=pd.Series([f"{a}_{b}" for a,b in zip(np.floor(pos.x_5070/BS).astype(int),np.floor(pos.y_5070/BS).astype(int))],index=pos.index)
cnt=ids.value_counts(); shuf=cnt.sample(frac=1,random_state=SEED).index.tolist()
tgt=int(round(VF*len(pos))); val=set(); run=0
for b in shuf:
    if run>=tgt: break
    val.add(b); run+=cnt[b]
split=ids.map(lambda b:'val' if b in val else 'train')
print(f"record-level val fraction: {100*(split=='val').mean():.2f}%")
tblo=pd.DataFrame({'block_id':ids,'split':split}).drop_duplicates('block_id')
print(f"BLOCK-level val fraction (what generate_negatives.py:229 computes): {100*(tblo['split']=='val').mean():.2f}%")
print(f"occupied blocks: {len(tblo)}, val blocks: {int((tblo['split']=='val').sum())}")
neg=pd.concat([pd.read_csv(f"data/negatives/negatives_{r}.csv") for r in REG],ignore_index=True)
nid=[f"{a}_{b}" for a,b in zip(np.floor(neg.x_5070/BS).astype(int),np.floor(neg.y_5070/BS).astype(int))]
tab=dict(zip(tblo.block_id,tblo.split))
hit=sum(1 for b in nid if b in tab)
print(f"negatives landing in a POSITIVE-bearing global block: {hit}/{len(nid)} ({100*hit/len(nid):.1f}%) "
      f"-> {100*(1-hit/len(nid)):.1f}% are hash-split at the BLOCK-level fraction")
for vf,lbl in ((0.2,"record-level 20%"),((tblo['split']=='val').mean(),"block-level")):
    def h(b): return 'val' if int(hashlib.md5(f"{SEED}:{b}".encode()).hexdigest(),16)%10000<vf*10000 else 'train'
    s=[tab.get(b) or h(b) for b in nid]
    print(f"  negatives' val fraction using {lbl} ({vf:.3f}): {100*np.mean(np.array(s)=='val'):.2f}%")
