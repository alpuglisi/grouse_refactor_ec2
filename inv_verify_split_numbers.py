"""Verify every number that will appear in the split CRs. Read-only.
Several v3 figures did not reproduce under review; nothing goes into a
draft unless it is measured here."""
import numpy as np, pandas as pd, rasterio
from pyproj import Transformer
from scipy.spatial import cKDTree
from rasterio.transform import rowcol
from grouse_data import GrouseData
from prepare_training_data import thin_by_min_distance
R=["ME","NH","VT"]; data=GrouseData()
t=Transformer.from_crs("EPSG:4326","EPSG:5070",always_xy=True)

# ---- reassignment quantities (v3's "1,012" reproduced under no definition)
ev={r:pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv",low_memory=False) for r in R}
rows=[]
for r in R:
    d=ev[r]
    if 'nonveg_landcover' in d: d=d[~d.nonveg_landcover.astype(bool)]
    d=d[["longitude","latitude","state"]].copy(); d["src"]=r; rows.append(d)
hab=pd.concat(rows,ignore_index=True)
hab["key"]=hab.longitude.round(5).astype(str)+","+hab.latitude.round(5).astype(str)
print("=== reassignment (habitat records) ===")
print(f"  habitat rows pooled                      : {len(hab)}")
print(f"  unique coords                            : {hab.key.nunique()}")
print(f"  rows whose src != state                  : {int((hab.src!=hab.state).sum())}")
g=hab.groupby('key')
print(f"  coords present in >1 region file         : {int((g.src.nunique()>1).sum())}")
only_foreign=g.apply(lambda d: (d.src!=d.state).all(), include_groups=False)
print(f"  coords present ONLY in a foreign file    : {int(only_foreign.sum())}")

# ---- duplicate positives: cross-split vs same-split
th=pd.concat([data[r].thinned.assign(src=r) for r in R],ignore_index=True)
th["key"]=th.longitude.round(5).astype(str)+","+th.latitude.round(5).astype(str)
d=th.groupby("key").split.agg(lambda s:set(s))
both=sum(1 for s in d if {"train","val"}<=s); same=sum(1 for k,s in d.items() if len(s)==1 and (th.key==k).sum()>1)
print(f"\n=== duplicate positive coordinates ===")
print(f"  coords in BOTH train and val (I4)        : {both}")
print(f"  duplicated coords inside ONE split       : {same}")

# ---- I4 negative half today
ng=pd.concat([pd.concat([data[r].negatives(s).assign(split=s) for s in("train","val")]) for r in R],ignore_index=True)
ng["key"]=ng.longitude.round(5).astype(str)+","+ng.latitude.round(5).astype(str)
tr=set(ng[ng.split=="train"].key); va=set(ng[ng.split=="val"].key)
print(f"  NEGATIVE train/val coord collisions      : {len(tr&va)}   (I4 neg half)")

# ---- geometric window violations, today vs after partition
print(f"\n=== full-window violations (evt), today vs state-partitioned ===")
for r in R:
    src=rasterio.open(data[r].latest_raster_path("evt"))
    tt=Transformer.from_crs("EPSG:4326",src.crs,always_xy=True)
    cur=data[r].thinned
    for label,df in (("as-filed",cur),("state==region",cur[cur.state==r])):
        x,y=tt.transform(df.longitude.values,df.latitude.values)
        rr,cc=rowcol(src.transform,x,y); rr,cc=np.asarray(rr),np.asarray(cc)
        for half,nm in ((32,"64px"),(40,"80px (jitter 8)")):
            bad=((rr-half<0)|(cc-half<0)|(rr+half>src.height)|(cc+half>src.width)).sum()
            print(f"  {r} {label:14s} {nm:16s}: {int(bad):3d} of {len(df)}")
    src.close()
