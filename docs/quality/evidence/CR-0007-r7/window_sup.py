"""Window-drop count on the post-buffer pool (all rasters of every FEATURE_SPEC
feature, header-only) and SUP-O / SUP-R before/after the §5-mandated drop."""
import sys, os, glob, numpy as np, pandas as pd, rasterio
sys.path.insert(0, "/home/ec2-user/grouse2"); os.chdir("/home/ec2-user/grouse2")
sys.path.insert(0, "/tmp/claude-1000/-home-ec2-user-grouse2/f462782e-8989-4c4d-919a-db7e5946838a/scratchpad/cr0007_A")
from lib import *
from pyproj import Transformer
from scipy.spatial import cKDTree
from grouse_data import GrouseData
from models import FEATURE_SPEC
data = GrouseData()
pos = split_positives(pd.read_csv(f"{OUT}/pos_thinned.csv"))
P = pd.read_csv(f"{OUT}/pool_prebuffer.csv", low_memory=False)
pool = P[P.d_grouse > 300].copy()
HALF = 32
def windowed(df, r):
    ok = np.ones(len(df), bool); rd = data[r]
    feats = [f for f in rd.available_features() if f in FEATURE_SPEC]
    files = set()
    for f in feats:
        for y in rd.raster_years(f):
            files.add(rd.raster_path(f, y, validate=False))
    grids = {}
    for fp in files:
        with rasterio.open(fp) as s:
            grids[(s.crs.to_string(), tuple(s.transform)[:6], s.width, s.height)] = 1
    for (crs, tr, w, h) in grids:
        t = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
        x, y = t.transform(df.longitude.values, df.latitude.values)
        A = rasterio.Affine(*tr)
        c, rr = ~A * (np.asarray(x), np.asarray(y))
        c = np.floor(c).astype(int); rr = np.floor(rr).astype(int)
        ok &= (c - HALF >= 0) & (c + HALF <= w) & (rr - HALF >= 0) & (rr + HALF <= h)
    return ok, len(files), len(grids)
pool['win'] = True
for r in R:
    m = (pool.state == r).values
    ok, nf, ng = windowed(pool[m], r)
    pool.loc[m, 'win'] = ok
    pm = (pos.state == r).values
    okp, _, _ = windowed(pos[pm], r)
    print(r, "files", nf, "grids", ng, "pool windowless", int((~ok).sum()), "of", int(m.sum()),
          " positives windowless", int((~okp).sum()))
pool.to_csv(f"{OUT}/pool_post.csv", index=False)

def sup(pos, cand):
    res = {}; outl = 0
    for r in R:
        p = pos[pos.state == r]; c = cand[cand.state == r]
        d = cKDTree(c[['x_5070', 'y_5070']].values).query(p[['x_5070', 'y_5070']].values)[0]
        cell = (np.floor(p.x_5070.values / 1e4).astype(int) * 100000 + np.floor(p.y_5070.values / 1e4).astype(int))
        s = pd.DataFrame({'c': cell, 'd': d})
        g = s.groupby('c').d
        med = g.median()[g.size() >= 5]
        m = med.median()
        outl += int((d > 10 * m).sum())
        res[f'SUPR_{r}'] = round(float(med.max() / m), 3)
        res[f'SUPO_{r}'] = int((d > 10 * m).sum())
    res['SUPO_total'] = outl
    return res
print("SUP, pool as-is:", sup(pos, pool))
print("SUP, windowless dropped:", sup(pos, pool[pool.win]))
