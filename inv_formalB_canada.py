"""Formal review B: check the CR's justification for the WITHDRAWN 'tsd
coverage not derivable' claim -- that 32767 is a fill code and that genuine
out-of-US disturbance codes appear only in Dist23/Dist24."""
import glob, os, re, numpy as np, rasterio
from rasterio.vrt import WarpedVRT
from rasterio.enums import Resampling
from rasterio.windows import Window
SENT=(-9999,-32768,32767,-1111)
def dy(p):
    yy=int(re.search(r"Dist(\d{2})",os.path.basename(p)).group(1));return 1900+yy if yy>=90 else 2000+yy
DP={dy(p):p for p in sorted(glob.glob("data/disturbance/USAnnualDisturbance_1999_present/*/*/Tif/*.tif"))}
with rasterio.open("data/landfire/ME_2025_nlcd.tif") as s:
    H,W,T,CRS=s.height,s.width,s.transform,s.crs; nl=s.read(1)
us = nl!=-9999; del nl
print(f"ME grid {H*W:,}; outside-US(NLCD) {int((~us).sum()):,}")
print(f"{'vintage':10s} {'32767':>12s} {'-9999':>12s} {'-1111':>12s} {'-32768':>12s} {'real>0 out-US':>14s} {'decl_nd':>8s}")
for d,p in sorted(DP.items()):
    with rasterio.open(p) as s:
        nd=s.nodata
        with WarpedVRT(s,crs=CRS,transform=T,width=W,height=H,resampling=Resampling.nearest) as v:
            c={k:0 for k in SENT}; real=0
            for r0 in range(0,H,2048):
                n=min(2048,H-r0); a=v.read(1,window=Window(0,r0,W,n))
                for k in SENT: c[k]+=int((a==k).sum())
                real+=int(((a>0)&~np.isin(a,SENT)&(~us[r0:r0+n])).sum())
    print(f"Dist{d%100:02d}      {c[32767]:>12,} {c[-9999]:>12,} {c[-1111]:>12,} {c[-32768]:>12,} {real:>14,} {nd:>8}")
