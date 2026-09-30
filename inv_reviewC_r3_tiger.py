"""R3-JOB3: TIGER-2023 download accounting, and whether the §10 densification
fix changes the county set (which would mean NH DOES need regeneration)."""
import os, rasterio, numpy as np, geopandas as gpd
from shapely.geometry import box
from rasterio.transform import array_bounds
import sys; sys.path.insert(0,".")
from generate_road_distance import padded_grid, PAD_KM_DEFAULT
from grouse_data import GrouseData
cty=gpd.read_file("data/roads/tl_2023_us_county.zip")
data=GrouseData()
CACHE="data/roads"
cached={f for f in os.listdir(CACHE)}
for region in ("ME","NH","VT"):
    rd=data[region]
    tf=next((f for f in rd.available_features() if f!="road_dist"),None)
    template=rd.latest_raster_path(tf)
    with rasterio.open(template) as src:
        crs=src.crs; pad_px=int(round(PAD_KM_DEFAULT*1000.0/abs(src.transform.a)))
        pt,ph,pw=padded_grid(src.transform,src.height,src.width,pad_px)
    w,s_,e,n=array_bounds(ph,pw,pt); gb=(min(w,e),min(s_,n),max(w,e),max(s_,n))
    fp=gpd.GeoSeries([box(*gb)],crs=crs)
    plain=fp.to_crs(cty.crs).iloc[0]
    dens=gpd.GeoSeries([box(*gb).segmentize(1000.0)],crs=crs).to_crs(cty.crs).iloc[0]
    a=set(cty[cty.intersects(plain)].apply(lambda r:r.STATEFP+r.COUNTYFP,axis=1))
    b=set(cty[cty.intersects(dens)].apply(lambda r:r.STATEFP+r.COUNTYFP,axis=1))
    miss=[f"tl_2023_{c}_roads.zip" for c in sorted(b) if f"tl_2023_{c}_roads.zip" not in cached]
    print(f"\n{region}: template={os.path.basename(template)} pad_px={pad_px}")
    print(f"   undensified footprint -> {len(a)} counties ; densified(1 km) -> {len(b)} counties")
    print(f"   DIFFERENCE (densification adds): {sorted(b-a)}   removes: {sorted(a-b)}")
    print(f"   uncached county road zips (densified set, TIGER 2023): {len(miss)} -> {[m.split('_')[2] for m in miss]}")
    print(f"   states: { {k:len([c for c in b if c.startswith(k)]) for k in sorted({c[:2] for c in b})} }")
print(f"\nnational county file cached: {'tl_2023_us_county.zip' in cached}")
print(f"cached county road zips: {len([f for f in cached if f.endswith('_roads.zip')])}")
