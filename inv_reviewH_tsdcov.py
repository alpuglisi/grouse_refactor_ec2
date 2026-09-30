"""Is 'the LANDFIRE disturbance stack's covered area' (CR-0008 §Coverage,
tsd's declared reference) computable?  Sample known out-of-US and in-US
pixels of the ME grid in several vintages."""
import glob, numpy as np, rasterio
from rasterio.warp import transform as wtf
import geopandas as gpd, rasterio.features
from shapely.geometry import box

with rasterio.open("data/landfire/ME_2025_tsd.tif") as s:
    H,W,T,CRS=s.height,s.width,s.transform,s.crs
cty=gpd.read_file("data/roads/tl_2023_us_county.zip")
fp=gpd.GeoSeries([box(*rasterio.transform.array_bounds(H,W,T))],crs=CRS).to_crs(cty.crs).iloc[0]
g=cty[cty.intersects(fp)].to_crs(CRS).geometry
M=rasterio.features.rasterize(((x,1) for x in g),out_shape=(H,W),transform=T,
    fill=0,default_value=1,all_touched=True,dtype="uint8").astype(bool)
rng=np.random.default_rng(0)
ri,ci=np.nonzero(~M[::97,::97]); ri,ci=ri*97,ci*97
sel=rng.choice(len(ri),400,replace=False); out_rc=list(zip(ri[sel],ci[sel]))
ri,ci=np.nonzero(M[::97,::97]); ri,ci=ri*97,ci*97
sel=rng.choice(len(ri),400,replace=False); in_rc=list(zip(ri[sel],ci[sel]))
def xy(rc): return zip(*[rasterio.transform.xy(T,r,c) for r,c in rc])
ox,oy=xy(out_rc); ix,iy=xy(in_rc)

vints=sorted(glob.glob("data/disturbance/USAnnualDisturbance_1999_present/LF*/*/Tif/*.tif"))
print(f"{len(vints)} disturbance vintages on disk")
for p in vints[:4]+vints[-4:]:
    with rasterio.open(p) as s:
        dx,dy=wtf(CRS,s.crs,list(ox),list(oy)); vo=np.array(list(s.sample(zip(dx,dy)))).ravel()
        dx,dy=wtf(CRS,s.crs,list(ix),list(iy)); vi=np.array(list(s.sample(zip(dx,dy)))).ravel()
        nd=s.nodata
    def summ(v): 
        u,c=np.unique(v,return_counts=True)
        return ", ".join(f"{a}:{b}" for a,b in list(zip(u,c))[:5])
    print(f"  {p.split('/')[-1]:28s} declared nodata={nd}")
    print(f"     OUT-of-US 400px: {summ(vo)}")
    print(f"     IN-US     400px: {summ(vi)}")
