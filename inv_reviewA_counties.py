import rasterio, geopandas as gpd, os
from shapely.geometry import box
from rasterio.transform import Affine, array_bounds
cty=gpd.read_file("data/roads/tl_2023_us_county.zip")
for r in ["ME","NH","VT"]:
    with rasterio.open(f"data/landfire/{r}_2024_evt.tif") as s:
        pad=int(round(10*1000/abs(s.transform.a)))
        t=s.transform*Affine.translation(-pad,-pad); H,W=s.height+2*pad,s.width+2*pad
        w,so,e,n=array_bounds(H,W,t); crs=s.crs
    fp=gpd.GeoSeries([box(min(w,e),min(so,n),max(w,e),max(so,n))],crs=crs).to_crs(cty.crs).iloc[0]
    sel=cty[cty.intersects(fp)]
    need=[f"tl_2023_{a}{b}_roads.zip" for a,b in zip(sel.STATEFP,sel.COUNTYFP)]
    miss=[n_ for n_ in need if not os.path.exists("data/roads/"+n_)]
    print(f"{r}: {len(need)} counties needed (2023 vintage), {len(miss)} NOT cached -> network required")
    print("   missing STATEFPs:", sorted({m.split('_')[2][:2] for m in miss}), "count", len(miss))
