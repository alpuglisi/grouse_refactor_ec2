import numpy as np, rasterio, rasterio.features
from rasterio.transform import array_bounds
from rasterio.warp import transform_bounds
import geopandas as gpd
from grouse_data import GrouseData
import generate_road_distance as G, predict
data=GrouseData(); counties=G.load_counties(2023)
BOUNDS=(-71.25,44.70,-70.95,44.90)
for reg in ['ME','NH']:
    rd=data[reg]
    with rasterio.open(rd.raster_path('nlcd',2016)) as s:
        T,H,W,crs=s.transform,s.height,s.width,s.crs
        r0,r1,c0,c1=predict.bounds_to_window(s,BOUNDS,pad=0)
        nl=s.read(1,window=rasterio.windows.Window(c0,r0,c1-c0,r1-r0))
    pad=int(round(10000/abs(T.a)))
    pt,ph,pw=G.padded_grid(T,H,W,pad); w,s_,e,n=array_bounds(ph,pw,pt)
    rows=G.counties_for_grid(counties,(min(w,e),min(s_,n),max(w,e),max(s_,n)),crs)
    wt=T*rasterio.Affine.translation(c0,r0)
    inside=rasterio.features.rasterize(((g,1) for g in rows.geometry if g is not None),
        out_shape=nl.shape, transform=wt, fill=0, default_value=1, all_touched=True, dtype='uint8').astype(bool)
    print(f"{reg}: Errol-box window {nl.shape} n={nl.size:,}")
    print(f"   TIGER2023-outside (future road_dist NODATA) in the box = {(~inside).sum():,} px = {100*(~inside).mean():.4f}%")
    print(f"   NLCD-invalid in the box                                = {((nl<11)|(nl>95)).sum():,} px = {100*((nl<11)|(nl>95)).mean():.4f}%")
