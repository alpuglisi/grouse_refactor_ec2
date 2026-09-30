# CR-0017 deliverable 8 sweep (PA-0023/PA-0032), read-only: does diagnose_water_bias.py's
# distance-to-water reach the NLCD coverage edge (nodata) before any water pixel?
# Run from the repo root: python docs/quality/evidence/CR-0017/sweep/water_dist_edge_probe.py
import sys, os; sys.path.insert(0, os.getcwd())
import numpy as np, pandas as pd, rasterio
from scipy.ndimage import distance_transform_edt
from grouse_data import GrouseData
import subprocess
print('HEAD', subprocess.check_output(['git','rev-parse','HEAD']).decode().strip())
import diagnose_water_bias as W
g = GrouseData()
for r in ("ME", "NH", "VT"):
    p = g[r].latest_raster_path("nlcd")
    with rasterio.open(p) as src:
        a = src.read(1); nd = src.nodata; t = src.transform
    samp = (abs(t.e), abs(t.a))
    valid = (a != nd) if nd is not None else np.ones_like(a, bool)
    valid &= (a != 0)
    vals, cnt = np.unique(a[~valid], return_counts=True)
    dist_w, tr, crs = W.build_distance_raster(p, (W.OPEN_WATER_CODE,))
    d_nd = distance_transform_edt(valid, sampling=samp)  # distance to nearest no-data pixel
    # grid edge: distance to the raster border
    h, w = a.shape
    rows, cols = np.indices(a.shape)
    d_edge = np.minimum.reduce([rows + 0.5, h - rows - 0.5, cols + 0.5, w - cols - 0.5]) * samp[0]
    d_out = np.minimum(d_nd, d_edge)
    pos = pd.concat([pd.read_csv(f"data/pipeline/{s}_positives_{r}.csv") for s in ("train", "val")])
    neg = pd.read_csv(f"data/negatives/negatives_{r}.csv")
    def frac(df):
        dw = W.sample_array(dist_w, tr, crs, df.longitude.values, df.latitude.values)
        do = W.sample_array(d_out, tr, crs, df.longitude.values, df.latitude.values)
        dn = W.sample_array(d_nd, tr, crs, df.longitude.values, df.latitude.values)
        ok = np.isfinite(dw)
        bad = ok & (dn < dw)
        lo, la = df.longitude.values[bad], df.latitude.values[bad]
        box = (f"lon {lo.min():.3f}..{lo.max():.3f}, lat {la.min():.3f}..{la.max():.3f}" if bad.any() else "-")
        return int(ok.sum()), int((do[ok] < dw[ok]).sum()), int(bad.sum()), box
    print(r, os.path.basename(p), "nodata", nd, "no-data px", int((~valid).sum()), "of", a.size,
          "values", dict(zip(vals.tolist(), cnt.tolist())))
    print("  positives (n, nearer grid-edge-or-nodata than water, nearer nodata than water):", frac(pos))
    print("  negatives:", frac(neg))
