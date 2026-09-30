"""I19: false-fail rate at 0.55 on the CR's own post-partition footing, and a
differential test of which footing reproduces the CR's quoted 0.5223/0.5258."""
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from inv_formalA_harness import R, VF, SEED, blk, val_blocks_fair, hash_split
from inv_formalA_thin import fast_thin

SCR = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
pos = pd.read_pickle(f"{SCR}/pos.pkl")
cand = pd.read_pickle(f"{SCR}/cand.pkl")
RF = 1920.0

vb = val_blocks_fair(pos, SEED)
pos = pos.copy()
pos['split'] = np.where(pos['blk'].isin(vb), 'val', 'train')
blocktab = {b: ('val' if b in vb else 'train') for b in pos['blk'].unique()}
gvf = len(vb) / pos['blk'].nunique()
cand = cand.copy()
cand['split'] = [blocktab.get(b) or hash_split(b, gvf, SEED) for b in cand['blk']]
POSXY = pos[['x_5070', 'y_5070']].values


def frac(sel_xy):
    d, _ = cKDTree(sel_xy).query(POSXY, k=1)
    return float((d > RF).mean())


def draw_scaled(seed, ratio):
    out = []
    rng = np.random.default_rng(seed)
    for r in R:
        for s in ('train', 'val'):
            n = int(round(((pos.state == r) & (pos.split == s)).sum() * ratio))
            pool = cand[(cand.state == r) & (cand.split == s)]
            n = min(n, len(pool))
            out.append(pool.iloc[rng.choice(len(pool), size=n, replace=False)])
    return pd.concat(out, ignore_index=True)


print("=== I19 fair envelope at NEG_RATIO = 1.0 (what CR-0007 builds), 300 seeds ===")
v = np.array([frac(draw_scaled(s, 1.0)[['x_5070', 'y_5070']].values) for s in range(300)])
print(f"  n_neg = {len(draw_scaled(0,1.0))}")
print(f"  min {v.min():.4f} p50 {np.median(v):.4f} p95 {np.percentile(v,95):.4f} "
      f"p99 {np.percentile(v,99):.4f} max {v.max():.4f}")
print(f"  FALSE-FAIL RATE of the proposed gate (<=0.55): {100*(v>0.55).mean():.1f}%  "
      f"({int((v>0.55).sum())}/300)")

print("\n=== differential: which footing reproduces the CR's 'fair p99 0.5223 / max 0.5258'? ===")
for ratio, label in [(1.0, "1:1 (6,230 negatives) - post-partition, what the CR builds"),
                     (8365/6230, "8,365 negatives - TODAY's pre-partition negative count"),
                     (1.5, "1.5:1"),
                     (2.0, "2:1")]:
    vv = np.array([frac(draw_scaled(s, ratio)[['x_5070', 'y_5070']].values) for s in range(60)])
    print(f"  {label:58} n={len(draw_scaled(0,ratio)):6}  "
          f"p99 {np.percentile(vv,99):.4f} max {vv.max():.4f}")

print("\n=== and against TODAY's ACTUAL (weighted, pre-CR) selected negatives ===")
neg = pd.concat([pd.read_csv(f"data/negatives/negatives_{r}.csv") for r in R],
                ignore_index=True)
print(f"  today's selected negatives n={len(neg)}  ->  I19 vs post-partition positives = "
      f"{frac(neg[['x_5070','y_5070']].values):.4f}")
tp = pd.concat([pd.read_csv(f"data/pipeline/thinned_positives_{r}.csv") for r in R],
               ignore_index=True)
d, _ = cKDTree(neg[['x_5070', 'y_5070']].values).query(tp[['x_5070', 'y_5070']].values, k=1)
print(f"  today's selected negatives vs TODAY's thinned positives (n={len(tp)}) = "
      f"{(d>RF).mean():.4f}   median {np.median(d):.0f} m")

print("\n=== post-BUG-0034 (positives restricted to 2020+) footing ===")
own = pd.concat([pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv").assign(_reg=r)
                 for r in R], ignore_index=True)
own = own[(own.state == own._reg) & (~own['nonveg_landcover'].astype(bool))]
own = own.drop_duplicates(subset=['longitude', 'latitude', 'year'])
p20 = fast_thin(own[own.year >= 2020].reset_index(drop=True), 30, SEED)
p20['blk'] = blk(p20.x_5070.values, p20.y_5070.values)
vb20 = val_blocks_fair(p20, SEED)
p20['split'] = np.where(p20['blk'].isin(vb20), 'val', 'train')
bt20 = {b: ('val' if b in vb20 else 'train') for b in p20['blk'].unique()}
gvf20 = len(vb20) / p20['blk'].nunique()
c20 = cand.copy()
c20['split'] = [bt20.get(b) or hash_split(b, gvf20, SEED) for b in c20['blk']]
P20 = p20[['x_5070', 'y_5070']].values


def frac20(xy):
    d, _ = cKDTree(xy).query(P20, k=1)
    return float((d > RF).mean())


def draw20(seed):
    out = []
    rng = np.random.default_rng(seed)
    for r in R:
        for s in ('train', 'val'):
            n = int(((p20.state == r) & (p20.split == s)).sum())
            pool = c20[(c20.state == r) & (c20.split == s)]
            n = min(n, len(pool))
            out.append(pool.iloc[rng.choice(len(pool), size=n, replace=False)])
    return pd.concat(out, ignore_index=True)


v20 = np.array([frac20(draw20(s)[['x_5070', 'y_5070']].values) for s in range(150)])
print(f"  positives n={len(p20)}  negatives n={len(draw20(0))}")
print(f"  min {v20.min():.4f} p50 {np.median(v20):.4f} p99 {np.percentile(v20,99):.4f} "
      f"max {v20.max():.4f}   false-fail at 0.55: {100*(v20>0.55).mean():.1f}%")
