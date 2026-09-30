import rasterio, glob, numpy as np, pandas as pd
for f in sorted(glob.glob("data/landfire/*_2024_evt.tif"))+sorted(glob.glob("data/landfire/*_2024_road_dist.tif")):
    with rasterio.open(f) as s:
        print(f.split('/')[-1], "crs=",s.crs.to_string()[:70], "res=",s.res, "shape=",(s.height,s.width))
        print("    bounds", tuple(round(b,1) for b in s.bounds), "nodata",s.nodata)
