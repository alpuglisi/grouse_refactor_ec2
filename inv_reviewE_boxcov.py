"""Verify CR-0009 v3 item 4's justification: does the Errol box contain any
pixel outside US coverage, in either the ME or the NH grid?  Read-only."""
import numpy as np, rasterio, geopandas as gpd, glob
from rasterio.features import rasterize
import predict
from grouse_data import GrouseData
BOUNDS=(-71.25,44.70,-70.95,44.90)
cty=gpd.read_file("data/roads/tl_2023_us_county.zip")
data=GrouseData()
for region in ("NH","ME"):
    tif=sorted(glob.glob(f"data/landfire/{region}_*_evt.tif"))[-1]
    with rasterio.open(tif) as src:
        r0,r1,c0,c1=predict.bounds_to_window(src,BOUNDS,pad=0)
        w=rasterio.windows.Window(c0,r0,c1-c0,r1-r0)
        tr=src.window_transform(w); shp=(r1-r0,c1-c0)
        us=rasterize(((g,1) for g in cty.to_crs(src.crs).geometry if g is not None),
                     out_shape=shp,transform=tr,fill=0,dtype="uint8").astype(bool)
    print(f"\n=== {region} grid, Errol box {shp[0]}x{shp[1]} = {us.size} px")
    print(f"    outside TIGER-2023 county union : {int((~us).sum())} px "
          f"({100*(~us).mean():.3f}%)")
    # road_dist NODATA share over the box and over the whole grid
    rp=data[region].latest_raster_path("road_dist")
    with rasterio.open(rp) as s:
        nd=s.nodata
        box=s.read(1,window=rasterio.windows.Window(c0,r0,c1-c0,r1-r0))
        print(f"    road_dist NODATA in box        : {int((box==nd).sum())} px "
              f"({100*(box==nd).mean():.3f}%)   [{rp.split('/')[-1]}, nodata={nd}]")
        full=s.read(1)
        print(f"    road_dist NODATA whole grid    : {100*(full==nd).mean():.2f}%")
