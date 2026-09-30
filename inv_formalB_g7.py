"""Formal review B / CR-0008 G7: independently re-measure road_dist error
against exact shapely distance to the nearest paved TIGER-2023 road.
Checks (a) the correct NH raster's max |err| against the claimed 38.9 m /
45 m bound, (b) whether a uniform median/p95 gate would pass the broken ME
raster on disk.  READ-ONLY."""
import sys, glob, os, numpy as np, rasterio, geopandas as gpd, pandas as pd
from rasterio.transform import Affine, array_bounds
from shapely.geometry import box, Point
from shapely import STRtree
from models import road_dist_decode

MT = ["S1100","S1200","S1400","S1630","S1640"]
reg = sys.argv[1]; NPTS = int(sys.argv[2]) if len(sys.argv)>2 else 1000
rng = np.random.default_rng(20260930)
path = f"data/landfire/{reg}_2025_road_dist.tif"
with rasterio.open(path) as s:
    H,W,T,CRS = s.height,s.width,s.transform,s.crs
    arr = s.read(1); ND = s.nodata
cty = gpd.read_file("data/roads/tl_2023_us_county.zip")
pad = int(round(10*1000.0/abs(T.a)))
t = T*Affine.translation(-pad,-pad)
b = array_bounds(H+2*pad, W+2*pad, t)
gb = (min(b[0],b[2]),min(b[1],b[3]),max(b[0],b[2]),max(b[1],b[3]))
sel = cty[cty.intersects(gpd.GeoSeries([box(*gb)],crs=CRS).to_crs(cty.crs).iloc[0])]
frames=[]
for sf,cf in zip(sel.STATEFP, sel.COUNTYFP):
    p=f"data/roads/tl_2023_{sf}{cf}_roads.zip"
    if not os.path.exists(p):
        print("   [skip, uncached]", os.path.basename(p)); continue
    g=gpd.read_file(p); frames.append(g[g.MTFCC.isin(MT)][["geometry"]])
roads = gpd.GeoDataFrame(pd.concat(frames,ignore_index=True), crs=frames[0].crs).to_crs(CRS)
print(f"{reg}: {len(sel)} counties, {len(roads):,} paved segments")
tree = STRtree(roads.geometry.values)

# uniform sample over valid (in-coverage) pixels
valid = np.flatnonzero(arr.ravel() != ND)
pick = rng.choice(valid, size=NPTS, replace=False)
rows, cols = np.divmod(pick, W)
# sample point = a uniform random position INSIDE the pixel (as a real
# ground-truth check must be), not the pixel centre
fx = rng.random(NPTS); fy = rng.random(NPTS)
xs = T.c + (cols + fx)*T.a
ys = T.f + (rows + fy)*T.e
pts = [Point(x,y) for x,y in zip(xs,ys)]
idx = tree.nearest(pts)
truth = np.array([pts[i].distance(roads.geometry.values[j]) for i,j in enumerate(idx)])
rast = road_dist_decode(arr[rows,cols])
err = rast - truth
a = np.abs(err)
q = lambda v,p: float(np.percentile(v,p))
print(f"  truth  : median {np.median(truth):.0f} m  p95 {q(truth,95):.0f}  max {truth.max():.0f}")
print(f"  raster : median {np.median(rast):.0f} m  p95 {q(rast,95):.0f}  max {rast.max():.0f}")
print(f"  |err|  : median {np.median(a):.2f}  p90 {q(a,90):.2f}  p95 {q(a,95):.2f} "
      f"p99 {q(a,99):.2f}  MAX {a.max():.2f} m")
print(f"  signed : median {np.median(err):.2f} m   frac(|err|>60m) = {(a>60).mean():.4f}"
      f"  count(|err|>60) = {int((a>60).sum())}/{NPTS}")
print(f"  frac(|err|>45m) = {(a>45).mean():.4f}   frac(|err|>42.5m) = {(a>42.5).mean():.4f}")
print(f"  RD1 median<=20m: {'PASS' if np.median(a)<=20 else 'FAIL'} | "
      f"RD2 p99<=60m: {'PASS' if q(a,99)<=60 else 'FAIL'} | "
      f"RD3 count(>60)==0: {'PASS' if (a>60).sum()==0 else 'FAIL'} | "
      f"RD4 median signed in [-20,5]: {'PASS' if -20<=np.median(err)<=5 else 'FAIL'}")
