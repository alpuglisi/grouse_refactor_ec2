"""TIGER 2023 county-union coverage mask per region, at full resolution,
exactly as generate_road_distance.py computes it (all_touched=True), plus
the all_touched=False variant to size the rasterisation fringe."""
import os, glob, numpy as np, rasterio, rasterio.features
from rasterio.transform import array_bounds
from shapely.geometry import box
import geopandas as gpd

SCRATCH = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
PAD_KM = 10.0

def padded_bounds(transform, height, width, pad_px):
    from rasterio.transform import Affine
    t = transform * Affine.translation(-pad_px, -pad_px)
    w, s, e, n = array_bounds(height + 2*pad_px, width + 2*pad_px, t)
    return (min(w, e), min(s, n), max(w, e), max(s, n))

counties = gpd.read_file("data/roads/tl_2023_us_county.zip")
print("national counties:", len(counties), counties.crs)

for r in ("ME", "NH", "VT"):
    tpl = sorted(glob.glob(f"data/landfire/{r}_*_evt.tif"))[-1]
    with rasterio.open(tpl) as s:
        transform, crs, H, W = s.transform, s.crs, s.height, s.width
    pad_px = int(round(PAD_KM * 1000.0 / abs(transform.a)))
    gb = padded_bounds(transform, H, W, pad_px)
    fp = gpd.GeoSeries([box(*gb)], crs=crs).to_crs(counties.crs).iloc[0]
    sel = counties[counties.intersects(fp)].to_crs(crs)
    print(f"\n{r}: {len(sel)} counties, states {sorted(set(sel.STATEFP))}")
    for at in (True, False):
        m = rasterio.features.rasterize(
            ((g, 1) for g in sel.geometry if g is not None),
            out_shape=(H, W), transform=transform, fill=0,
            default_value=1, all_touched=at, dtype="uint8").astype(bool)
        n = int(m.sum())
        print(f"   all_touched={at}: inside {n:,}/{m.size:,} = {n/m.size:.6f}  "
              f"outside_frac {1-n/m.size:.6f}")
        np.save(os.path.join(SCRATCH, f"{r}_tiger_at{int(at)}.npy"),
                np.packbits(m.ravel()))
        del m
