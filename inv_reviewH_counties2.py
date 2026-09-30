import os, rasterio, numpy as np, geopandas as gpd
from rasterio.transform import Affine, array_bounds
from shapely.geometry import box
cty=gpd.read_file("data/roads/tl_2023_us_county.zip")
for reg in ("ME","NH","VT"):
    with rasterio.open(f"data/landfire/{reg}_2025_nlcd.tif") as s:
        T,H,W,CRS=s.transform,s.height,s.width,s.crs
    pad=int(round(10000.0/abs(T.a)))
    pt=T*Affine.translation(-pad,-pad)
    w,so,e,n=array_bounds(H+2*pad,W+2*pad,pt)
    gb=(min(w,e),min(so,n),max(w,e),max(so,n))
    fp=gpd.GeoSeries([box(*gb)],crs=CRS).to_crs(cty.crs).iloc[0]
    sel=cty[cty.intersects(fp)]
    miss=sorted(f"{a}{b}" for a,b in zip(sel.STATEFP,sel.COUNTYFP)
                if not os.path.exists(f"data/roads/tl_2023_{a}{b}_roads.zip"))
    print(f"{reg}: pad {pad}px, {len(sel)} counties, {len(miss)} uncached: {miss}")
