"""What does step 5 actually need to download at TIGER 2023?
Uses generate_road_distance's own county selection. Read-only."""
import os, rasterio
from rasterio.transform import array_bounds
import generate_road_distance as g
from grouse_data import GrouseData
data = GrouseData()
need = set()
for region in ("ME", "VT", "NH"):
    rd = data[region]
    tf = next(f for f in rd.available_features() if f != "road_dist")
    with rasterio.open(rd.latest_raster_path(tf)) as src:
        crs = src.crs
        pad_px = int(round(g.PAD_KM_DEFAULT * 1000.0 / abs(src.transform.a)))
        pt, ph, pw = g.padded_grid(src.transform, src.height, src.width, pad_px)
    w, s_, e, n = array_bounds(ph, pw, pt)
    rows = g.counties_for_grid(g.load_counties(2023),
                               (min(w,e), min(s_,n), max(w,e), max(s_,n)), crs)
    fips = {f"{a}{b}" for a, b in zip(rows.STATEFP, rows.COUNTYFP)}
    miss = {f for f in fips
            if not os.path.exists(f"data/roads/tl_2023_{f}_roads.zip")}
    by_state = {}
    for f in sorted(fips): by_state[f[:2]] = by_state.get(f[:2], 0) + 1
    print(f"{region}: {len(fips)} counties {by_state} | uncached: {len(miss)} "
          f"{sorted(miss) if miss else ''}")
    need |= miss
print(f"\nUNIQUE uncached county road files to download at TIGER 2023: {len(need)}")
print(f"national county file cached: {os.path.exists('data/roads/tl_2023_us_county.zip')}")
