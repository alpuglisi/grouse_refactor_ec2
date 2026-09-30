"""CR-0007 I5: reconcile 'NH 4 / 6' with my round-2 measurement of 0."""
import numpy as np, pandas as pd, rasterio
from pyproj import Transformer
from grouse_data import GrouseData, RASTER_FEATURES
d=GrouseData(); R=["ME","NH","VT"]
def count_oob(sub, region, margin):
    worst=0; hits={}
    rd=d[region]
    for f in [x for x in RASTER_FEATURES if rd.raster_years(x)]:
        for yr in rd.raster_years(f):
            p=rd.raster_path(f,yr,validate=False)
            with rasterio.open(p) as s:
                tr=Transformer.from_crs("EPSG:4326",s.crs,always_xy=True)
                x,y=tr.transform(sub.longitude.values,sub.latitude.values)
                rr,cc=rasterio.transform.rowcol(s.transform,x,y)
                rr=np.asarray(rr); cc=np.asarray(cc)
                n=int(((rr-margin<0)|(cc-margin<0)|
                       (rr+margin>s.height)|(cc+margin>s.width)).sum())
                if n: hits[f"{f}_{yr}"]=n
                worst=max(worst,n)
    return worst,hits
for margin,label in ((32,"64x64"),(36,"64+2*jitter(4)=72")):
    print(f"--- margin {margin} px ({label}) ---")
    for r in R:
        pre=pd.concat([pd.read_csv(f"data/pipeline/{s}_positives_{r}.csv")
                       for s in ("train","val")],ignore_index=True)
        post=pre[pre.state==r]
        for nm,sub in (("PRE-partition (today's file)",pre),
                       ("POST-partition (state==region)",post)):
            w,h=count_oob(sub,r,margin)
            print(f"  {r} {nm}: {len(sub)} records, max out-of-window {w} {h if h else ''}")
