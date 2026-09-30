import numpy as np, pandas as pd, rasterio, sys
from pyproj import Transformer
IMG=64; H2=IMG//2
for reg in ("ME","NH","VT"):
    with rasterio.open(f"data/landfire/{reg}_2025_nlcd.tif") as s:
        nd=(s.read(1)==-9999); T=s.transform; CRS=s.crs; H,W=s.height,s.width
    inv=~T
    for kind,path in (("train neg",f"data/negatives/train_negatives_{reg}.csv"),
                      ("val neg",f"data/negatives/val_negatives_{reg}.csv"),
                      ("train pos",f"data/pipeline/train_positives_{reg}.csv"),
                      ("val pos",f"data/pipeline/val_positives_{reg}.csv")):
        df=pd.read_csv(path)
        tr=Transformer.from_crs("EPSG:4326",CRS,always_xy=True)
        x,y=tr.transform(df.longitude.values,df.latitude.values)
        fr=[];ct=[]
        for xi,yi in zip(x,y):
            c,r=inv*(xi,yi); c=int(np.floor(c)); r=int(np.floor(r))
            r0,c0=max(r-H2,0),max(c-H2,0)
            w=nd[r0:min(r-H2+IMG,H), c0:min(c-H2+IMG,W)]
            tot=IMG*IMG
            fr.append((w.sum()+(tot-w.size))/tot)   # off-grid counts as nodata
            ct.append(bool(nd[r,c]) if 0<=r<H and 0<=c<W else True)
        fr=np.array(fr); ct=np.array(ct)
        print(f"{reg} {kind:10s} n={len(df):5d}  any-nodata-in-window={(fr>0).sum():3d}"
              f"  >10%={(fr>0.10).sum():3d}  =100%={(fr==1.0).sum():2d}"
              f"  centre-nodata={ct.sum():2d}  max={fr.max():.2f}",flush=True)
    del nd
