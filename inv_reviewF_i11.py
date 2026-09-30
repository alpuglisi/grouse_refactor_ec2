"""I11: recorded block_id vs block id recomputed from lon/lat.
Is the recomputation stable, or does reprojection put boundary points in
different blocks than the stored x_5070 does?"""
import pandas as pd, numpy as np
from pyproj import Transformer
R=["ME","NH","VT"]
T=Transformer.from_crs("EPSG:4326","EPSG:5070",always_xy=True)
tot=0; diff=0; maxd=0.0
for r in R:
    for p in [f"data/pipeline/thinned_positives_{r}.csv",f"data/negatives/negatives_{r}.csv"]:
        d=pd.read_csv(p)
        x,y=T.transform(d.longitude.values,d.latitude.values)
        dx=np.abs(x-d.x_5070.values); dy=np.abs(y-d.y_5070.values)
        maxd=max(maxd,dx.max(),dy.max())
        a=np.floor(d.x_5070.values/3000).astype(int); b=np.floor(d.y_5070.values/3000).astype(int)
        a2=np.floor(x/3000).astype(int); b2=np.floor(y/3000).astype(int)
        n=int(((a!=a2)|(b!=b2)).sum())
        tot+=len(d); diff+=n
print(f"records {tot}: recomputed-vs-stored 3km block mismatches {diff}; max coord delta {maxd:.6e} m")
# distance of each record to the nearest 3km block edge
allr=pd.concat([pd.read_csv(f"data/pipeline/thinned_positives_{r}.csv") for r in R],ignore_index=True)
ex=np.minimum(allr.x_5070%3000, 3000-allr.x_5070%3000)
ey=np.minimum(allr.y_5070%3000, 3000-allr.y_5070%3000)
e=np.minimum(ex,ey)
print(f"min distance from a record to a 3km block edge: {e.min():.4f} m ; records within 1 m of an edge: {int((e<1).sum())}")
