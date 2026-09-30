"""Is any footprint recoverable from data/treemap_raw (post unmask(0)) ?
And what do the derived tcc/treemap/tsd rasters read outside the NLCD footprint?"""
import os, glob, numpy as np, rasterio
from pyproj import Transformer

print("=== raw TreeMap headers / value ranges (ME 2022 BALIVE) ===")
for p in sorted(glob.glob("data/treemap_raw/TreeMap*_ME_*.tif")):
    with rasterio.open(p) as s:
        print(f"{os.path.basename(p):38s} {s.width}x{s.height} {s.dtypes[0]} "
              f"nodata={s.nodata} crs={s.crs.to_epsg()} masks={s.mask_flag_enums[0]}")
p = "data/treemap_raw/TreeMap2022_ME_BALIVE.tif"
with rasterio.open(p) as s:
    tf = Transformer.from_crs("EPSG:4326", s.crs, always_xy=True)
    # deep Quebec, far Atlantic, mid-Maine forest, Penobscot Bay water
    pts = {"Quebec_47.6N_-69.5": (-69.5, 47.6),
           "Atlantic_43.0N_-68.0": (-68.0, 43.0),
           "Maine_forest_45.5N_-69.5": (-69.5, 45.5),
           "PenobscotBay_44.0N_-68.8": (-68.8, 44.0),
           "NB_Canada_45.8N_-67.0": (-67.0, 45.8)}
    for k, (lon, lat) in pts.items():
        x, y = tf.transform(lon, lat)
        try:
            v = list(s.sample([(x, y)]))[0][0]
        except Exception as e:
            v = f"ERR {e}"
        print(f"  {k:28s} -> {v}")
    a = s.read(1)
    print(f"  full-raster: min {a.min()} max {a.max()} n_zero {int((a==0).sum()):,}"
          f" / {a.size:,} = {(a==0).mean():.4f}; any nan {bool(np.isnan(a).any())};"
          f" any<0 {int((a<0).sum())}")
    v, c = np.unique(a[a < 1e-6], return_counts=True)
    print(f"  distinct values below 1e-6: {list(zip(v[:5], c[:5]))}")
