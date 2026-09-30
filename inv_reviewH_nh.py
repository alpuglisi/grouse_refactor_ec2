"""Verify CR-0008's NH road_dist control numbers, and whether G2's
'exactly 1.0000' is a tautology (checker mask == generator mask)."""
import numpy as np, rasterio, rasterio.features, geopandas as gpd
from shapely.geometry import box
cty=gpd.read_file("data/roads/tl_2023_us_county.zip")
for reg in ("ME","NH","VT"):
    with rasterio.open(f"data/landfire/{reg}_2025_road_dist.tif") as s:
        H,W,T,CRS,ND=s.height,s.width,s.transform,s.crs,s.nodata
        rd=s.read(1)
    N=H*W
    fp=gpd.GeoSeries([box(*rasterio.transform.array_bounds(H,W,T))],crs=CRS).to_crs(cty.crs).iloc[0]
    g=cty[cty.intersects(fp)].to_crs(CRS).geometry
    def rast(at):
        return rasterio.features.rasterize(((x,1) for x in g),out_shape=(H,W),
          transform=T,fill=0,default_value=1,all_touched=at,dtype="uint8").astype(bool)
    Mt,Mf=rast(True),rast(False)
    with rasterio.open(f"data/landfire/{reg}_2025_nlcd.tif") as s:
        nl=s.read(1)!=-9999
    nd=(rd==ND)
    print(f"{reg}: grid {N:,}  road_dist nodata frac {nd.mean():.6f}")
    for nm,M in (("all_touched=True",Mt),("all_touched=False",Mf),("NLCD-valid",nl)):
        out=~M
        g2 = nd[out].mean() if out.sum() else float('nan')
        stray = int((out & ~nd).sum())
        print(f"    ref={nm:18s} outside frac {out.mean():.6f}  "
              f"G2={g2:.6f}  stray(outside-but-valid)={stray:,}  "
              f"nodata-inside-coverage={int((M&nd).sum()):,}")
    print(f"    TIGER(at=True) vs NLCD disagreement: "
          f"{100*int((Mt&~nl).sum())/N:.4f}% / {100*int((nl&~Mt).sum())/N:.4f}%  of grid")
    print(f"    TIGER(at=False) vs NLCD disagreement: "
          f"{100*int((Mf&~nl).sum())/N:.4f}% / {100*int((nl&~Mf).sum())/N:.4f}%  of grid")
