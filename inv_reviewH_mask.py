"""Reviewer H / CR-0008 G1 attack: G1 and G2 both consume the SAME coverage
mask.  How far apart do *defensible* derivations of that mask sit on the real
ME grid, and what does the gap cost?"""
import sys, numpy as np, rasterio, rasterio.features, geopandas as gpd
from shapely.geometry import box

TEMPLATE = "data/landfire/ME_2025_tsd.tif"
with rasterio.open(TEMPLATE) as src:
    H, W, T, CRS = src.height, src.width, src.transform, src.crs
N = H * W
print(f"ME grid {W} x {H} = {N:,} px;  0.05% budget = {int(0.0005*N):,} px")

cty = gpd.read_file("data/roads/tl_2023_us_county.zip")
print("national counties:", len(cty), "crs", cty.crs.to_string())
gb = rasterio.transform.array_bounds(H, W, T)          # (minx,miny,maxx,maxy)
fp = gpd.GeoSeries([box(*gb)], crs=CRS).to_crs(cty.crs).iloc[0]
sel = cty[cty.intersects(fp)]
print("counties intersecting ME grid bbox:", len(sel),
      "states:", sorted(sel.STATEFP.unique()))

def rast(geoms, all_touched):
    return rasterio.features.rasterize(
        ((g, 1) for g in geoms if g is not None), out_shape=(H, W),
        transform=T, fill=0, default_value=1, all_touched=all_touched,
        dtype="uint8").astype(bool)

# --- variant 1: exactly what generate_road_distance.py does today
g_proj = sel.to_crs(CRS).geometry
M_at = rast(g_proj, True)
# --- variant 2: identical, all_touched=False (the other obvious choice)
M_af = rast(g_proj, False)
# --- variant 3: densify in 4326 (30 m ~ 3e-4 deg) before reprojecting,
#     the fix CR-0008 requires for counties_for_grid's footprint
g_dens = sel.to_crs(4326).geometry.segmentize(3e-4).to_crs(CRS)
M_dn = rast(g_dens, True)
# --- variant 4: dissolve first, then rasterize (CR-0007 uses dissolve-by-
#     STATEFP for verify_partition; a natural thing to reuse)
g_diss = gpd.GeoSeries([sel.to_crs(CRS).geometry.union_all()], crs=CRS)
M_ds = rast(g_diss, True)

with rasterio.open("data/landfire/ME_2025_nlcd.tif") as s:
    nlcd = s.read(1)
M_nl = (nlcd != -9999) & (nlcd != -32768) & (nlcd != 32767) & (nlcd != -1111)
del nlcd

V = {"TIGER all_touched=True (code today)": M_at,
     "TIGER all_touched=False": M_af,
     "TIGER densified+all_touched=True": M_dn,
     "TIGER dissolved+all_touched=True": M_ds,
     "NLCD valid footprint (the 'cross-check')": M_nl}
for k, m in V.items():
    print(f"  {k:42s} inside {m.sum():12,}  ({100*m.sum()/N:8.4f}% of grid)")

print("\npairwise disagreement, px and % of grid (A-not-B / B-not-A):")
ks = list(V)
for i in range(len(ks)):
    for j in range(i+1, len(ks)):
        a, b = V[ks[i]], V[ks[j]]
        an = int((a & ~b).sum()); bn = int((b & ~a).sum())
        print(f"  {ks[i][:34]:34s} vs {ks[j][:34]:34s}  "
              f"{an:>10,} ({100*an/N:6.4f}%) / {bn:>10,} ({100*bn/N:6.4f}%)")
np.save("inv_reviewH_M_at.npy", M_at); np.save("inv_reviewH_M_af.npy", M_af)
np.save("inv_reviewH_M_dn.npy", M_dn); np.save("inv_reviewH_M_nl.npy", M_nl)
