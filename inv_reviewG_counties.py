import os, rasterio
from rasterio.transform import array_bounds
from grouse_data import GrouseData
import generate_road_distance as G
data=GrouseData(); counties=G.load_counties(2023)
print("national county zip present:", os.path.exists("data/roads/tl_2023_us_county.zip"))
for reg in ['ME','NH','VT']:
    rd=data[reg]
    tf=next(f for f in rd.available_features() if f!='road_dist')
    with rasterio.open(rd.latest_raster_path(tf)) as s:
        t,H,W,crs=s.transform,s.height,s.width,s.crs; pad=int(round(10000/abs(s.transform.a)))
    pt,ph,pw=G.padded_grid(t,H,W,pad); w,s_,e,n=array_bounds(ph,pw,pt)
    rows=G.counties_for_grid(counties,(min(w,e),min(s_,n),max(w,e),max(s_,n)),crs)
    miss=[]
    for sf,cf in zip(rows.STATEFP,rows.COUNTYFP):
        p=f"data/roads/tl_2023_{sf}{cf}_roads.zip"
        if not os.path.exists(p): miss.append(sf+cf)
    print(f"{reg}: {len(rows)} counties, uncached={len(miss)} {sorted(miss)}")
