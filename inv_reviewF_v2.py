import pandas as pd, numpy as np, rasterio, os, collections
from grouse_data import GrouseData, RASTER_FEATURES
from pyproj import Transformer
gd=GrouseData(); R=["ME","NH","VT"]
print("=== window-fit drop on RAW candidate pool ===")
for n in (64,80):
    for r in R:
        rd=gd[r]; d=pd.read_csv(f"data/negatives/gbif_negatives_{r}.csv")
        fail=np.zeros(len(d),dtype=bool)
        for feat in RASTER_FEATURES:
            years=rd.raster_years(feat)
            yr=d['year'].fillna(max(years)).astype(int).values
            res=np.array([min(years,key=lambda y:(abs(y-v),y)) for v in yr])
            for y in sorted(set(res)):
                p=rd.path("raster",feature=feat,year=int(y))
                if not os.path.exists(p): continue
                with rasterio.open(p) as src:
                    inv=~src.transform; H,W=src.height,src.width; crs=src.crs
                m=res==y
                T=Transformer.from_crs("EPSG:4326",crs,always_xy=True)
                x,y2=T.transform(d.loc[m,'longitude'].values,d.loc[m,'latitude'].values)
                c,ro=inv*(x,y2); c=np.floor(c).astype(int); ro=np.floor(ro).astype(int)
                h=n//2
                bad=(c-h<0)|(ro-h<0)|(c-h+n>W)|(ro-h+n>H)
                fail[np.where(m)[0][bad]]=True
        print(f"  window {n}: {r}: {int(fail.sum())} of {len(d)} raw candidates lack a full window")
