"""I19 fair envelope + region-targeted-skew attacks, on the CR-0007
post-partition footing. READ-ONLY."""
import hashlib
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from inv_formalA_harness import R, BS, VF, SEED, blk, val_blocks_fair, hash_split

SCR = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
pos = pd.read_pickle(f"{SCR}/pos.pkl")
cand = pd.read_pickle(f"{SCR}/cand.pkl")
RF = 1920.0

vb = val_blocks_fair(pos, SEED)
pos = pos.copy()
pos['split'] = np.where(pos['blk'].isin(vb), 'val', 'train')
blocktab = {}
for b in pos['blk'].unique():
    blocktab[b] = 'val' if b in vb else 'train'
gvf = len(vb) / pos['blk'].nunique()
cand = cand.copy()
cand['split'] = [blocktab.get(b) or hash_split(b, gvf, SEED) for b in cand['blk']]

targets = {}
for r in R:
    for s in ('train', 'val'):
        targets[(r, s)] = int(round(((pos.state == r) & (pos.split == s)).sum()))
print("positive counts per (region,split):", targets)
print("candidate supply  per (region,split):",
      {k: int(((cand.state == k[0]) & (cand.split == k[1])).sum()) for k in targets})

POSXY = pos[['x_5070', 'y_5070']].values


def i19(sel):
    d, _ = cKDTree(sel[['x_5070', 'y_5070']].values).query(POSXY, k=1)
    return float((d > RF).mean()), float(np.median(d))


def i19_region(sel, r):
    m = (pos.state == r).values
    d, _ = cKDTree(sel[['x_5070', 'y_5070']].values).query(POSXY[m], k=1)
    return float((d > RF).mean())


def draw(mode, seed, skew_regions=(), frac=0.5, gridsize=30000.0):
    out = []
    rng = np.random.default_rng(seed)
    for (r, s), n in targets.items():
        pool = cand[(cand.state == r) & (cand.split == s)]
        if mode == 'skew' and r in skew_regions:
            gy = np.floor(pool.y_5070.values / gridsize)
            off = pool.y_5070.values - gy * gridsize
            sub = pool[off < gridsize * frac]
            if len(sub) >= n:
                pool = sub
        take = min(n, len(pool))
        out.append(pool.iloc[rng.choice(len(pool), size=take, replace=False)])
    return pd.concat(out, ignore_index=True)


print("\n=== I19 fair envelope (uniform draw within the correct split), 200 seeds ===")
vals = []
for s in range(200):
    f, _ = i19(draw('fair', s))
    vals.append(f)
vals = np.array(vals)
print(f"  min {vals.min():.4f}  p50 {np.median(vals):.4f}  p99 {np.percentile(vals,99):.4f}  max {vals.max():.4f}")
print(f"  CR claims: fair p99 0.5223, max 0.5258   gate <= 0.55")

print("\n=== attacks: southern-fraction skew of each 30 km block, applied to a SUBSET of regions ===")
print(f"{'regions skewed':22} {'frac':>6} {'I19 pooled':>11} {'gate<=.55':>10}   per-region I19 (ME/NH/VT)")
base = draw('fair', 0)
bp, bmed = i19(base)
print(f"{'(none, fair seed 0)':22} {'-':>6} {bp:11.4f} {'PASS':>10}   " +
      "  ".join(f"{i19_region(base,r):.4f}" for r in R))
for regs in [("NH",), ("VT",), ("NH", "VT"), ("ME", "NH", "VT")]:
    for fr in (0.5, 0.333, 0.25):
        for gs in (30000.0, 12000.0):
            sel = draw('skew', 0, regs, fr, gs)
            p, med = i19(sel)
            tag = "PASS" if p <= 0.55 else "FAIL"
            print(f"{'+'.join(regs):14} g={gs/1000:4.0f}km {fr:6.3f} {p:11.4f} {tag:>10}   " +
                  "  ".join(f"{i19_region(sel,r):.4f}" for r in R))
