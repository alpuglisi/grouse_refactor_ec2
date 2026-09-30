"""R3-JOB3: validate the NLCD-footprint coverage definition for ALL regions,
its stability across years, and its agreement with the TIGER county union."""
import rasterio, numpy as np, geopandas as gpd
from rasterio.features import rasterize
from pyproj import Transformer
cty=gpd.read_file("data/roads/tl_2023_us_county.zip")
us=cty.dissolve()
for r in ("ME","NH","VT"):
    print(f"\n=== {r}")
    with rasterio.open(f"data/landfire/{r}_2016_nlcd.tif") as s:
        T,W,H,crs=s.transform,s.width,s.height,s.crs
        n16=s.read(1)
    with rasterio.open(f"data/landfire/{r}_2025_nlcd.tif") as s: n25=s.read(1)
    m16=n16!=-9999; m25=n25!=-9999
    print(f"  nlcd valid frac 2016={m16.mean():.4f} 2025={m25.mean():.4f} "
          f"| pixels differing between years: {(m16!=m25).sum():,} ({100*(m16!=m25).mean():.4f}%)")
    usg=us.to_crs(crs)
    tig=rasterize([(g,1) for g in usg.geometry],out_shape=(H,W),transform=T,fill=0,dtype='uint8').astype(bool)
    print(f"  TIGER-union valid frac = {tig.mean():.4f}")
    print(f"  nlcd valid & NOT in TIGER : {(m16&~tig).sum():,} ({100*(m16&~tig).mean():.4f}% of grid)")
    print(f"  TIGER & nlcd NODATA       : {(tig&~m16).sum():,} ({100*(tig&~m16).mean():.4f}% of grid)")
    with rasterio.open(f"data/landfire/{r}_2022_evt.tif") as s: ev=s.read(1)
    evv=ev!=-9999
    print(f"  evt valid frac={evv.mean():.4f} | evt valid & nlcd NODATA = {100*(evv&~m16).mean():.3f}% of grid")
    print(f"  evt NODATA & nlcd valid   = {100*(~evv&m16).mean():.3f}% of grid")
    ty=2023
    with rasterio.open(f"data/landfire/{r}_{ty}_tcc.tif") as s: tc=s.read(1)
    print(f"  tcc: own nodata {100*(tc==-9999).mean():.3f}% | would gain nodata from nlcd mask: "
          f"{100*((tc!=-9999)&~m16).mean():.3f}% of grid")
    print(f"  tcc nonzero&valid OUTSIDE nlcd footprint (real data that would be lost): "
          f"{int(((tc>0)&(tc!=-9999)&~m16).sum()):,} px")
    with rasterio.open(f"data/landfire/{r}_2023_balive.tif") as s: ba=s.read(1)
    print(f"  balive: nonzero OUTSIDE nlcd footprint (real data that would be lost): "
          f"{int(((ba>0)&(ba!=-9999)&~m16).sum()):,} px  | zeros outside footprint: {int(((ba==0)&~m16).sum()):,}")
