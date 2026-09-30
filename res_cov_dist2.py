"""LANDFIRE Annual Disturbance footprint, derived locally and CORRECTLY.

The vintages use FOUR distinct out-of-coverage codes, all of which are already
in grouse_data.NODATA_SENTINELS:
   -9999  "Fill-NoData"     (in every vintage's shipped CSV_Data table)
   -1111  "Fill-Not Mapped" (in the table; 51.8M px on the ME grid in LF2020)
   32767  the declared GeoTIFF nodata tag (in NO table)
  -32768  (also a declared tag on LF2022_Dist22) / out-of-source-extent
covered  <=>  value not in SENTINELS  and  value != src.nodata.
Reprojection is identical to generate_time_since_disturbance.py (WarpedVRT,
nearest) so the mask is index-for-index with the tsd rasters.

Also emits cov_all restricted to the vintages a given OUTPUT year consults
(vintages <= y), which is what tsd's value actually depends on.
"""
import os, sys, glob, re, time
import numpy as np, rasterio
from rasterio.vrt import WarpedVRT
from rasterio.enums import Resampling

SCRATCH = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
DIST = "data/disturbance/USAnnualDisturbance_1999_present"
SENT = (-9999, -32768, 32767, -1111)
VRT_FILL = -32768
OUT_YEARS = (2016, 2025)

def dist_paths():
    found = {}
    for p in glob.glob(os.path.join(DIST, "**", "*.tif"), recursive=True):
        m = re.search(r"Dist(\d{2})", os.path.basename(p))
        if not m: continue
        yy = int(m.group(1)); y = 1900+yy if yy >= 90 else 2000+yy
        if y not in found or p > found[y]: found[y] = p
    return found

def load(region, name, shape):
    a = np.load(os.path.join(SCRATCH, f"{region}_{name}.npy"))
    return np.unpackbits(a)[:shape[0]*shape[1]].astype(bool).reshape(shape)

region = sys.argv[1]
tpl = sorted(glob.glob(f"data/landfire/{region}_*_evt.tif"))[-1]
with rasterio.open(tpl) as s: H, W, crs, T = s.height, s.width, s.crs, s.transform
tot = H*W
nlcd = load(region, "nlcd", (H, W)); evt = load(region, "evt", (H, W))
tiger = load(region, "tiger_at1", (H, W))
print(f"{region} grid {W}x{H} = {tot:,}  nlcd {nlcd.sum():,} ({nlcd.mean():.6f})")

paths = dist_paths()
cov_any = np.zeros((H, W), bool)
cov_all = {y: np.ones((H, W), bool) for y in OUT_YEARS}
code_any = np.zeros((H, W), bool)
for y in sorted(paths):
    t0 = time.time()
    with rasterio.open(paths[y]) as src:
        nd = src.nodata
        with WarpedVRT(src, crs=crs, transform=T, width=W, height=H,
                       resampling=Resampling.nearest, src_nodata=VRT_FILL,
                       nodata=VRT_FILL) as v:
            arr = v.read(1)
    cov = np.ones((H, W), bool)
    for s_ in SENT: cov &= (arr != s_)
    if nd is not None: cov &= (arr != nd)
    code = cov & (arr > 0)
    cov_any |= cov; code_any |= code
    for oy in OUT_YEARS:
        if y <= oy: cov_all[oy] &= cov
    print(f"  {os.path.basename(paths[y]):28s} nd={nd!s:>8} cov {int(cov.sum()):>12,} "
          f"({cov.mean():.6f}) code {int(code.sum()):>9,} | cov&!nlcd "
          f"{int((cov & ~nlcd).sum()):>9,} nlcd&!cov {int((nlcd & ~cov).sum()):>8,} "
          f"code&!nlcd {int((code & ~nlcd).sum()):>8,}  [{time.time()-t0:.0f}s]")
    del arr, cov, code

def rep(nm, M):
    print(f"\n{nm}: {int(M.sum()):,} ({M.mean():.6f})"
          f"\n    M&~nlcd {int((M & ~nlcd).sum()):,}   nlcd&~M {int((nlcd & ~M).sum()):,}"
          f"\n    M&~tiger {int((M & ~tiger).sum()):,}  tiger&~M {int((tiger & ~M).sum()):,}"
          f"\n    M&~evt {int((M & ~evt).sum()):,}    evt&~M {int((evt & ~M).sum()):,}")
    np.save(os.path.join(SCRATCH, f"{region}_dist2_{nm}.npy"), np.packbits(M.ravel()))
rep("cov_any", cov_any)
for oy in OUT_YEARS: rep(f"cov_all_{oy}", cov_all[oy])
rep("code_any", code_any)
