"""R3-JOB2: is a local post-process against the NLCD footprint feasible?
Checks grid identity between nlcd and every product to be corrected."""
import rasterio, numpy as np, glob, os, re
from collections import defaultdict
years=defaultdict(lambda: defaultdict(list))
for p in sorted(glob.glob("data/landfire/*.tif")):
    m=re.match(r'^([A-Z]{2})_(\d{4})_(.+)\.tif$',os.path.basename(p))
    if m: years[m.group(1)][m.group(3)].append(int(m.group(2)))
for r in ("ME","NH","VT"):
    print(f"\n=== {r}")
    for f in ("evt","nlcd","tcc","balive","tpa_live","qmd","carbon_dwn","tsd","road_dist"):
        print(f"  {f:11s} years {sorted(years[r].get(f,[]))}")
print("\n=== grid identity (transform, shape, crs, nodata, dtype) ===")
for r in ("ME","NH","VT"):
    ref=None
    for f in ("nlcd","tcc","balive","tpa_live","qmd","carbon_dwn","tsd","road_dist","evt"):
        ys=sorted(years[r].get(f,[]))
        if not ys: continue
        for y in (ys[0],ys[-1]):
            p=f"data/landfire/{r}_{y}_{f}.tif"
            with rasterio.open(p) as s:
                sig=(tuple(round(v,6) for v in s.transform[:6]),s.width,s.height)
                info=(s.nodata,s.dtypes[0])
            if ref is None: ref=sig; print(f"  {r} REF {f}_{y}: {sig}")
            ok = "SAME GRID" if sig==ref else f"*** DIFFERENT {sig}"
            print(f"    {r}_{y}_{f:11s} nodata={info[0]} dtype={info[1]:8s} {ok}")
