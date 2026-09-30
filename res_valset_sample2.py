"""Sample UNMODELLED spatial covariates (not in models.FEATURE_SPEC) at the
base points: terrain (slope, gradient), lidar elevation where present, plus
the CSV's own observer/density columns.  READ-ONLY."""
import os, sys, glob
import numpy as np, pandas as pd, rasterio, rasterio.warp
os.chdir("/home/ec2-user/grouse2"); sys.path.insert(0, ".")
from grouse_data import NODATA_SENTINELS
SP = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
base = pd.read_csv(SP + "/base.csv")
out = pd.DataFrame(index=base.index)
for f, yr in [("slope", 2020), ("gradient", 2020), ("lidar_elev", 2016)]:
    col = np.full(len(base), np.nan)
    for r in ["ME", "NH", "VT"]:
        p = f"data/landfire/{r}_{yr}_{f}.tif"
        if not os.path.exists(p):
            print("  absent:", p); continue
        m = (base.state == r).values
        with rasterio.open(p) as src:
            tr = rasterio.warp.transform("EPSG:4326", src.crs,
                                         list(base.longitude[m]), list(base.latitude[m]))
            col[m] = [v[0] for v in src.sample(list(zip(*tr)))]
    col[np.isin(col, NODATA_SENTINELS)] = np.nan
    out[f] = col
    print(f"{f:11s} n={np.isfinite(col).sum():5d} min={np.nanmin(col):.1f} "
          f"med={np.nanmedian(col):.1f} max={np.nanmax(col):.1f}")
out['spatial_density'] = base['spatial_density'].values
out['n_visits'] = base['n_visits'].values
out['year'] = base['year'].values
out.to_csv(SP + "/unmod.csv", index=False)
print("wrote unmod.csv")
