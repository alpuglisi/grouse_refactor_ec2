"""Formal review B / CR-0008 G0: reproduce the pre-registered disturbance-
intersection masks (`disturbance∩`).  READ-ONLY (reads only source rasters).

covered(pixel) = AND over consulted vintages of (value not in
grouse_data.NODATA_SENTINELS), warped onto the region grid exactly as
generate_time_since_disturbance.py does (WarpedVRT, nearest).
"""
import sys, re, glob, hashlib, os, time
import numpy as np, rasterio
from rasterio.vrt import WarpedVRT
from rasterio.enums import Resampling
from rasterio.windows import Window

SENT = (-9999, -32768, 32767, -1111)
EXPECT = {'ME': (107321500, '9006374548fa58f4a59e3ff14c24130d'),
          'NH': ( 51379852, 'c10c46f12978de0e68fd1ded93b65a84'),
          'VT': ( 50447193, '64677a7523a8b20e24f1e595dbf8c39a')}
reg = sys.argv[1]
maxyear = int(sys.argv[2]) if len(sys.argv) > 2 else 2025
tpl = f"data/landfire/{reg}_2025_nlcd.tif"

def dyear(p):
    yy = int(re.search(r"Dist(\d{2})", os.path.basename(p)).group(1))
    return 1900+yy if yy >= 90 else 2000+yy

paths = {}
for p in sorted(glob.glob(
    "data/disturbance/USAnnualDisturbance_1999_present/*/*/Tif/*.tif")):
    paths[dyear(p)] = p
use = {d: p for d, p in sorted(paths.items()) if d <= maxyear}
print(f"{reg}: {len(use)} vintages {min(use)}-{max(use)} (<= {maxyear})")

with rasterio.open(tpl) as ref:
    H, W, T, CRS = ref.height, ref.width, ref.transform, ref.crs
cov = np.ones((H, W), dtype=bool)
BR = 1024
t0 = time.time()
srcs, vrts = [], []
try:
    for d, p in sorted(use.items()):
        s = rasterio.open(p); srcs.append(s)
        vrts.append(WarpedVRT(s, crs=CRS, transform=T, width=W, height=H,
                              resampling=Resampling.nearest))
    for r0 in range(0, H, BR):
        n = min(BR, H - r0)
        win = Window(0, r0, W, n)
        blk = np.ones((n, W), dtype=bool)
        for v in vrts:
            a = v.read(1, window=win)
            blk &= ~np.isin(a, SENT)
        cov[r0:r0+n] = blk
        if r0 % (BR*8) == 0:
            print(f"   rows {r0}/{H}  {time.time()-t0:.0f}s", flush=True)
finally:
    for v in vrts: v.close()
    for s in srcs: s.close()
n = int(cov.sum()); h = hashlib.sha256(np.packbits(cov.ravel())).hexdigest()
wn, wh = EXPECT[reg]
print(f"{reg} maxyear={maxyear}: inside={n:,}  outside_frac={1-n/(H*W):.6f}")
print(f"   sha256[:32]={h[:32]}   expected inside={wn:,} sha={wh}")
print(f"   COUNT {'MATCH' if n==wn else 'MISMATCH diff=%d'%(n-wn)} | SHA {'MATCH' if h[:32]==wh else 'MISMATCH'}")
np.save(f"inv_formalB_cov_{reg}_{maxyear}.npy", cov)
