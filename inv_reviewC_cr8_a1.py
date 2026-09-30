"""CR-0008 § Acceptance A1/A2/A3: recompute against the NLCD footprint, and put
A1's 0.99 threshold into the SAME UNITS as the 0.05%-of-grid budget."""
import rasterio, numpy as np, glob, os, re
from collections import defaultdict
STEP=8
yrs=defaultdict(lambda: defaultdict(list))
for p in glob.glob("data/landfire/*.tif"):
    m=re.match(r'^([A-Z]{2})_(\d{4})_(.+)\.tif$',os.path.basename(p))
    if m: yrs[m.group(1)][m.group(3)].append(int(m.group(2)))
FEATS=["tsd","balive","tpa_live","qmd","carbon_dwn","tcc","road_dist","nlcd","evt"]
for r in ("ME","NH","VT"):
    with rasterio.open(f"data/landfire/{r}_2016_nlcd.tif") as s:
        full=(s.width,s.height); nl=s.read(1)[::STEP,::STEP]
    inside=nl!=-9999; out=~inside
    npx_full=full[0]*full[1]
    print(f"\n=== {r}  grid {full[0]}x{full[1]} = {npx_full:,} px | outside-US {out.mean():.4f} "
          f"({out.sum():,} of {out.size:,} sampled)")
    print(f"    budget 0.05% of grid = {0.0005*npx_full:,.0f} real px"
          f"  |  A1 slack (1% of outside-coverage) = {0.01*out.mean()*npx_full:,.0f} real px"
          f"  -> A1 is {0.01*out.mean()/0.0005:.1f}x looser than the budget")
    for f in FEATS:
        ys=sorted(yrs[r].get(f,[]))
        if not ys: print(f"    {f:11s} ABSENT"); continue
        y=max(ys)
        with rasterio.open(f"data/landfire/{r}_{y}_{f}.tif") as s: a=s.read(1)[::STEP,::STEP]
        ndo=(a[out]==-9999).mean()
        zi=int((a[inside]==0).sum()); ndi=int((a[inside]==-9999).sum())
        print(f"    {f:11s} y={y} A1(out nodata frac)={ndo:.4f} | in-cov zeros={zi:,} "
              f"in-cov nodata={ndi:,} | fabricated-out px(sampled)={int((a[out]!=-9999).sum()):,}")
