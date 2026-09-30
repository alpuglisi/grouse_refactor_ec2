"""Verify CR v2's 'Why now' nodata table for ALL 15 FEATURE_SPEC channels."""
import rasterio, numpy as np, glob, os
from models import FEATURE_SPEC
feats=sorted(FEATURE_SPEC)
for reg in ("ME","NH"):
    with rasterio.open(f"data/landfire/{reg}_2024_evt.tif") as s:
        e=s.read(1,out_shape=(s.height//8,s.width//8)); nd=s.nodata; shp=e.shape
    out=(e==nd)
    print(f"\n=== {reg}: evt-nodata fraction {out.mean():.3f} (8x downsample) ===")
    for f in feats:
        c=[p for p in sorted(glob.glob(f"data/landfire/{reg}_*_{f}.tif")) if "_2024_" in p] or sorted(glob.glob(f"data/landfire/{reg}_*_{f}.tif"))[-1:]
        if not c: print(f"  {f:11s} NO RASTER"); continue
        with rasterio.open(c[0]) as s2:
            a=s2.read(1,out_shape=shp); n2=s2.nodata
        v=a[out]
        fr=float(np.mean(v==n2)) if n2 is not None else 0.0
        vals,cnts=np.unique(v,return_counts=True)
        mode=vals[np.argmax(cnts)]
        verdict="correct" if fr>0.95 else "FABRICATED"
        print(f"  {f:11s} nodata_frac={fr:.3f}  mode={mode}  -> {verdict}   [{os.path.basename(c[0])}]")
