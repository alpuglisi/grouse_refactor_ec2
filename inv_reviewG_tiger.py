import os, numpy as np, rasterio, rasterio.features
from rasterio.transform import array_bounds
import geopandas as gpd
from grouse_data import GrouseData
import generate_road_distance as G

data=GrouseData()
counties=G.load_counties(2023)
print("national county file:", counties.crs, len(counties))
for reg in ['ME','NH','VT']:
    rd=data[reg]
    tf=next((f for f in rd.available_features() if f!='road_dist'), None)
    template=rd.latest_raster_path(tf)
    with rasterio.open(template) as src:
        t=src.transform; H=src.height; W=src.width; crs=src.crs
        pad_px=int(round(10.0*1000.0/abs(src.transform.a)))
    pt,ph,pw=G.padded_grid(t,H,W,pad_px)
    w,s_,e,n=array_bounds(ph,pw,pt)
    gb=(min(w,e),min(s_,n),max(w,e),max(s_,n))
    rows=G.counties_for_grid(counties,gb,crs)
    by=rows.groupby("STATEFP").size().to_dict()
    inside=rasterio.features.rasterize(
        ((g,1) for g in rows.geometry if g is not None),
        out_shape=(H,W), transform=t, fill=0, default_value=1,
        all_touched=True, dtype='uint8').astype(bool)
    with rasterio.open(rd.raster_path('nlcd',2016)) as s:
        nl=s.read(1)
    nlvalid=(nl>=11)&(nl<=95)
    out_frac=1.0-inside.mean()
    print(f"\n{reg}: template={os.path.basename(template)} grid={H}x{W} pad_px={pad_px}")
    print(f"   counties={len(rows)} by_state={by}")
    print(f"   TIGER2023 union: OUTSIDE frac = {out_frac:.6f}  ({100*out_frac:.2f}%)  -> predicted road_dist NODATA")
    print(f"   NLCD-invalid frac              = {(~nlvalid).mean():.6f}")
    a = int((inside & ~nlvalid).sum()); b=int((~inside & nlvalid).sum())
    print(f"   disagreement: TIGER-in & NLCD-nodata = {a} ({100*a/nl.size:.4f}% of grid)")
    print(f"                 TIGER-out & NLCD-valid = {b} ({100*b/nl.size:.4f}% of grid)")
    # current road_dist nodata
    with rasterio.open(rd.raster_path('road_dist',2016)) as s:
        rr=s.read(1)
    print(f"   current road_dist nodata frac  = {(rr==-9999).mean():.6f}")
    print(f"   A1 (nodata frac among TIGER-outside px, current) = {(rr[~inside]==-9999).mean():.6f}")
    print(f"   A1 (nodata frac among NLCD-outside px,  current) = {(rr[~nlvalid]==-9999).mean():.6f}")
    del nl, rr, inside
