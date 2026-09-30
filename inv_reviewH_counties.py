import os, rasterio, geopandas as gpd
from shapely.geometry import box
cty=gpd.read_file("data/roads/tl_2023_us_county.zip")
for reg in ("ME","NH","VT"):
    with rasterio.open(f"data/landfire/{reg}_2025_nlcd.tif") as s:
        gb=rasterio.transform.array_bounds(s.height,s.width,s.transform); CRS=s.crs
    fp=gpd.GeoSeries([box(*gb)],crs=CRS).to_crs(cty.crs).iloc[0]
    sel=cty[cty.intersects(fp)]
    miss=[f"{a}{b}" for a,b in zip(sel.STATEFP,sel.COUNTYFP)
          if not os.path.exists(f"data/roads/tl_2023_{a}{b}_roads.zip")]
    print(f"{reg}: {len(sel)} intersecting counties, {len(miss)} uncached at TIGER 2023: {sorted(miss)}")
