"""FORMAL D: verify CR-0008's distributional / cross-lineage claims."""
import numpy as np, rasterio, hashlib, geopandas as gpd, rasterio.features
from rasterio.transform import array_bounds
from shapely.geometry import box
SC="/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
cty=gpd.read_file('data/roads/tl_2023_us_county.zip')
for reg in ['ME','NH','VT']:
    tpl=f"data/landfire/{reg}_2025_nlcd.tif"
    with rasterio.open(tpl) as s:
        H,W,T,CRS=s.height,s.width,s.transform,s.crs; nl=s.read(1)
    N=H*W
    cn = nl!=-9999; del nl
    cd = np.load(f"{SC}/covD_{reg}_2025.npy")
    w,s_,e,n=array_bounds(H,W,T); gb=(min(w,e),min(s_,n),max(w,e),max(s_,n))
    fp=gpd.GeoSeries([box(*gb)],crs=CRS).to_crs(cty.crs).iloc[0]
    g=cty[cty.intersects(fp)].to_crs(CRS).geometry
    ct=rasterio.features.rasterize(((x,1) for x in g if x is not None),
        out_shape=(H,W),transform=T,fill=0,default_value=1,all_touched=True,
        dtype='uint8').astype(bool)
    print(f"==== {reg} N={N:,}")
    for a,b,na,nb in ((cn,ct,'nlcd','tiger'),(cn,cd,'nlcd','dist'),(ct,cd,'tiger','dist')):
        d=int((a^b).sum()); print(f"  |{na} XOR {nb}| = {d:>9,}  = {100*d/N:.4f}% of grid")
    print(f"  outside-nlcd & inside-dist  (tsd px NLCD would leave fabricated) = {int((~cn&cd).sum()):,}")
    print(f"  inside-nlcd  & outside-dist (tsd px NLCD would wrongly blank)    = {int((cn&~cd).sum()):,}")
    # TreeMap / tcc  >0 outside the NLCD footprint
    for feat,yr in (('balive',2025),('tcc',2023)):
        with rasterio.open(f"data/landfire/{reg}_{yr}_{feat}.tif") as s: a=s.read(1)
        print(f"  {feat}_{yr} >0 outside NLCD footprint = {int((a[~cn]>0).sum()):,}")
        del a
    # evt nodata inside the NLCD footprint
    with rasterio.open(f"data/landfire/{reg}_2024_evt.tif") as s: ev=s.read(1)
    print(f"  evt nodata inside NLCD footprint = {int(((ev==-9999)&cn).sum()):,}   evt-nodata frac = {(ev==-9999).mean():.4f}")
    del ev, cn, cd, ct
