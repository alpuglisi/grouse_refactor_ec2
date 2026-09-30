"""Dump road_dist (metres) over the prediction box, split by state.
usage: python inv_road_dist_box.py <road_dist.tif> [label]
Read-only."""
import sys, numpy as np, rasterio, geopandas as gpd
from rasterio.features import rasterize
from rasterio.windows import from_bounds
from pyproj import Transformer
from models import road_dist_decode

BOUNDS = (-71.25, 44.70, -70.95, 44.90)
COUNTY_ZIP = "data/roads/tl_2023_us_county.zip"
FIPS = {"23": "ME", "33": "NH"}
path = sys.argv[1]
label = sys.argv[2] if len(sys.argv) > 2 else path

with rasterio.open(path) as src:
    tr = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
    xs, ys = tr.transform([BOUNDS[0], BOUNDS[2], BOUNDS[0], BOUNDS[2]],
                          [BOUNDS[1], BOUNDS[1], BOUNDS[3], BOUNDS[3]])
    win = from_bounds(min(xs), min(ys), max(xs), max(ys), src.transform)
    win = win.round_offsets().round_lengths()
    a = src.read(1, window=win)
    wt = src.window_transform(win)
    nd = src.nodata
    crs = src.crs
    H, W = a.shape

c = gpd.read_file(COUNTY_ZIP)
c = c[c.STATEFP.isin(FIPS)].to_crs(crs)
masks = {}
for fp, name in FIPS.items():
    masks[name] = rasterize(((g, 1) for g in c[c.STATEFP == fp].geometry
                             if g is not None), out_shape=(H, W),
                            transform=wt, fill=0, dtype="uint8").astype(bool)

nodata_m = (a == nd) if nd is not None else np.zeros_like(a, bool)
m = road_dist_decode(a.astype(np.float64))
m = np.where(nodata_m, np.nan, m)
print(f"=== {label}: {path}")
print(f"  window {H}x{W}  nodata value={nd}  nodata pixels={nodata_m.sum()} "
      f"({nodata_m.mean():.2%})")
print(f"  encoded int16 range (valid): {a[~nodata_m].min()}..{a[~nodata_m].max()}")
for name, mk in masks.items():
    s = m[mk & ~nodata_m]
    ndc = (mk & nodata_m).sum()
    if s.size == 0:
        print(f"  {name}: no valid pixels ({ndc} nodata)"); continue
    print(f"  {name}: n={s.size:6d} nodata={ndc:5d} min={s.min():8.0f}m "
          f"p10={np.percentile(s,10):8.0f}m median={np.median(s):8.0f}m "
          f"p90={np.percentile(s,90):8.0f}m max={s.max():8.0f}m mean={s.mean():8.0f}m")
if "ME" in masks and "NH" in masks:
    me = m[masks["ME"] & ~nodata_m]; nh = m[masks["NH"] & ~nodata_m]
    if me.size and nh.size:
        print(f"  ME median / NH median = {np.median(me)/max(np.median(nh),1e-9):.2f}x")
np.save(f"inv_road_dist_{label}.npy", m)
