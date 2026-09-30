"""What disturbance CODES do the LF2020+ vintages report OUTSIDE the NLCD
footprint on the ME grid?  Real mapped disturbance, or a systematic code?"""
import os, glob, numpy as np, rasterio, csv
from rasterio.vrt import WarpedVRT
from rasterio.enums import Resampling
SCRATCH = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
DIST = "data/disturbance/USAnnualDisturbance_1999_present"
region = "ME"
tpl = sorted(glob.glob(f"data/landfire/{region}_*_evt.tif"))[-1]
with rasterio.open(tpl) as s: H, W, crs, T = s.height, s.width, s.crs, s.transform
a = np.load(os.path.join(SCRATCH, f"{region}_nlcd.npy"))
nlcd = np.unpackbits(a)[:H*W].astype(bool).reshape(H, W)
for tag in ("LF2020_Dist17", "LF2023_Dist23", "LF2014_Dist13"):
    p = glob.glob(f"{DIST}/{tag}_CONUS/{tag}_CONUS/Tif/{tag}_CONUS.tif")[0]
    with rasterio.open(p) as src, WarpedVRT(src, crs=crs, transform=T, width=W,
            height=H, resampling=Resampling.nearest, src_nodata=-32768,
            nodata=-32768) as v:
        arr = v.read(1)
    lut = {}
    cp = glob.glob(f"{DIST}/{tag}_CONUS/{tag}_CONUS/CSV_Data/*.csv")[0]
    with open(cp, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            lut[int(row["VALUE"])] = (row.get("DIST_TYPE", "?"),
                                      row.get("SEVERITY", "?"))
    for lbl, sel in (("OUTSIDE nlcd", ~nlcd), ("INSIDE nlcd", nlcd)):
        sub = arr[sel]
        vals, cnt = np.unique(sub, return_counts=True)
        o = np.argsort(-cnt)[:8]
        print(f"{tag} {lbl} ({sel.sum():,} px):")
        for i in o:
            vv = int(vals[i]); d = lut.get(vv, ("<not in table>", ""))
            print(f"    {vv:>8} x {cnt[i]:>12,}  {d[0]}/{d[1]}")
    del arr
