"""Is there ANY separating I19 threshold on the v5 (BUG-0034-fixed) footing?
Fair envelope vs the southern-fraction negative-skew attacks, both drawn the
same way (uniform within the correct split) so the comparison is internal."""
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from inv_formalA_harness import R, BS, SEED, blk, val_blocks_fair, hash_split
from inv_formalA_thin import fast_thin

SCR = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
cand = pd.read_pickle(f"{SCR}/cand.pkl").copy()
RF = 1920.0

own = pd.concat([pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv").assign(_reg=r)
                 for r in R], ignore_index=True)
own = own[(own.state == own._reg) & (~own['nonveg_landcover'].astype(bool))]
own = own.drop_duplicates(subset=['longitude', 'latitude', 'year']).reset_index(drop=True)


def footing(year_min):
    p = fast_thin(own[own.year >= year_min].reset_index(drop=True), 30, SEED) if year_min \
        else fast_thin(own, 30, SEED)
    p = p.copy()
    p['blk'] = blk(p.x_5070.values, p.y_5070.values)
    vb = val_blocks_fair(p, SEED)
    p['split'] = np.where(p['blk'].isin(vb), 'val', 'train')
    bt = {b: ('val' if b in vb else 'train') for b in p['blk'].unique()}
    gvf = len(vb) / p['blk'].nunique()
    c = cand.copy()
    c['split'] = [bt.get(b) or hash_split(b, gvf, SEED) for b in c['blk']]
    tg = {(r, s): int(((p.state == r) & (p.split == s)).sum())
          for r in R for s in ('train', 'val')}
    return p, c, tg


def run(p, c, tg, mode, seed, regs=(), fr=0.5, gs=30000.0):
    rng = np.random.default_rng(seed)
    out = []
    for (r, s), n in tg.items():
        pool = c[(c.state == r) & (c.split == s)]
        if mode == 'skew' and r in regs:
            gy = np.floor(pool.y_5070.values / gs)
            sub = pool[(pool.y_5070.values - gy * gs) < gs * fr]
            if len(sub) >= n:
                pool = sub
        out.append(pool.iloc[rng.choice(len(pool), size=min(n, len(pool)), replace=False)])
    sel = pd.concat(out, ignore_index=True)
    d, _ = cKDTree(sel[['x_5070', 'y_5070']].values).query(
        p[['x_5070', 'y_5070']].values, k=1)
    return float((d > RF).mean())


for ymin, lbl in ((None, "v4 footing: all-years positives (6,230)"),
                  (2020, "v5 footing: 2020+ positives (4,809)  <- the DECIDED fix")):
    p, c, tg = footing(ymin)
    fair = np.array([run(p, c, tg, 'fair', s) for s in range(150)])
    print(f"\n### {lbl}   n_pos = {len(p)}")
    print(f"  FAIR  min {fair.min():.4f}  p50 {np.median(fair):.4f}  "
          f"p99 {np.percentile(fair,99):.4f}  max {fair.max():.4f}")
    worst_attack = 1.0
    for regs, fr in ((("NH",), 0.5), (("VT",), 0.5), (("NH", "VT"), 0.5),
                     (("NH", "VT"), 0.333), (("ME", "NH", "VT"), 0.5)):
        a = np.array([run(p, c, tg, 'skew', s, regs, fr) for s in range(6)])
        worst_attack = min(worst_attack, a.min())
        print(f"  ATTACK {'+'.join(regs):14} south {fr:.3f}: min {a.min():.4f} max {a.max():.4f}")
    gap = worst_attack - fair.max()
    print(f"  => separation: fair max {fair.max():.4f} vs weakest attack "
          f"{worst_attack:.4f}   gap {gap:+.4f} ({100*gap/fair.max():+.1f}% of fair max)")
    print(f"     a gate at 1.02x fair max = {1.02*fair.max():.4f} -> "
          f"{'SEPARATES' if 1.02*fair.max() < worst_attack else 'DOES NOT SEPARATE'}")
