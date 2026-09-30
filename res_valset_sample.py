"""Sample the 9 continuous FEATURE_SPEC rasters (2023 vintage, present for
every feature in every region) at the pooled base points.  READ-ONLY."""
import os, sys, glob
import numpy as np, pandas as pd, rasterio, rasterio.warp
os.chdir("/home/ec2-user/grouse2"); sys.path.insert(0, ".")
from grouse_data import NODATA_SENTINELS
SP = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
base = pd.read_csv(SP + "/base.csv")
CONT = ["ch", "cc", "tcc", "road_dist", "tsd", "balive", "tpa_live", "qmd", "carbon_dwn"]
DIRS = {}
out = pd.DataFrame(index=base.index)
for f in CONT:
    col = np.full(len(base), np.nan)
    for r in ["ME", "NH", "VT"]:
        d = DIRS.get(f, "data/landfire")
        p = f"{d}/{r}_2023_{f}.tif"
        if not os.path.exists(p):
            cand = sorted(glob.glob(f"data/*/{r}_*_{f}.tif"))
            print("  MISSING", p, "->", cand[-1] if cand else None); p = cand[-1]
        m = (base.state == r).values
        pts = list(zip(base.longitude[m], base.latitude[m]))
        with rasterio.open(p) as src:
            tr = rasterio.warp.transform("EPSG:4326", src.crs, [q[0] for q in pts], [q[1] for q in pts])
            vals = np.array([v[0] for v in src.sample(list(zip(*tr)))], dtype=float)
        col[m] = vals
    col[np.isin(col, NODATA_SENTINELS)] = np.nan
    out[f] = col
    print(f"{f:11s} n={np.isfinite(col).sum():5d} nan={np.isnan(col).sum():4d} "
          f"min={np.nanmin(col):.0f} med={np.nanmedian(col):.0f} max={np.nanmax(col):.0f}")
out.to_csv(SP + "/feat.csv", index=False)
print("wrote feat.csv")
