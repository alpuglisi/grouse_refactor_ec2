"""Why the §9.2 source-derived coverage accumulator cannot work."""
import rasterio, numpy as np, glob
from pyproj import Transformer
srcs=sorted(glob.glob("data/disturbance/**/*.tif",recursive=True))
with rasterio.open("data/landfire/ME_2016_nlcd.tif") as s:
    T,W,H,crs=s.transform,s.width,s.height,s.crs; nl=s.read(1)
rng=np.random.default_rng(1); rows=rng.integers(0,H,20000); cols=rng.integers(0,W,20000)
xs,ys=rasterio.transform.xy(T,rows,cols); inside=nl[rows,cols]!=-9999
X,Y=Transformer.from_crs(crs,"EPSG:5070",always_xy=True).transform(np.array(xs),np.array(ys))
SENT={32767.0,-9999.0,-32768.0,-1111.0}
covA=np.zeros(20000,bool); covB=np.zeros(20000,bool)
for p in srcs:
    with rasterio.open(p) as s:
        v=np.array([a[0] for a in s.sample(zip(X,Y))],dtype=np.float64); nd=s.nodata
    covA |= (v!=nd)                       # §9.2 as written
    covB |= ~np.isin(v,list(SENT))        # hardened: all known sentinels
print(f"§9.2 as written  (arr != src.nodata): out-of-US marked COVERED {100*covA[~inside].mean():.3f}%  (want 0)")
print(f"hardened (all NODATA_SENTINELS)     : out-of-US marked COVERED {100*covB[~inside].mean():.3f}%  (want 0)")
print(f"                                      in-US marked covered     {100*covB[inside].mean():.3f}%  (want 100)")
# which vintages are responsible for the residual under the hardened test?
bad=(~inside)&covB
print("\nvintages that report a NON-sentinel value at out-of-US points:")
for p in srcs:
    with rasterio.open(p) as s:
        v=np.array([a[0] for a in s.sample(zip(X,Y))],dtype=np.float64)
    n=int((~np.isin(v,list(SENT)))[~inside].sum())
    if n: print(f"   {p.split('/')[-1]:32s} {n:6d} of {int((~inside).sum())} out-of-US pts, top={np.unique(v[(~inside)&~np.isin(v,list(SENT))],return_counts=True)[0][:4]}")
