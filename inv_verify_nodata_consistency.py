"""Author-side verification of reviewer A's Concern 10: where the
LANDFIRE reference (evt) is nodata, what do the other feature rasters
say? Read-only. PA-0017: uncovered area must be nodata, not a
legitimate-looking value."""
import numpy as np, rasterio
from grouse_data import GrouseData
STEP = 8
for region in ("ME", "NH"):
    rd = GrouseData()[region]
    feats = [f for f in rd.available_features()]
    with rasterio.open(rd.latest_raster_path("evt")) as s:
        evt = s.read(1)[::STEP, ::STEP]; evt_nd = s.nodata
    mask = evt == evt_nd
    print(f"\n=== {region}: evt nodata over {mask.mean():.1%} of the grid "
          f"({mask.sum():,} sampled px) ===")
    print(f"{'feature':12s} {'nodata_frac':>11s} {'uniq':>5s}  most common value there")
    for f in feats:
        if f == "evt": continue
        with rasterio.open(rd.latest_raster_path(f)) as s:
            a = s.read(1)[::STEP, ::STEP]; nd = s.nodata
        v = a[mask]
        if v.size == 0: continue
        ndf = (v == nd).mean() if nd is not None else 0.0
        vals, cnt = np.unique(v, return_counts=True)
        top = vals[np.argmax(cnt)]
        flag = "  <-- FABRICATED" if ndf < 0.5 else ""
        print(f"{f:12s} {ndf:11.3f} {len(vals):5d}  {top}{flag}")
