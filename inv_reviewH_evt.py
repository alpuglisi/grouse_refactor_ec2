"""CR-0008 declares evh/evc/sclass/fdist/ch/cc and nlcd 'correct' on the
evidence that they are nodata where LANDFIRE evt is nodata -- a reference the
same CR forbids (32.8% of evt-VALID ME pixels are outside the US).  Re-check
against the declared reference (TIGER county union)."""
import numpy as np, rasterio, rasterio.features, geopandas as gpd, glob, os
from shapely.geometry import box
cty=gpd.read_file("data/roads/tl_2023_us_county.zip")
for reg in ("ME","NH","VT"):
    with rasterio.open(f"data/landfire/{reg}_2025_nlcd.tif") as s:
        H,W,T,CRS=s.height,s.width,s.transform,s.crs
    N=H*W
    fp=gpd.GeoSeries([box(*rasterio.transform.array_bounds(H,W,T))],crs=CRS).to_crs(cty.crs).iloc[0]
    g=cty[cty.intersects(fp)].to_crs(CRS).geometry
    M=rasterio.features.rasterize(((x,1) for x in g),out_shape=(H,W),transform=T,
        fill=0,default_value=1,all_touched=True,dtype="uint8").astype(bool)
    out=~M
    print(f"\n=== {reg}: outside TIGER-2023 county union = {out.sum():,} px "
          f"({100*out.mean():.4f}% of grid)")
    for feat in ("evt","evh","evc","sclass","fdist","ch","cc","nlcd"):
        c=sorted(glob.glob(f"data/landfire/{reg}_*_{feat}.tif"))
        if not c: print(f"   {feat:8s} absent"); continue
        p=c[-1]
        with rasterio.open(p) as s:
            a=s.read(1); nd=s.nodata
        bad=(a!=nd)
        for sent in (-9999,-32768,32767,-1111):
            bad &= (a!=sent)
        fab=int((bad&out).sum())
        print(f"   {feat:8s} {os.path.basename(p):24s} non-nodata OUTSIDE "
              f"coverage: {fab:>12,}  ({100*fab/N:7.4f}% of grid, "
              f"{100*fab/out.sum():6.2f}% of the outside area)")
        del a,bad
