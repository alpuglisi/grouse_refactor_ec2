"""Reviewer D vs CR-0007: per-region validation fraction is ungated (I7 is per CLASS only)."""
import numpy as np, pandas as pd, hashlib
from scipy.spatial import cKDTree
REG=["ME","NH","VT"]; BS=3000.0; ORIGIN=(0.0,0.0); VF=0.2
allp=pd.concat([pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv").assign(src=r) for r in REG],ignore_index=True)
hab=allp[~allp['nonveg_landcover'].astype(bool)]
own=hab[hab.state==hab.src].drop_duplicates(subset=["longitude","latitude","year"]).reset_index(drop=True)
def thin(df,m,seed):
    rng=np.random.default_rng(seed); o=rng.permutation(len(df)); c=df[['x_5070','y_5070']].values[o]
    k=np.zeros(len(df),bool); kept=[]; t=None
    for i,pt in enumerate(c):
        if t is None or t.query(pt,k=1)[0]>=m: kept.append(pt); k[o[i]]=True; t=cKDTree(np.array(kept))
    return df[k].copy()
def gid(df):
    return pd.Series([f"{a}_{b}" for a,b in zip(np.floor((df.x_5070.values-ORIGIN[0])/BS).astype(int),
                                                np.floor((df.y_5070.values-ORIGIN[1])/BS).astype(int))],index=df.index)
print("seed | pooled n | pooled val% | ME val% | NH val% | VT val% | ME n | NH n | VT n")
for seed in (42,1,2,3,7,13,99,2024):
    pos=thin(own,30.0,seed); ids=gid(pos)
    cnt=ids.value_counts(); shuf=cnt.sample(frac=1,random_state=seed).index.tolist()
    tgt=int(round(VF*len(pos))); val=set(); run=0
    for b in shuf:
        if run>=tgt: break
        val.add(b); run+=cnt[b]
    split=ids.map(lambda b:'val' if b in val else 'train')
    row=[f"{seed:4d}",f"{len(pos):8d}",f"{100*(split=='val').mean():10.2f}"]
    for r in REG:
        m=(pos.state==r).values
        row.append(f"{100*(split[m]=='val').mean():7.2f}")
    for r in REG: row.append(f"{int((pos.state==r).sum()):5d}")
    print(" | ".join(row))
