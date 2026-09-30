"""FORMAL D: road_dist N_pre rows against the pinned tiger_at1 mask."""
import glob,re,numpy as np,rasterio,rasterio.features,geopandas as gpd,hashlib
from shapely.geometry import box
SENT=(-9999,-32768,32767,-1111)
PIN={'ME':(107441621,'22a9995e0b920e81c205a962e7e64237',96180811),
     'NH':(51386748,'1a29cc5bc79b7d4c73dc49e4fb9ac93a',0),
     'VT':(50450367,'52e5049c360a5143146ac1342d4177f8',2100978)}
cty=gpd.read_file('data/roads/tl_2023_us_county.zip')
for reg,(wn,wh,npre) in PIN.items():
    with rasterio.open(f"data/landfire/{reg}_2025_nlcd.tif") as s:
        H,W,T,CRS=s.height,s.width,s.transform,s.crs
    from rasterio.transform import array_bounds
    w,s_,e,n=array_bounds(H,W,T); gb=(min(w,e),min(s_,n),max(w,e),max(s_,n))
    fp=gpd.GeoSeries([box(*gb)],crs=CRS).to_crs(cty.crs).iloc[0]
    g=cty[cty.intersects(fp)].to_crs(CRS).geometry
    cov=rasterio.features.rasterize(((x,1) for x in g if x is not None),
        out_shape=(H,W),transform=T,fill=0,default_value=1,all_touched=True,
        dtype='uint8').astype(bool)
    assert int(cov.sum())==wn and hashlib.sha256(np.packbits(cov.ravel())).hexdigest()[:32]==wh
    print(f"==== {reg} tiger mask OK, outside={int((~cov).sum()):,}  N_pre(pinned)={npre:,}")
    for p in sorted(glob.glob(f"data/landfire/{reg}_*_road_dist.tif")):
        yr=re.search(r'_(\d{4})_',p).group(1)
        with rasterio.open(p) as s: a=s.read(1)
        isnd=np.isin(a,SENT)
        chg=int((~cov&~isnd).sum()); ndin=int((cov&isnd).sum())
        print(f"   {yr} |changed|={chg:>12,} delta={chg-npre:>+9,} nodata_inside_cov={ndin:>9,}"
              + ("" if chg==npre else "  <-- MISMATCH"))
        del a,isnd
