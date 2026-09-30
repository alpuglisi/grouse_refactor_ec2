"""Formal review B / CR-0008 G0: reproduce the pre-registered `tiger_at1`
masks, under several defensible county-selection recipes.  READ-ONLY."""
import hashlib, numpy as np, rasterio, rasterio.features, geopandas as gpd
from rasterio.transform import Affine, array_bounds
from shapely.geometry import box

EXPECT = {'ME': (107441621, '22a9995e0b920e81c205a962e7e64237'),
          'NH': ( 51386748, '1a29cc5bc79b7d4c73dc49e4fb9ac93a'),
          'VT': ( 50450367, '52e5049c360a5143146ac1342d4177f8')}
TPL = {'ME':'data/landfire/ME_2025_nlcd.tif',
       'NH':'data/landfire/NH_2025_nlcd.tif',
       'VT':'data/landfire/VT_2025_nlcd.tif'}
cty = gpd.read_file('data/roads/tl_2023_us_county.zip')
print('national counties', len(cty), cty.crs.to_string())

def dig(m): return hashlib.sha256(np.packbits(m.ravel())).hexdigest()[:32]

for reg,(wn,wh) in EXPECT.items():
    with rasterio.open(TPL[reg]) as s:
        H,W,T,CRS = s.height,s.width,s.transform,s.crs
    pad = int(round(10*1000.0/abs(T.a)))
    pt = T*Affine.translation(-pad,-pad); ph,pw = H+2*pad, W+2*pad
    b_pad = array_bounds(ph,pw,pt); b_raw = array_bounds(H,W,T)
    sels = {}
    for tag,b in (('pad10km',b_pad),('nopad',b_raw)):
        gb=(min(b[0],b[2]),min(b[1],b[3]),max(b[0],b[2]),max(b[1],b[3]))
        fp = gpd.GeoSeries([box(*gb)],crs=CRS).to_crs(cty.crs).iloc[0]
        sels[tag] = cty[cty.intersects(fp)]
        # densified-footprint variant
        fpd = gpd.GeoSeries([box(*gb)],crs=CRS).segmentize(30.0).to_crs(cty.crs).iloc[0]
        sels[tag+'_densfp'] = cty[cty.intersects(fpd)]
    print(f"=== {reg} grid {H}x{W} pad_px={pad} expect inside={wn:,} sha={wh}")
    for tag,sel in sels.items():
        g = sel.to_crs(CRS).geometry
        for at in (True,False):
            m = rasterio.features.rasterize(((x,1) for x in g if x is not None),
                out_shape=(H,W), transform=T, fill=0, default_value=1,
                all_touched=at, dtype='uint8').astype(bool)
            n=int(m.sum()); h=dig(m)
            print(f"  {tag:16s} ncty={len(sel):3d} all_touched={at!s:5s} inside={n:>12,} sha={h}"
                  f"{' COUNT-MATCH' if n==wn else ''}{' SHA-MATCH' if h==wh else ''}")
            del m
