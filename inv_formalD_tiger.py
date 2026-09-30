"""FORMAL D / CR-0008 G0 `tiger_at1`: independent reproduction.
Source: data/roads/tl_2023_us_county.zip; counties intersecting the grid bbox;
rasterised onto the raster's own transform/(H,W) with all_touched=True.
Tests pad (generator's 10 km vs none), densification, and all_touched.
READ-ONLY."""
import hashlib, numpy as np, rasterio, rasterio.features, geopandas as gpd
from rasterio.transform import Affine, array_bounds
from shapely.geometry import box
PIN = {'ME': (107441621, 0.472349, '22a9995e0b920e81c205a962e7e64237'),
       'NH': ( 51386748, 0.099165, '1a29cc5bc79b7d4c73dc49e4fb9ac93a'),
       'VT': ( 50450367, 0.039980, '52e5049c360a5143146ac1342d4177f8')}
cty = gpd.read_file('data/roads/tl_2023_us_county.zip')
print(f"national counties: {len(cty)}  crs={cty.crs.to_string()}")
dg = lambda m: hashlib.sha256(np.packbits(m.ravel())).hexdigest()[:32]
for reg,(wn,wf,wh) in PIN.items():
    tpl = f"data/landfire/{reg}_2025_nlcd.tif"
    with rasterio.open(tpl) as s: H,W,T,CRS = s.height,s.width,s.transform,s.crs
    pad = int(round(10*1000.0/abs(T.a)))
    pt,ph,pw = T*Affine.translation(-pad,-pad), H+2*pad, W+2*pad
    print(f"=== {reg} {H}x{W} pad_px={pad}  pinned inside={wn:,} outfrac={wf} sha={wh}")
    for tag,(bh,bw,bt) in (('pad10km',(ph,pw,pt)), ('nopad',(H,W,T))):
        w,s_,e,n = array_bounds(bh,bw,bt)
        gb = (min(w,e),min(s_,n),max(w,e),max(s_,n))
        for dens, geom in (('plain', gpd.GeoSeries([box(*gb)],crs=CRS)),
                           ('dens30', gpd.GeoSeries([box(*gb)],crs=CRS).segmentize(30.0))):
            fp = geom.to_crs(cty.crs).iloc[0]
            sel = cty[cty.intersects(fp)]
            g = sel.to_crs(CRS).geometry
            for at in (True, False):
                m = rasterio.features.rasterize(
                    ((x,1) for x in g if x is not None), out_shape=(H,W),
                    transform=T, fill=0, default_value=1, all_touched=at,
                    dtype='uint8').astype(bool)
                c=int(m.sum()); h=dg(m)
                print(f"   {tag:8s} {dens:6s} ncty={len(sel):3d} at={at!s:5s} "
                      f"inside={c:>12,} outfrac={1-c/(H*W):.6f} sha={h}"
                      f"{'  COUNT+SHA MATCH' if (c==wn and h==wh) else ''}")
                del m
