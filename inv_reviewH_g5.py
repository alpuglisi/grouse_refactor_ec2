"""Verify CR-0008 G5 / Impact training-window numbers."""
import numpy as np, pandas as pd, rasterio
from rasterio.windows import Window
from pyproj import Transformer
IMG=64; H2=IMG//2
def scan(reg,df,tag):
    with rasterio.open(f"data/landfire/{reg}_2025_nlcd.tif") as s:
        tr=Transformer.from_crs("EPSG:4326",s.crs,always_xy=True)
        x,y=tr.transform(df.longitude.values,df.latitude.values)
        inv=~s.transform
        res=[]
        for xi,yi in zip(x,y):
            c,r=inv*(xi,yi); c,r=int(np.floor(c)),int(np.floor(r))
            a=s.read(1,window=Window(c-H2,r-H2,IMG,IMG),boundless=True,fill_value=-9999)
            ctr=s.read(1,window=Window(c,r,1,1),boundless=True,fill_value=-9999)[0,0]
            res.append(((a==-9999).mean(),ctr==-9999))
    f=np.array([r[0] for r in res]); ctr=np.array([r[1] for r in res])
    print(f"  {reg} {tag:14s} n={len(df):5d}  any nodata in 64px window: {(f>0).sum():3d}"
          f"   >10%: {(f>0.10).sum():3d}   =100%: {(f==1.0).sum():2d}"
          f"   centre px nodata: {ctr.sum():2d}   max frac {f.max():.2f}")
for reg in ("ME","NH","VT"):
    for kind,path in (("train neg",f"data/negatives/train_negatives_{reg}.csv"),
                      ("val neg",f"data/negatives/val_negatives_{reg}.csv"),
                      ("train pos",f"data/pipeline/train_positives_{reg}.csv"),
                      ("val pos",f"data/pipeline/val_positives_{reg}.csv")):
        scan(reg,pd.read_csv(path),kind)
