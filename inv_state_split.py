"""Compare suitability scores on the Maine vs New Hampshire side of the
state line inside a prediction GeoTIFF. Read-only.

usage: python inv_state_split.py tif [tif ...]
"""
import sys, numpy as np, rasterio, geopandas as gpd
from rasterio.features import rasterize

COUNTY_ZIP = "data/roads/tl_2023_us_county.zip"
FIPS = {"23": "ME", "33": "NH", "50": "VT"}

def state_masks(src):
    c = gpd.read_file(COUNTY_ZIP)
    c = c[c.STATEFP.isin(FIPS)].to_crs(src.crs)
    out = {}
    for fp, name in FIPS.items():
        geoms = c[c.STATEFP == fp].geometry
        out[name] = rasterize(((g, 1) for g in geoms if g is not None),
                              out_shape=(src.height, src.width),
                              transform=src.transform, fill=0,
                              dtype="uint8").astype(bool)
    return out

def report(path, masks=None):
    with rasterio.open(path) as src:
        a = src.read(1, masked=True).filled(np.nan)
        if masks is None:
            masks = state_masks(src)
    print(f"\n=== {path}  shape={a.shape}")
    fin = np.isfinite(a)
    v = a[fin]
    print(f"  all valid: n={v.size} min={v.min():.4f} median={np.median(v):.4f} "
          f"mean={v.mean():.4f} max={v.max():.4f} p>=0.5={(v>=.5).mean():.3%} "
          f"p>=0.8={(v>=.8).mean():.3%}")
    stats = {}
    for name, m in masks.items():
        s = a[m & fin]
        if s.size == 0:
            print(f"  {name}: no pixels"); continue
        stats[name] = s
        print(f"  {name}: n={s.size:6d} mean={s.mean():.4f} median={np.median(s):.4f} "
              f"p10={np.percentile(s,10):.4f} p90={np.percentile(s,90):.4f} "
              f">=0.5={(s>=.5).mean():6.2%} >=0.8={(s>=.8).mean():6.2%}")
    if "ME" in stats and "NH" in stats:
        me, nh = stats["ME"], stats["NH"]
        print(f"  ME-NH mean diff: {me.mean()-nh.mean():+.4f}  "
              f"median diff: {np.median(me)-np.median(nh):+.4f}")
        # rank: fraction of random ME pixel > random NH pixel (AUC-style)
        from scipy.stats import mannwhitneyu
        u = mannwhitneyu(me, nh, alternative="two-sided")
        print(f"  P(ME pixel > NH pixel) = {u.statistic/(me.size*nh.size):.4f}"
              f"  (0.5 = no difference)")
    return masks

if __name__ == "__main__":
    masks = None
    for p in sys.argv[1:]:
        masks = report(p, masks)
