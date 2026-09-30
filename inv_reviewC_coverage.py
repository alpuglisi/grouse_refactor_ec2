import numpy as np, rasterio, geopandas as gpd, pandas as pd
from pyproj import Transformer
from grouse_data import GrouseData
STEP=16
rd=GrouseData()["ME"]
pe=rd.latest_raster_path("evt")
with rasterio.open(pe) as s:
    evt=s.read(1)[::STEP,::STEP]; nd=s.nodata; T=s.transform; crs=s.crs
    print("evt raster:",pe,s.width,s.height,"crs",crs.to_string()[:60])
    print("bounds",s.bounds)
ins=evt!=nd
with rasterio.open(rd.latest_raster_path("nlcd")) as s: nl=s.read(1)[::STEP,::STEP]
with rasterio.open(rd.latest_raster_path("balive")) as s: ba=s.read(1)[::STEP,::STEP]
rows,cols=np.mgrid[0:evt.shape[0],0:evt.shape[1]]
xs,ys=rasterio.transform.xy(T,(rows*STEP).ravel(),(cols*STEP).ravel())
tr=Transformer.from_crs(crs,"EPSG:4326",always_xy=True)
lon,lat=tr.transform(np.array(xs),np.array(ys))
cty=gpd.read_file("data/roads/tl_2023_us_county.zip")
us=cty.dissolve().to_crs("EPSG:4326")
me=cty[cty.STATEFP=="23"].dissolve().to_crs("EPSG:4326")
def frac_in(mask,poly,name):
    idx=np.flatnonzero(mask.ravel())
    if len(idx)>40000: idx=np.random.default_rng(0).choice(idx,40000,replace=False)
    g=gpd.GeoDataFrame(geometry=gpd.points_from_xy(lon[idx],lat[idx]),crs="EPSG:4326")
    j=gpd.sjoin(g,poly[["geometry"]],how="left",predicate="within")
    j=j[~j.index.duplicated()]
    print(f"   {name}: {100*j.index_right.notna().mean():.1f}% inside polygon (n={len(idx)})")
print("\nevt VALID pixels:"); frac_in(ins,us,"in US"); frac_in(ins,me,"in Maine")
hole=ins&(nl==-9999)
print("evt valid & nlcd NODATA:"); frac_in(hole,us,"in US"); frac_in(hole,me,"in Maine")
print("evt valid & nlcd valid:"); frac_in(ins&(nl!=-9999),us,"in US")
print("evt NODATA pixels:"); frac_in(~ins,us,"in US")
print("evt valid & balive==0:"); frac_in(ins&(ba==0),us,"in US"); frac_in(ins&(ba==0),me,"in Maine")
