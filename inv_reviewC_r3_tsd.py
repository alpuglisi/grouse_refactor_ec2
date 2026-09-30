"""R3-JOB3: is the tsd coverage accumulator (§9.2) implementable?  i.e. does the
LANDFIRE Annual Disturbance source actually STORE its declared nodata (32767)
outside CONUS, and does its footprint match the NLCD reference?"""
import rasterio, numpy as np, glob
from pyproj import Transformer
srcs=sorted(glob.glob("data/disturbance/**/*.tif",recursive=True))
print(len(srcs),"disturbance tifs")
with rasterio.open(f"data/landfire/ME_2016_nlcd.tif") as s:
    T,W,H,crs=s.transform,s.width,s.height,s.crs; nl=s.read(1)
rng=np.random.default_rng(0)
rows=rng.integers(0,H,60000); cols=rng.integers(0,W,60000)
xs,ys=rasterio.transform.xy(T,rows,cols)
inside=nl[rows,cols]!=-9999
tr=Transformer.from_crs(crs,"EPSG:5070",always_xy=True)
X,Y=tr.transform(np.array(xs),np.array(ys))
for p in srcs[:3]+srcs[-2:]:
    with rasterio.open(p) as s:
        v=np.array([a[0] for a in s.sample(zip(X,Y))],dtype=np.float64)
        nd=s.nodata
    def tab(mask,name):
        vv=v[mask]; u,c=np.unique(vv,return_counts=True); o=np.argsort(-c)[:5]
        print(f"    {name:8s} n={mask.sum():6d} nodata({nd})={100*(vv==nd).mean():6.2f}%  "
              f"zero={100*(vv==0).mean():6.2f}%  top={[(float(u[i]),int(c[i])) for i in o]}")
    print(f"  {p.split('/')[-1]}  declared nodata={nd}")
    tab(inside,"IN-US"); tab(~inside,"OUT-US")
# union coverage across ALL vintages at the sampled points
cov=np.zeros(len(X),dtype=bool)
for p in srcs:
    with rasterio.open(p) as s:
        v=np.array([a[0] for a in s.sample(zip(X,Y))],dtype=np.float64); nd=s.nodata
    cov |= (v!=nd)
print(f"\n  UNION 'any vintage non-nodata' over {len(srcs)} tifs:")
print(f"    inside NLCD footprint : covered {100*cov[inside].mean():.3f}%  (want ~100)")
print(f"    outside NLCD footprint: covered {100*cov[~inside].mean():.3f}%  (want ~0)")
