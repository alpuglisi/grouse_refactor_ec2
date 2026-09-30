"""RES-COMP: can a train.py-level assertion afford the continuous-feature
point sample the S* gates need?  READ-ONLY."""
import time, numpy as np, pandas as pd, rasterio
from pyproj import Transformer
CONT = ["ch","cc","tcc","road_dist","tsd","balive","tpa_live","qmd","carbon_dwn"]
R = ["ME","NH","VT"]
neg = pd.concat([pd.read_csv(f"data/negatives/negatives_{r}.csv", low_memory=False)
                 for r in R], ignore_index=True)
print("negatives on disk:", len(neg), neg.groupby('state').size().to_dict())
print("cols present for composition gates WITHOUT any raster read:",
      [c for c in ('is_nonveg','weight','weight_basis','envelope_id','evt_phys',
                   'split','block_id','common_name','state','year') if c in neg.columns])
print("continuous FEATURE_SPEC cols present in the CSV:",
      [c for c in CONT if c in neg.columns], "<- none")
t0 = time.time(); nread = 0
for r in R:
    sub = neg[neg.state == r]
    with rasterio.open(f"data/landfire/{r}_2022_road_dist.tif") as s:
        T = Transformer.from_crs("EPSG:4326", s.crs, always_xy=True)
    xs, ys = T.transform(sub.longitude.values, sub.latitude.values)
    pts = list(zip(xs, ys))
    for f in CONT:
        with rasterio.open(f"data/landfire/{r}_2022_{f}.tif") as s:
            v = np.array([x[0] for x in s.sample(pts)], dtype=float)
        nread += len(v)
print(f"point-sampled {nread} values ({len(neg)} records x {len(CONT)} features, "
      f"2022 vintage only) in {time.time()-t0:.1f}s")
