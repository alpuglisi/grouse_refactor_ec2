import os
os.chdir('/home/ec2-user/grouse2')
import pandas as pd, numpy as np, rasterio
from pyproj import Transformer
import grouse_data as G
cfg=G.DataConfig(); rd=G.RegionData('NH',cfg)
P=pd.concat([pd.read_csv(f'data/pipeline/{p}_positives_NH.csv') for p in ['train','val']],ignore_index=True)
d=P.sample(1500,random_state=3); lons,lats=d['longitude'].values,d['latitude'].values
def s(feat,y):
    with rasterio.open(rd.path("raster",feature=feat,year=y)) as src:
        tr=Transformer.from_crs("EPSG:4326",src.crs,always_xy=True)
        xs,ys=tr.transform(lons,lats)
        return np.array([a[0] for a in src.sample(list(zip(xs,ys)))])
for feat in ['evt','sclass','evh','fdist','nlcd']:
    ys=rd.raster_years(feat)
    a=s(feat,ys[0]); 
    for y in ys[1:]:
        b=s(feat,y)
        print(f"{feat}: {ys[0]} vs {y}: differ at {100*(a!=b).mean():.2f}% of 1500 points")
