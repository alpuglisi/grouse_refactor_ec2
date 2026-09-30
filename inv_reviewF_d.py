import pandas as pd, numpy as np
from pyproj import Transformer
T=Transformer.from_crs("EPSG:4326","EPSG:5070",always_xy=True)
R=["ME","NH","VT"]
def bid(df,size):
    x,y=T.transform(df['longitude'].values,df['latitude'].values)
    return set(zip(np.floor(x/size).astype(int),np.floor(y/size).astype(int)))
def blk(df,size):
    x,y=T.transform(df['longitude'].values,df['latitude'].values)
    return pd.Series(list(zip(np.floor(x/size).astype(int),np.floor(y/size).astype(int))),index=df.index)
for size in (30000.0,):
    print(f"--- (d) support, {size/1000:.0f} km blocks, origin (0,0) ---")
    for r in R:
        p=pd.read_csv(f"data/pipeline/thinned_positives_{r}.csv")
        n=pd.read_csv(f"data/negatives/negatives_{r}.csv")
        bp=bid(p,size); bn=bid(n,size)
        frac=len(bp-bn)/len(bp)
        print(f"  {r}: pos blocks {len(bp)}, neg blocks {len(bn)}, pos-blocks with no neg = {len(bp-bn)} -> {frac:.4f}")
        # reverse direction
        print(f"      neg-blocks with no pos = {len(bn-bp)} -> {len(bn-bp)/len(bn):.4f}")
# val_fraction block-level rate at :243
print("\n--- :243 val_fraction (block-level) ---")
allb=[]
for r in R:
    b=pd.read_csv(f"data/pipeline/block_assignments_{r}.csv")
    print(f"  {r}: {len(b)} blocks, val share {(b['split']=='val').mean():.4f}")
    allb.append(b)
# global equivalent: recompute global block ids on pooled thinned positives
tp=pd.concat([pd.read_csv(f"data/pipeline/thinned_positives_{r}.csv").assign(_reg=r) for r in R],ignore_index=True)
tp['_gb']=blk(tp,3000.0)
gb=tp.drop_duplicates('_gb')[['_gb','split']]
print(f"  GLOBAL (recomputed 3km ids on pooled thinned positives): {len(gb)} blocks, val share {(gb['split']=='val').mean():.4f}")
# share of candidates in a block holding no positive
from scipy.spatial import cKDTree
posblocks=set(tp['_gb'])
tot=0; miss=0
for r in R:
    c=pd.read_csv(f"data/negatives/negatives_{r}.csv")
    c['_gb']=blk(c,3000.0)
    tot+=len(c); miss+=int((~c['_gb'].isin(posblocks)).sum())
print(f"  final negatives in a 3km block holding no pooled positive: {miss}/{tot} = {100*miss/tot:.1f}%")
# on the eligible candidate pool
import prepare_training_data as P
tot=0;miss=0
for r in R:
    c=pd.read_csv(f"data/negatives/gbif_negatives_{r}.csv")
    k=c[['longitude','latitude']].round(5); c=c.loc[~k.duplicated()].copy()
    c['_gb']=blk(c,3000.0)
    tot+=len(c); miss+=int((~c['_gb'].isin(posblocks)).sum())
print(f"  deduped candidates in a 3km block holding no pooled positive: {miss}/{tot} = {100*miss/tot:.1f}%")
