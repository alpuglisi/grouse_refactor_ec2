import numpy as np, pandas as pd, rasterio
from pyproj import Transformer
src=rasterio.open("data/landfire/NH_2023_evt.tif"); H,W=src.shape
print("NH evt bounds:",src.bounds,"shape",src.shape)
T=Transformer.from_crs("EPSG:4326",src.crs,always_xy=True)
df=pd.read_csv("data/pipeline/thinned_positives_NH.csv")
x,y=T.transform(df.longitude.values,df.latitude.values)
rows,cols=rasterio.transform.rowcol(src.transform,x,y); rows=np.asarray(rows);cols=np.asarray(cols)
for half in (32,40):
    bad=(rows-half<0)|(rows+half>H)|(cols-half<0)|(cols+half>W)
    print(f"\nhalf={half}: {bad.sum()} violations")
    print(df.loc[bad,["longitude","latitude","state","year","split"]].to_string())
    print("  rows/cols:",list(zip(rows[bad],cols[bad])))
# also: the whole evaluated_sightings_NH set, and state==NH records from all files
allp=pd.concat([pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv") for r in ("ME","NH","VT")],ignore_index=True)
nh=allp[allp.state=="NH"].drop_duplicates(subset=["longitude","latitude","year"])
x,y=T.transform(nh.longitude.values,nh.latitude.values)
rows,cols=rasterio.transform.rowcol(src.transform,x,y); rows=np.asarray(rows);cols=np.asarray(cols)
for half in (32,40):
    bad=(rows-half<0)|(rows+half>H)|(cols-half<0)|(cols+half>W)
    print(f"\nALL state==NH records (n={len(nh)}), half={half}: {bad.sum()} would violate after the partition")
    if bad.sum(): print(nh.loc[bad,["longitude","latitude","state","year"]].drop_duplicates().to_string())
