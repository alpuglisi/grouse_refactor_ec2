"""As inv_formalB_g7 but the uniform sample is restricted to pixels INSIDE
the pre-registered tiger_at1 coverage mask (G7's stated population)."""
import numpy as np, rasterio, rasterio.features, geopandas as gpd, pandas as pd, os
from rasterio.transform import Affine, array_bounds
from shapely.geometry import box, Point
from shapely import STRtree
from models import road_dist_decode
MT=["S1100","S1200","S1400","S1630","S1640"]
reg='ME'; NPTS=1000; rng=np.random.default_rng(20260930)
with rasterio.open(f"data/landfire/{reg}_2025_road_dist.tif") as s:
    H,W,T,CRS=s.height,s.width,s.transform,s.crs; arr=s.read(1)
cty=gpd.read_file("data/roads/tl_2023_us_county.zip")
pad=int(round(10*1000/abs(T.a))); t=T*Affine.translation(-pad,-pad)
b=array_bounds(H+2*pad,W+2*pad,t)
gb=(min(b[0],b[2]),min(b[1],b[3]),max(b[0],b[2]),max(b[1],b[3]))
sel=cty[cty.intersects(gpd.GeoSeries([box(*gb)],crs=CRS).to_crs(cty.crs).iloc[0])]
g=sel.to_crs(CRS).geometry
M=rasterio.features.rasterize(((x,1) for x in g),out_shape=(H,W),transform=T,
    fill=0,default_value=1,all_touched=True,dtype='uint8').astype(bool)
frames=[gpd.read_file(f"data/roads/tl_2023_{sf}{cf}_roads.zip") for sf,cf in zip(sel.STATEFP,sel.COUNTYFP)]
roads=gpd.GeoDataFrame(pd.concat([f[f.MTFCC.isin(MT)][["geometry"]] for f in frames],ignore_index=True),crs=frames[0].crs).to_crs(CRS)
tree=STRtree(roads.geometry.values)
idxs=np.flatnonzero(M.ravel()); pick=rng.choice(idxs,NPTS,replace=False)
rows,cols=np.divmod(pick,W)
xs=T.c+(cols+rng.random(NPTS))*T.a; ys=T.f+(rows+rng.random(NPTS))*T.e
pts=[Point(x,y) for x,y in zip(xs,ys)]
j=tree.nearest(pts)
truth=np.array([pts[i].distance(roads.geometry.values[k]) for i,k in enumerate(j)])
rast=road_dist_decode(arr[rows,cols]); err=rast-truth; a=np.abs(err)
q=lambda v,p: float(np.percentile(v,p))
print(f"ME, uniform INSIDE tiger_at1 coverage, n={NPTS}")
print(f"  truth median {np.median(truth):.0f} max {truth.max():.0f}")
print(f"  |err| median {np.median(a):.2f} p90 {q(a,90):.2f} p95 {q(a,95):.2f} p99 {q(a,99):.2f} MAX {a.max():.2f}")
print(f"  signed median {np.median(err):.2f}  count(|err|>60)={int((a>60).sum())}  frac={(a>60).mean():.4f}")
print(f"  RD1 {'PASS' if np.median(a)<=20 else 'FAIL'} | RD2 {'PASS' if q(a,99)<=60 else 'FAIL'}"
      f" | RD3 {'PASS' if (a>60).sum()==0 else 'FAIL'} | RD4 {'PASS' if -20<=np.median(err)<=5 else 'FAIL'}")
