"""Re-measure CR-0008's load-bearing raster numbers at full resolution."""
import numpy as np, rasterio, rasterio.features, geopandas as gpd
from shapely.geometry import box
cty=gpd.read_file("data/roads/tl_2023_us_county.zip")
for reg,yr_tm,yr_tcc in (("ME",2025,2023),("NH",2025,2023),("VT",2025,2023)):
    with rasterio.open(f"data/landfire/{reg}_{yr_tm}_tsd.tif") as s:
        H,W,T,CRS=s.height,s.width,s.transform,s.crs; tsd=s.read(1); tnd=s.nodata
    N=H*W
    fp=gpd.GeoSeries([box(*rasterio.transform.array_bounds(H,W,T))],crs=CRS).to_crs(cty.crs).iloc[0]
    g=cty[cty.intersects(fp)].to_crs(CRS).geometry
    M=rasterio.features.rasterize(((x,1) for x in g),out_shape=(H,W),transform=T,
        fill=0,default_value=1,all_touched=True,dtype="uint8").astype(bool)
    out=~M
    u,c=np.unique(tsd[out],return_counts=True)
    print(f"\n=== {reg}  grid {N:,}  outside-TIGER {out.sum():,} ({100*out.mean():.4f}%)")
    print(f"  tsd {yr_tm} outside coverage: top values "
          f"{[(int(a),int(b)) for a,b in sorted(zip(u,c),key=lambda z:-z[1])[:3]]}"
          f"  nodata there: {int((tsd[out]==tnd).sum()):,}")
    print(f"  tsd {yr_tm} in-coverage tsd==0: {int((tsd[M]==0).sum()):,}"
          f"   in-cov saturation share: {(tsd[M]==tsd[M].max()).mean():.4f} (max={tsd[M].max()})")
    del tsd
    with rasterio.open(f"data/landfire/{reg}_{yr_tm}_balive.tif") as s:
        ba=s.read(1); bnd=s.nodata
    print(f"  balive>0 OUTSIDE coverage: {int((ba[out]>0).sum()):,}   "
          f"(CR: ME 11,700 / NH 4,464 / VT 2,137)")
    print(f"  balive==0 in-coverage: {int((ba[M]==0).sum()):,} "
          f"({100*(ba[M]==0).mean():.2f}% of in-coverage)")
    print(f"  balive nodata anywhere: {int((ba==bnd).sum()):,}")
    del ba
    with rasterio.open(f"data/landfire/{reg}_{yr_tcc}_tcc.tif") as s:
        tc=s.read(1); cnd=s.nodata
    print(f"  tcc {yr_tcc}: nodata outside coverage {int((tc[out]==cnd).sum()):,} "
          f"of {out.sum():,}  -> fabricated share {1-(tc[out]==cnd).mean():.6f}")
    print(f"  tcc==0 in-coverage: {int((tc[M]==0).sum()):,}")
    del tc
