"""How much of each region grid will become NODATA under bf8d31a
(pixels outside all US counties). Computed at 1/10 resolution."""
import rasterio, numpy as np, geopandas as gpd, glob
from shapely.geometry import box
from rasterio.features import rasterize
from rasterio.transform import Affine
cty=gpd.read_file("data/roads/tl_2023_us_county.zip")
for r in ["ME","NH","VT"]:
    f=f"data/landfire/{r}_2024_evt.tif"
    with rasterio.open(f) as s:
        t=s.transform; H,W=s.height,s.width; crs=s.crs; b=s.bounds
    k=10
    t2=t*Affine.scale(k,k); H2,W2=H//k,W//k
    fp=gpd.GeoSeries([box(*b)],crs=crs).to_crs(cty.crs).iloc[0]
    sel=cty[cty.intersects(fp)].to_crs(crs)
    m=rasterize(((g,1) for g in sel.geometry if g is not None),out_shape=(H2,W2),
                transform=t2,fill=0,default_value=1,all_touched=True,dtype="uint8")
    print(f"{r}: grid {H}x{W}; counties intersecting {len(sel)} states {sorted(set(sel.STATEFP))}")
    print(f"    fraction OUTSIDE US county coverage -> NODATA: {1-m.mean():.3f}")
