"""Reviewer C: what do the §9 raster fixes actually affect, inside vs outside coverage?"""
import numpy as np, rasterio
from grouse_data import GrouseData
STEP=8
for region in ("ME","NH","VT"):
    rd=GrouseData()[region]
    feats=rd.available_features()
    with rasterio.open(rd.latest_raster_path("evt")) as s:
        evt=s.read(1)[::STEP,::STEP]; nd=s.nodata
    out = evt==nd
    ins = ~out
    print(f"\n=== {region}: evt nodata {out.mean():.1%} of grid, sampled {evt.size:,} px")
    for f in ["tsd","balive","tpa_live","qmd","carbon_dwn","tcc","nlcd","road_dist"]:
        if f not in feats: 
            print(f"  {f:11s} NOT AVAILABLE"); continue
        p=rd.latest_raster_path(f)
        with rasterio.open(p) as s:
            a=s.read(1)[::STEP,::STEP].astype(np.float64); fnd=s.nodata
        zi=(a[ins]==0).mean(); zo=(a[out]==0).mean() if out.any() else float('nan')
        ndi=(a[ins]==fnd).mean() if fnd is not None else 0
        ndo=(a[out]==fnd).mean() if fnd is not None else 0
        print(f"  {f:11s} nodata={fnd} | INSIDE evt-cov: zero={zi:.3%} nodataf={ndi:.3%} "
              f"| OUTSIDE: zero={zo:.3%} nodataf={ndo:.3%}")
