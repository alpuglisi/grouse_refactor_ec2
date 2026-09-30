"""FORMAL D / CR-0008 G0 `disturbance∩`: independent reproduction.
Predicate: covered = AND over consulted vintages of (value not in
NODATA_SENTINELS), warped onto the region grid exactly as
generate_time_since_disturbance.py does (WarpedVRT, nearest, ref transform).
maxyear lets us test the CR's load-bearing claim that cov_2016 == cov_2025
(the tsd generator consults only vintages d <= output year).
READ-ONLY: reads source rasters, writes one bool .npy into the scratchpad."""
import sys, re, glob, hashlib, os, time
import numpy as np, rasterio
from rasterio.vrt import WarpedVRT
from rasterio.enums import Resampling
from rasterio.windows import Window
SENT = (-9999, -32768, 32767, -1111)
PIN = {'ME': (107321500, 0.472939, '9006374548fa58f4a59e3ff14c24130d'),
       'NH': ( 51379852, 0.099286, 'c10c46f12978de0e68fd1ded93b65a84'),
       'VT': ( 50447193, 0.040040, '64677a7523a8b20e24f1e595dbf8c39a')}
SCRATCH = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
reg = sys.argv[1]; maxyear = int(sys.argv[2])
def dy(p):
    yy = int(re.search(r"Dist(\d{2})", os.path.basename(p)).group(1))
    return 1900+yy if yy >= 90 else 2000+yy
paths = {dy(p): p for p in sorted(glob.glob(
    "data/disturbance/USAnnualDisturbance_1999_present/*/*/Tif/*.tif"))}
use = {d: p for d, p in sorted(paths.items()) if d <= maxyear}
tpl = f"data/landfire/{reg}_2025_nlcd.tif"
with rasterio.open(tpl) as r: H, W, T, CRS = r.height, r.width, r.transform, r.crs
print(f"{reg} maxyear={maxyear}: {len(use)} vintages {min(use)}-{max(use)}  grid {H}x{W}")
cov = np.ones((H, W), dtype=bool); BR = 2048; t0 = time.time()
srcs, vrts = [], []
try:
    for d, p in sorted(use.items()):
        s = rasterio.open(p); srcs.append(s)
        vrts.append(WarpedVRT(s, crs=CRS, transform=T, width=W, height=H,
                              resampling=Resampling.nearest))
    for r0 in range(0, H, BR):
        n = min(BR, H - r0); win = Window(0, r0, W, n)
        blk = np.ones((n, W), dtype=bool)
        for v in vrts:
            blk &= ~np.isin(v.read(1, window=win), SENT)
        cov[r0:r0+n] = blk
finally:
    for v in vrts: v.close()
    for s in srcs: s.close()
c = int(cov.sum()); h = hashlib.sha256(np.packbits(cov.ravel())).hexdigest()[:32]
wn, wf, wh = PIN[reg]
print(f"  inside={c:,}  outfrac={1-c/(H*W):.6f}  sha={h}   [{time.time()-t0:.0f}s]")
print(f"  pinned inside={wn:,} outfrac={wf} sha={wh}")
print(f"  COUNT {'MATCH' if c==wn else f'MISMATCH ({c-wn:+,})'} | SHA {'MATCH' if h==wh else 'MISMATCH'}")
np.save(f"{SCRATCH}/covD_{reg}_{maxyear}.npy", cov)
