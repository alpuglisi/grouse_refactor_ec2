import numpy as np, pandas as pd
from pyproj import Transformer
from scipy.spatial import cKDTree
REG=["ME","NH","VT"]
T=Transformer.from_crs("EPSG:4326","EPSG:5070",always_xy=True)
cs=[]
for r in REG:
    c=pd.read_csv(f"data/negatives/gbif_negatives_{r}.csv")
    c=c[c.coord_uncertainty_m.fillna(0)<=1000]
    c=c.loc[~c[['longitude','latitude']].round(5).duplicated()]
    x,y=T.transform(c.longitude.values,c.latitude.values); c['x']=x; c['y']=y; c['reg']=r
    cs.append(c[['x','y','reg','longitude','latitude']])
c=pd.concat(cs,ignore_index=True)
print("pooled unique candidates after hygiene:",len(c), c.reg.value_counts().to_dict())
t=cKDTree(c[['x','y']].values); p=t.query_pairs(30.0,output_type='ndarray')
rg=c.reg.values
print(f"candidate pairs <30 m pooled: {len(p)}; cross-STATE: {(rg[p[:,0]]!=rg[p[:,1]]).sum()}; same-state: {(rg[p[:,0]]==rg[p[:,1]]).sum()}")
# duplicate coordinates WITHIN each class/split of the selected sets (double weighting)
for lbl,paths in (("positives",[f"data/pipeline/thinned_positives_{r}.csv" for r in REG]),
                  ("negatives",[f"data/negatives/negatives_{r}.csv" for r in REG])):
    d=pd.concat([pd.read_csv(p) for p in paths],ignore_index=True)
    k=d[['x_5070','y_5070']].round(3)
    print(f"{lbl}: {len(d)} rows, duplicated coords within the same split: "
          f"{int(pd.concat([k,d['split']],axis=1).duplicated().sum())}; any split: {int(k.duplicated().sum())}")
