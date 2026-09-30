"""Over pixels OUTSIDE LANDFIRE coverage (evt == nodata), what do the other
channels read?  Settles BUG-0024/BUG-0025's 'unconfirmed on real data'."""
import rasterio, numpy as np, glob, os
for reg in ("NH","VT","ME"):
    ev=f"data/landfire/{reg}_2024_evt.tif"
    with rasterio.open(ev) as s:
        e=s.read(1, out_shape=(s.height//8, s.width//8)); nd=s.nodata
    out=(e==nd)
    print(f"\n{reg}: evt-nodata fraction (8x downsample) {out.mean():.3f}")
    if out.sum()==0: continue
    for feat in ("tsd","road_dist","balive","tpa_live","qmd","carbon_dwn","tcc","nlcd"):
        cands=sorted(glob.glob(f"data/landfire/{reg}_*_{feat}.tif"))
        if not cands:
            print(f"   {feat}: no raster"); continue
        p=[c for c in cands if "2024" in c] or cands[-1:]
        with rasterio.open(p[0]) as s2:
            if (s2.height,s2.width)!=(  [x for x in [0]][0] or s2.height, s2.width): pass
            a=s2.read(1, out_shape=e.shape); n2=s2.nodata
        v=a[out]
        frac_nd = float(np.mean(v==n2)) if n2 is not None else 0.0
        print(f"   {feat:11s} nodata={str(n2):8s} outside-LANDFIRE: nodata_frac={frac_nd:.3f} "
              f"median={np.median(v.astype(float)):.1f} unique(first5)={np.unique(v)[:5]}")
