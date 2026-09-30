import pandas as pd, numpy as np
from pyproj import Transformer
from scipy.spatial import cKDTree
import prepare_training_data as P
T=Transformer.from_crs("EPSG:4326","EPSG:5070",always_xy=True)
R=["ME","NH","VT"]
def blk(df,size=3000.0):
    x,y=T.transform(df['longitude'].values,df['latitude'].values)
    return pd.Series(list(zip(np.floor(x/size).astype(int),np.floor(y/size).astype(int))),index=df.index)
tp=pd.concat([pd.read_csv(f"data/pipeline/thinned_positives_{r}.csv") for r in R],ignore_index=True)
posblocks=set(blk(tp))
# per-region block table coverage (what the code actually uses: region-local ids)
for r in R:
    b=pd.read_csv(f"data/pipeline/block_assignments_{r}.csv")
    c=pd.read_csv(f"data/negatives/negatives_{r}.csv")
    print(f"{r}: final negatives whose recorded block_id is NOT in block_assignments_{r}: "
          f"{int((~c['block_id'].isin(set(b['block_id']))).sum())}/{len(c)} "
          f"= {100*(~c['block_id'].isin(set(b['block_id']))).mean():.1f}%")
tot=0;miss=0
for r in R:
    c=pd.read_csv(f"data/negatives/gbif_negatives_{r}.csv")
    n0=len(c)
    c=c[~(c['coord_uncertainty_m']>1000).fillna(False)].copy()
    k=c[['longitude','latitude']].round(5); c=c.loc[~k.duplicated()].copy()
    c['x_5070'],c['y_5070']=T.transform(c['longitude'].values,c['latitude'].values)
    c=P.thin_by_min_distance(c,30,42)
    ev=pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv")
    px,py=T.transform(ev['longitude'].values,ev['latitude'].values)
    d,_=cKDTree(np.c_[px,py]).query(c[['x_5070','y_5070']].values,k=1)
    c=c[d>300].copy()
    c['_gb']=blk(c)
    tot+=len(c); miss+=int((~c['_gb'].isin(posblocks)).sum())
    print(f"  {r}: post-buffer pool {len(c)}, in a no-positive 3km block: {int((~c['_gb'].isin(posblocks)).sum())} = {100*(~c['_gb'].isin(posblocks)).mean():.1f}%")
print(f"POOLED post-buffer: {miss}/{tot} = {100*miss/tot:.1f}%")
