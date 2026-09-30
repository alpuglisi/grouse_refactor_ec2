"""Same attack, erosion direction: coarse mask with all_touched=False."""
import numpy as np, rasterio, rasterio.features, geopandas as gpd
from rasterio.transform import Affine
from shapely.geometry import box
with rasterio.open("data/landfire/ME_2025_tsd.tif") as s:
    H,W,T,CRS = s.height,s.width,s.transform,s.crs; ND=s.nodata
N=H*W
cty=gpd.read_file("data/roads/tl_2023_us_county.zip")
fp=gpd.GeoSeries([box(*rasterio.transform.array_bounds(H,W,T))],crs=CRS).to_crs(cty.crs).iloc[0]
g=cty[cty.intersects(fp)].to_crs(CRS).geometry
M_nl=np.load("inv_reviewH_M_nl.npy")
def cm(k,at):
    h,w=(H+k-1)//k,(W+k-1)//k
    m=rasterio.features.rasterize(((x,1) for x in g),out_shape=(h,w),
      transform=T*Affine.scale(k),fill=0,default_value=1,all_touched=at,
      dtype="uint8").astype(bool)
    return np.repeat(np.repeat(m,k,0),k,1)[:H,:W] if k>1 else m
for k in (4,8,16):
    M=cm(k,False); outside=~M
    destroyed=int((M_nl&outside).sum()); fab=int(((~M_nl)&M).sum())
    print(f"mask at {k:2d}x, all_touched=False, upsampled: "
          f"G1=0 PASS  G2=1.000000 PASS  |  in-US px DESTROYED {destroyed:>9,}  "
          f"out-of-US px left FABRICATED {fab:>8,}  |  NLCD cross-check "
          f"{100*fab/N:.4f}% / {100*destroyed/N:.4f}%  (budget 0.0500%)")
