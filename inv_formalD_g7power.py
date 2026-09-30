"""FORMAL D attack: OVER-masking of road_dist ME/VT is gated by nothing.
G1 and G2' exempt road_dist; G2 only requires outside-coverage == nodata
(satisfied a fortiori by a superset); G7 samples 400 pts/stratum.
Scenario: the coverage rasterisation uses all_touched=False (or a simplified
county union) while the VERIFIER recomputes the pinned all_touched=True mask.
Measure the damage and G7's detection probability."""
import numpy as np, rasterio, rasterio.features, geopandas as gpd, hashlib
from rasterio.transform import array_bounds
from shapely.geometry import box
from scipy.ndimage import distance_transform_edt
cty = gpd.read_file('data/roads/tl_2023_us_county.zip')
for reg in ['ME','VT']:
    with rasterio.open(f"data/landfire/{reg}_2025_nlcd.tif") as s:
        H,W,T,CRS = s.height,s.width,s.transform,s.crs
    N=H*W
    w,s_,e,n=array_bounds(H,W,T); gb=(min(w,e),min(s_,n),max(w,e),max(s_,n))
    fp=gpd.GeoSeries([box(*gb)],crs=CRS).to_crs(cty.crs).iloc[0]
    g=list(cty[cty.intersects(fp)].to_crs(CRS).geometry)
    def rast(at, geoms):
        return rasterio.features.rasterize(((x,1) for x in geoms if x is not None),
            out_shape=(H,W),transform=T,fill=0,default_value=1,all_touched=at,
            dtype='uint8').astype(bool)
    pin = rast(True, g)
    print(f"==== {reg}  pinned inside={int(pin.sum()):,}  "
          f"sha={hashlib.sha256(np.packbits(pin.ravel())).hexdigest()[:32]}")
    for tag, bad in (('all_touched=False', rast(False, g)),
                     ('union.simplify(30m)', rast(True, [gpd.GeoSeries(g,crs=CRS).union_all().simplify(30.0)]))):
        over = pin & ~bad          # legitimate in-coverage px the repair blanks
        under = ~pin & bad         # fabricated px left valid  (G2 catches these)
        print(f"  {tag}: inside={int(bad.sum()):,}")
        print(f"     OVER-masked (legit readings destroyed) = {int(over.sum()):,}  ({100*over.sum()/N:.4f}% of grid)")
        print(f"     UNDER-masked (G2 would catch)          = {int(under.sum()):,}"
              f"   -> G2 = {1 - under.sum()/max(1,(~pin).sum()):.6f} "
              f"({'FAIL' if under.sum() else 'PASS = 1.000000'})")
        # stratum-5 population: in-coverage and within 5 km of the coverage boundary
        d = distance_transform_edt(pin, sampling=(abs(T.e),abs(T.a)))   # dist inside cov to nearest outside px
        band = pin & (d <= 5000.0)
        pop = int(band.sum()); hit = int((over & band).sum())
        p = hit/max(pop,1)
        print(f"     stratum-5 population (in-cov, <=5km of cov boundary) = {pop:,}")
        print(f"     over-masked px inside that stratum = {hit:,}  -> p(one draw) = {p:.6f}")
        print(f"     P(400 draws all miss) = {(1-p)**400:.4f}   "
              f"P(2000 draws all miss) = {(1-p)**2000:.4f}")
        del d, band, over, under, bad
    del pin
