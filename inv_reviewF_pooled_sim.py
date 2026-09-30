import pandas as pd, numpy as np, importlib.util
from pyproj import Transformer
from scipy.spatial import cKDTree
import prepare_training_data as P
R=["ME","NH","VT"]
ev={r:pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv") for r in R}
hab=pd.concat([ev[r][~ev[r]['nonveg_landcover'].astype(bool)].assign(_reg=r) for r in R],ignore_index=True)
print("pooled habitat rows:",len(hab))
# Check x_5070 consistency for the same coordinate across region files
k=list(zip(hab['longitude'].round(7),hab['latitude'].round(7)))
hab['_k']=[f"{a},{b}" for a,b in k]
g=hab.groupby('_k')[['x_5070','y_5070']].agg(['min','max'])
dx=(g[('x_5070','max')]-g[('x_5070','min')]).abs().max()
dy=(g[('y_5070','max')]-g[('y_5070','min')]).abs().max()
print(f"max x_5070 spread for identical coord across region files: {dx:.6f} m ; y: {dy:.6f} m")
# ==== the CR's proposed pipeline: pool -> thin once at 30m -> global blocks -> draw
th=P.thin_by_min_distance(hab,30,42)
print("pooled thin(30m,seed42) ->",len(th),"records")
print("  by state:",th['state'].value_counts().to_dict())
print("  by filing region:",th['_reg'].value_counts().to_dict())
print("  pairs<30m after:",len(cKDTree(th[['x_5070','y_5070']].values).query_pairs(30)))
# dedupe-first variant (unique coords then thin)
uniq=hab.drop_duplicates('_k')
th2=P.thin_by_min_distance(uniq,30,42)
print("dedupe-to-unique-coords(%d) then thin -> %d"%(len(uniq),len(th2)))
print("  by state:",th2['state'].value_counts().to_dict())
# global block assignment, origin (0,0)
def blocks(df,size=3000.0,origin=(0.0,0.0)):
    bx=np.floor((df['x_5070'].values-origin[0])/size).astype(int)
    by=np.floor((df['y_5070'].values-origin[1])/size).astype(int)
    return pd.Series([f"{a}_{b}" for a,b in zip(bx,by)],index=df.index)
for label,d in (("row-dup pooled thin",th),("unique-coord pooled thin",th2)):
    bid=blocks(d)
    bc=bid.value_counts()
    shuf=bc.sample(frac=1,random_state=42).index.tolist()
    target=int(round(0.2*len(d))); vb=set(); run=0
    for b in shuf:
        if run>=target: break
        vb.add(b); run+=bc[b]
    split=bid.map(lambda b:'val' if b in vb else 'train')
    d=d.copy(); d['block_id']=bid; d['split']=split
    print(f"\n--- {label}: n={len(d)} blocks={bc.size} val_blocks={len(vb)} val_frac={100*(split=='val').mean():.2f}%")
    print("   per-STATE val fraction:")
    for s in ["ME","NH","VT"]:
        sub=d[d['state']==s]
        print(f"     {s}: n={len(sub)} val={int((sub.split=='val').sum())} ({100*(sub.split=='val').mean():.2f}%)")
