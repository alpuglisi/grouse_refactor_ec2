import numpy as np, pandas as pd, rasterio
from rasterio.windows import Window
from pyproj import Transformer
# Proxy for post-fix ME road_dist coverage: NLCD valid footprint (the CR's own reference)
src=rasterio.open("data/landfire/ME_2023_nlcd.tif")
arr=src.read(1); nd=(arr==src.nodata)
print("ME nlcd-invalid share of grid: %.2f%%"%(100*nd.mean()))
T=Transformer.from_crs("EPSG:4326",src.crs,always_xy=True)
for name,path in (("train pos","data/pipeline/train_positives_ME.csv"),
                  ("val pos","data/pipeline/val_positives_ME.csv"),
                  ("negatives","data/negatives/negatives_ME.csv")):
    df=pd.read_csv(path)
    xs,ys=T.transform(df.longitude.values,df.latitude.values)
    rows,cols=rasterio.transform.rowcol(src.transform,xs,ys)
    rows=np.asarray(rows); cols=np.asarray(cols)
    H,W=arr.shape
    fr=[]; cn=0
    for rr,cc in zip(rows,cols):
        r0,r1=rr-32,rr+32; c0,c1=cc-32,cc+32
        sub=np.ones((64,64),bool)
        rs,re=max(r0,0),min(r1,H); cs,ce=max(c0,0),min(c1,W)
        if re>rs and ce>cs:
            sub=np.ones((64,64),bool)
            sub[rs-r0:re-r0, cs-c0:ce-c0]=nd[rs:re,cs:ce]
        fr.append(sub.mean())
        cn += int(nd[rr,cc]) if (0<=rr<H and 0<=cc<W) else 1
    fr=np.array(fr)
    print(f"{name} (ME, n={len(fr)}): centre outside coverage {cn};  any nodata in 64x64 window {(fr>0).sum()} ({100*(fr>0).mean():.2f}%);"
          f"  >10% {(fr>0.10).sum()};  >25% {(fr>0.25).sum()};  >50% {(fr>0.50).sum()};  max {fr.max():.3f}")
