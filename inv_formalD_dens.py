"""FORMAL D: the CR deliverable adds 'densified footprint reprojection' to
counties_for_grid.  G0's tiger_at1 pin is computed from UNDENSIFIED county
polygons reprojected 4269 -> local Albers.  The ME/NH/VT northern border is the
45th parallel: a straight line in lat/lon, a CURVE in Albers.  Does densifying
the COUNTY geometries (the natural misreading of that deliverable) move the
coverage mask, and in which direction?"""
import numpy as np, rasterio, rasterio.features, geopandas as gpd, hashlib
from rasterio.transform import array_bounds
from shapely.geometry import box
cty = gpd.read_file('data/roads/tl_2023_us_county.zip')
PIN={'ME':(107441621,'22a9995e0b920e81c205a962e7e64237'),
     'NH':( 51386748,'1a29cc5bc79b7d4c73dc49e4fb9ac93a'),
     'VT':( 50450367,'52e5049c360a5143146ac1342d4177f8')}
for reg,(wn,wh) in PIN.items():
    with rasterio.open(f"data/landfire/{reg}_2025_nlcd.tif") as s:
        H,W,T,CRS=s.height,s.width,s.transform,s.crs
    N=H*W
    w,s_,e,n=array_bounds(H,W,T); gb=(min(w,e),min(s_,n),max(w,e),max(s_,n))
    fp=gpd.GeoSeries([box(*gb)],crs=CRS).to_crs(cty.crs).iloc[0]
    sel=cty[cty.intersects(fp)]
    def rast(geoms):
        return rasterio.features.rasterize(((x,1) for x in geoms if x is not None),
            out_shape=(H,W),transform=T,fill=0,default_value=1,all_touched=True,
            dtype='uint8').astype(bool)
    plain = rast(list(sel.to_crs(CRS).geometry))
    h=hashlib.sha256(np.packbits(plain.ravel())).hexdigest()[:32]
    print(f"==== {reg}: undensified inside={int(plain.sum()):,} sha={h} "
          f"{'PIN-MATCH' if (int(plain.sum())==wn and h==wh) else 'PIN-MISMATCH'}")
    for step in (1000.0, 100.0, 30.0):   # densify in DEGREES-space source CRS
        deg = step/111320.0
        dens = rast(list(sel.geometry.segmentize(deg).to_crs(CRS)))
        over = plain & ~dens; under = ~plain & dens
        g2 = 1 - under.sum()/max(1,(~plain).sum())
        print(f"  segmentize ~{step:.0f} m before reproject: inside={int(dens.sum()):,} "
              f"delta={int(dens.sum())-int(plain.sum()):+,}")
        print(f"     OVER-masked vs pin (legit destroyed) = {int(over.sum()):>8,}"
              f"  UNDER-masked = {int(under.sum()):>8,}   G2 = {g2:.6f} "
              f"({'FAIL' if under.sum() else 'PASS = 1.000000'})")
        del dens, over, under
    del plain
