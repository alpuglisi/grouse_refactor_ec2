import os
os.chdir('/home/ec2-user/grouse2')
import pandas as pd, numpy as np, rasterio
from pyproj import Transformer
import grouse_data as G
cfg=G.DataConfig(); rd=G.RegionData('NH',cfg)
P=pd.concat([pd.read_csv(f'data/pipeline/{p}_positives_NH.csv') for p in ['train','val']],ignore_index=True)
d=P.sample(800,random_state=3)
lons,lats=d['longitude'].values,d['latitude'].values
for feat in ['carbon_dwn','balive','qmd','tpa_live','tcc','tsd','nlcd','road_dist']:
    out=[]
    for y in rd.raster_years(feat):
        path=rd.path("raster",feature=feat,year=y)
        with rasterio.open(path) as src:
            tr=Transformer.from_crs("EPSG:4326",src.crs,always_xy=True)
            xs,ys=tr.transform(lons,lats)
            v=np.array([a[0] for a in src.sample(list(zip(xs,ys)))],dtype=float)
            nd=src.nodata
        if nd is not None: v[v==nd]=np.nan
        out.append((y,np.nanmean(v),np.nanstd(v)))
    print(f"\n{feat}: (same 800 NH points, each vintage)")
    base=[m for y,m,s in out if y==2022][0]
    for y,m,s in out:
        print(f"   {y}: mean={m:10.2f} sd={s:9.2f}  vs2022={100*(m-base)/base if base else 0:+7.2f}%")
