"""I5 cost: full 64 px window inside every feature raster a record is
read from, both classes. Metadata-only -- no pixel reads."""
import time, resource, os, sys
import numpy as np, pandas as pd, rasterio
from pyproj import Transformer
sys.path.insert(0,"/home/ec2-user/grouse2")
from grouse_data import GrouseData
from models import FEATURE_SPEC
def rss(): return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024.0
def tic(): return time.perf_counter()
T0=tic()
data=GrouseData()
regions=["ME","NH","VT"]
feats=sorted(set.intersection(*[set(data[r].available_features()) & set(FEATURE_SPEC) for r in regions]))
print("features:",len(feats),feats)
READ=64
t=tic()
nviol=0; nrast=0; nrec=0
per_region={}
for r in regions:
    rd=data[r]
    frames=[]
    for p in (f"data/pipeline/train_positives_{r}.csv", f"data/pipeline/val_positives_{r}.csv",
              f"data/negatives/train_negatives_{r}.csv", f"data/negatives/val_negatives_{r}.csv"):
        frames.append(pd.read_csv(p)[["longitude","latitude","year"]])
    d=pd.concat(frames,ignore_index=True)
    d["year"]=d["year"].fillna(d["year"].max()).astype(int)
    nrec+=len(d)
    bad=np.zeros(len(d),dtype=bool)
    for f in feats:
        for yr in sorted(d["year"].unique()):
            m=(d["year"].values==yr)
            path=rd.raster_path(f,int(yr))
            with rasterio.open(path) as src:
                nrast+=1
                tr=Transformer.from_crs("EPSG:4326",src.crs,always_xy=True)
                x,y=tr.transform(d.loc[m,"longitude"].values,d.loc[m,"latitude"].values)
                inv=~src.transform
                fc,fr=inv*(np.asarray(x),np.asarray(y))
                rows=np.floor(fr).astype(np.int64); cols=np.floor(fc).astype(np.int64)
                half=READ//2
                r0=rows-half; c0=cols-half
                ok=(r0>=0)&(c0>=0)&(r0+READ<=src.height)&(c0+READ<=src.width)
                bad[m] |= ~ok
    per_region[r]=int(bad.sum()); nviol+=int(bad.sum())
print(f"I5 metadata window check: {time.perf_counter()-t:.2f}s  maxRSS {rss():.0f} MB")
print(f"   records {nrec}  raster opens {nrast}  violations {per_region} total {nviol}")
print(f"TOTAL {time.perf_counter()-T0:.2f}s")
