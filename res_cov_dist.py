"""LANDFIRE Annual Disturbance footprint, derived locally, on each region grid.

The shipped CSV_Data attribute table for EVERY vintage declares VALUE=-9999 as
"Fill-NoData" and VALUE=0 as "Background"; 32767/-32768 (the GeoTIFF nodata tag)
appear in NO table.  So "covered" = in the source's own extent AND value != -9999.
Reprojected exactly as generate_time_since_disturbance.py does (WarpedVRT,
nearest) so the mask is index-for-index with the tsd rasters.
"""
import os, sys, glob, re, time
import numpy as np, rasterio
from rasterio.vrt import WarpedVRT
from rasterio.enums import Resampling

SCRATCH = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
DIST = "data/disturbance/USAnnualDisturbance_1999_present"
FILL = -9999
OUT_SENT = -32768            # WarpedVRT fill for out-of-source-extent

def dist_paths():
    found = {}
    for p in glob.glob(os.path.join(DIST, "**", "*.tif"), recursive=True):
        m = re.search(r"Dist(\d{2})", os.path.basename(p))
        if not m: continue
        yy = int(m.group(1)); y = 1900+yy if yy >= 90 else 2000+yy
        if y not in found or p > found[y]:
            found[y] = p
    return found

def load_packed(region, name, shape):
    a = np.load(os.path.join(SCRATCH, f"{region}_{name}.npy"))
    return np.unpackbits(a)[:shape[0]*shape[1]].astype(bool).reshape(shape)

region = sys.argv[1]
tpl = sorted(glob.glob(f"data/landfire/{region}_*_evt.tif"))[-1]
with rasterio.open(tpl) as s:
    H, W, crs, T = s.height, s.width, s.crs, s.transform
nlcd = load_packed(region, "nlcd", (H, W))
evt = load_packed(region, "evt", (H, W))
tiger = load_packed(region, "tiger_at1", (H, W))
tot = H*W
print(f"{region} grid {W}x{H} = {tot:,}; nlcd valid {nlcd.sum():,}")

paths = dist_paths()
cov_any = np.zeros((H, W), bool)
cov_all = np.ones((H, W), bool)
code_any = np.zeros((H, W), bool)
rows = []
for y in sorted(paths):
    t0 = time.time()
    with rasterio.open(paths[y]) as src:
        with WarpedVRT(src, crs=crs, transform=T, width=W, height=H,
                       resampling=Resampling.nearest, src_nodata=OUT_SENT,
                       nodata=OUT_SENT) as v:
            arr = v.read(1)
    inext = arr != OUT_SENT
    cov = inext & (arr != FILL)
    code = cov & (arr > 0)
    cov_any |= cov
    cov_all &= cov
    code_any |= code
    r = dict(year=y, name=os.path.basename(paths[y]),
             out_of_extent=int((~inext).sum()), fill=int((inext & (arr == FILL)).sum()),
             cov=int(cov.sum()), code=int(code.sum()),
             cov_outside_nlcd=int((cov & ~nlcd).sum()),
             code_outside_nlcd=int((code & ~nlcd).sum()),
             nlcd_not_cov=int((nlcd & ~cov).sum()),
             t=time.time()-t0)
    rows.append(r)
    print(f"  {r['name']:28s} oo_extent {r['out_of_extent']:>12,} fill {r['fill']:>12,} "
          f"cov {r['cov']:>12,} ({r['cov']/tot:.6f}) code {r['code']:>10,} | "
          f"cov&!nlcd {r['cov_outside_nlcd']:>10,} code&!nlcd {r['code_outside_nlcd']:>9,} "
          f"nlcd&!cov {r['nlcd_not_cov']:>9,}  [{r['t']:.0f}s]")
    del arr, inext, cov, code

for nm, M in (("cov_any", cov_any), ("cov_all", cov_all), ("code_any", code_any)):
    print(f"\n{nm}: {M.sum():,} ({M.sum()/tot:.6f})  "
          f"& ~nlcd {int((M & ~nlcd).sum()):,}  nlcd & ~M {int((nlcd & ~M).sum()):,}  "
          f"& ~evt {int((M & ~evt).sum()):,}  evt & ~M {int((evt & ~M).sum()):,}  "
          f"& ~tiger {int((M & ~tiger).sum()):,}  tiger & ~M {int((tiger & ~M).sum()):,}")
    np.save(os.path.join(SCRATCH, f"{region}_dist_{nm}.npy"), np.packbits(M.ravel()))
