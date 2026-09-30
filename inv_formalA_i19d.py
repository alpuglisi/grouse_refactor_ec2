"""I19 under the v5 BUG-0034 decision, using a WEIGHTED-pattern negative draw
(subsampled from the real weighted selection) so the envelope-weighting and
NonVeg cap are represented rather than approximated away."""
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from inv_formalA_harness import R, SEED, blk
from inv_formalA_thin import fast_thin

RF = 1920.0
neg = pd.concat([pd.read_csv(f"data/negatives/negatives_{r}.csv") for r in R],
                ignore_index=True)
own = pd.concat([pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv").assign(_reg=r)
                 for r in R], ignore_index=True)
own = own[(own.state == own._reg) & (~own['nonveg_landcover'].astype(bool))]
own = own.drop_duplicates(subset=['longitude', 'latitude', 'year']).reset_index(drop=True)

pos_all = fast_thin(own, 30, SEED)
pos_20 = fast_thin(own[own.year >= 2020].reset_index(drop=True), 30, SEED)
print(f"positives: all-years {len(pos_all)}   2020+ {len(pos_20)}")

rng = np.random.default_rng(0)


def env(ref_xy, n, draws=80):
    v = []
    for _ in range(draws):
        s = neg.iloc[rng.choice(len(neg), n, replace=False)]
        d, _ = cKDTree(s[['x_5070', 'y_5070']].values).query(ref_xy, k=1)
        v.append(float((d > RF).mean()))
    return np.array(v)


print("\nI19 fair envelope, weighted-pattern negative draw at NEG_RATIO=1.0:")
for tag, p in (("CR-0007 v4 footing  (all years)", pos_all),
               ("CR-0007 v5 footing  (2020+ only, the DECIDED fix)", pos_20)):
    xy = p[['x_5070', 'y_5070']].values
    v = env(xy, len(p))
    print(f"  {tag:50} n_pos=n_neg={len(p):5}  "
          f"p50 {np.median(v):.4f}  p99 {np.percentile(v,99):.4f}  max {v.max():.4f}"
          f"   gate<=0.55 false-fail {100*(v>0.55).mean():5.1f}%")

print("\nmonotone count sensitivity of I19 (same weighted pattern, all-years positives):")
xy = pos_all[['x_5070', 'y_5070']].values
for n in (8365, 7000, 6230, 5500, 4809, 4000):
    v = env(xy, n, draws=40)
    print(f"   n_neg={n:5}  p50 {np.median(v):.4f}")
