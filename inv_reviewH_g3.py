"""CR-0008 G3 attack: G3 mandates full-resolution *measurement*.  It says
nothing about the resolution at which the coverage *mask* is derived.  If the
mask is derived coarsely and upsampled, G1 and G2 are still satisfied exactly
at full resolution, because the repair and the gate read the same mask."""
import numpy as np, rasterio, rasterio.features, geopandas as gpd
from rasterio.transform import Affine
from shapely.geometry import box

with rasterio.open("data/landfire/ME_2025_tsd.tif") as s:
    H, W, T, CRS = s.height, s.width, s.transform, s.crs
    tsd = s.read(1); TSD_ND = s.nodata
N = H*W
cty = gpd.read_file("data/roads/tl_2023_us_county.zip")
gb = rasterio.transform.array_bounds(H, W, T)
fp = gpd.GeoSeries([box(*gb)], crs=CRS).to_crs(cty.crs).iloc[0]
g = cty[cty.intersects(fp)].to_crs(CRS).geometry

M_full = rasterio.features.rasterize(((x,1) for x in g), out_shape=(H,W),
    transform=T, fill=0, default_value=1, all_touched=True, dtype="uint8").astype(bool)

def coarse_mask(k):
    h, w = (H + k - 1)//k, (W + k - 1)//k
    t = T * Affine.scale(k)
    m = rasterio.features.rasterize(((x,1) for x in g), out_shape=(h,w),
        transform=t, fill=0, default_value=1, all_touched=True,
        dtype="uint8").astype(bool)
    return np.repeat(np.repeat(m, k, 0), k, 1)[:H, :W]

M_nl = np.load("inv_reviewH_M_nl.npy")
legit = tsd != TSD_ND            # tsd today is fabricated everywhere outside US
print(f"ME grid {N:,}px.  0.05%-of-grid budget = {int(5e-4*N):,}px per direction")
print(f"tsd non-nodata today: {legit.sum():,} ({100*legit.sum()/N:.4f}%)\n")

for k in (1, 4, 8):
    M = M_full if k == 1 else coarse_mask(k)
    outside = ~M
    # the repair: every outside-coverage pixel that is not already nodata
    changed = outside & legit
    # G1: changed subset of outside  -> violations
    g1 = int((changed & M).sum())
    # G2: fraction of outside-coverage px reading nodata AFTER repair
    after_nd = (~legit) | changed          # nodata after
    g2 = float(after_nd[outside].mean())
    # real-world damage, judged against NLCD's footprint
    destroyed = int((M_nl & outside & legit).sum())     # in-US data thrown away
    kept_fab  = int(((~M_nl) & M & legit).sum())        # out-of-US left fabricated
    xa = int((M & ~M_nl).sum()); xb = int((M_nl & ~M).sum())
    tag = "full-res mask" if k == 1 else f"mask derived at {k}x, upsampled"
    print(f"{tag}")
    print(f"   G1 violating px ............ {g1}            required 0  -> "
          f"{'PASS' if g1==0 else 'FAIL'}")
    print(f"   G2 outside-cov nodata frac .. {g2:.6f}     required 1.000000 -> "
          f"{'PASS' if g2==1.0 else 'FAIL'}")
    print(f"   in-US pixels DESTROYED ...... {destroyed:,}")
    print(f"   out-of-US left FABRICATED ... {kept_fab:,}")
    print(f"   NLCD cross-check (not a gate) {100*xa/N:.4f}% / {100*xb/N:.4f}% "
          f"of grid   budget 0.0500% -> "
          f"{'within' if max(xa,xb) <= 5e-4*N else 'OVER BUDGET'}")
    print()
