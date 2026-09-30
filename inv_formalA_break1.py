"""BREAK 1, fully scored: a NH-ONLY negative skew defeats I19, the only
positive/negative spatial-support gate left in CR-0007 v5, while passing every
other GATE row.  The escape is the same one that retired I10: I19 is a POOLED
statistic and NH holds 17 % of the pooled positives."""
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from scipy.stats import ks_2samp

from inv_formalA_harness import R, BS, SEED, blk, val_blocks_fair, hash_split

SCR = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
pos = pd.read_pickle(f"{SCR}/pos.pkl").copy()
cand = pd.read_pickle(f"{SCR}/cand.pkl").copy()
RF = 1920.0
G = 30000.0

vb = val_blocks_fair(pos, SEED)
pos['split'] = np.where(pos['blk'].isin(vb), 'val', 'train')
bt = {b: ('val' if b in vb else 'train') for b in pos['blk'].unique()}
gvf = len(vb) / pos['blk'].nunique()
cand['split'] = [bt.get(b) or hash_split(b, gvf, SEED) for b in cand['blk']]
tg = {(r, s): int(((pos.state == r) & (pos.split == s)).sum())
      for r in R for s in ('train', 'val')}


def draw(skew_regions, seed=0, fr=0.5):
    rng = np.random.default_rng(seed)
    out = []
    for (r, s), n in tg.items():
        pool = cand[(cand.state == r) & (cand.split == s)]
        if r in skew_regions:
            gy = np.floor(pool.y_5070.values / G)
            sub = pool[(pool.y_5070.values - gy * G) < G * fr]
            print(f"      [{r}/{s}] skew pool {len(sub)} vs target {n} "
                  f"({'sufficient' if len(sub) >= n else 'SHORT'})")
            if len(sub) >= n:
                pool = sub
        out.append(pool.iloc[rng.choice(len(pool), size=min(n, len(pool)),
                                        replace=False)].assign(split=s))
    return pd.concat(out, ignore_index=True)


def report(label, neg):
    rec = pd.concat([pos.assign(cls='pos'), neg.assign(cls='neg')], ignore_index=True)
    px = pos[['x_5070', 'y_5070']].values
    print(f"\n########## {label} ##########")
    print(f"  I1  {len(cKDTree(px).query_pairs(30.0, output_type='ndarray'))}   require 0")
    g = rec.groupby('blk')['split'].nunique()
    print(f"  I2  {int((g>1).sum())}   require 0")
    trb = set(rec.loc[rec.split == 'train', 'blk'])
    vn = rec[(rec.split == 'val') & (rec.cls == 'neg')]
    print(f"  I3  {100*vn.blk.isin(trb).mean():.2f}%   require 0%")
    for c in ('pos', 'neg'):
        s = rec[rec.cls == c]
        kt = set(map(tuple, np.round(s.loc[s.split == 'train', ['x_5070', 'y_5070']].values, 3)))
        kv = list(map(tuple, np.round(s.loc[s.split == 'val', ['x_5070', 'y_5070']].values, 3)))
        print(f"  I4  [{c}] {sum(1 for k in kv if k in kt)}   require 0")
    print(f"  I6  {len(pos)}   require 6230 +/- 10")
    ok = all(int(((neg.state == r) & (neg.split == s)).sum()) == tg[(r, s)]
             for r in R for s in ('train', 'val'))
    print(f"  I8  {'PASS (exact)' if ok else 'FAIL'}")
    print(f"  I9  out-of-state pos {int((~pos.state.isin(R)).sum())} / "
          f"neg {int((~neg.state.isin(R)).sum())}   require 0")
    bl = pos.drop_duplicates('blk')
    print(f"  I15 {abs(100*(bl.split=='val').mean()-100*(pos.split=='val').mean()):.3f} pp   require <= 2.5")
    blm = pos.drop_duplicates('blk')[['blk', 'split']].copy()
    XY = np.c_[(blm.blk // 100000 + .5) * BS, (blm.blk % 100000 + .5) * BS]
    y = (blm.split == 'val').values.astype(float)
    z = y - y.mean()
    for k in (4, 8):
        _, idx = cKDTree(XY).query(XY, k=k+1)
        I = (z[idx[:, 1:]].mean(axis=1) * z).sum() / (z**2).sum()
        sd = 0.010507 if k == 4 else 0.007636
        print(f"  I16 k={k}  I={I:+.4f}  z={(I+0.000141)/sd:+.2f}   require z <= 5.0")
    t = pos[pos.split == 'train'][['x_5070', 'y_5070']].values
    v = pos[pos.split == 'val'][['x_5070', 'y_5070']].values
    d, _ = cKDTree(t).query(v, k=1)
    print(f"  I18 {np.median(d)/1000:.3f} km   require in [2.33, 2.75]")
    d, _ = cKDTree(neg[['x_5070', 'y_5070']].values).query(px, k=1)
    print(f"  I19 {(d>RF).mean():.4f}   gate <= 0.55; measured FAIR envelope [0.5209, 0.5607]")
    for r in R:
        m = (pos.state == r).values
        dd, _ = cKDTree(neg[['x_5070', 'y_5070']].values).query(px[m], k=1)
        print(f"      I19 restricted to {r}: {(dd>RF).mean():.4f}   "
              f"median pos->nearest-neg {np.median(dd):.0f} m")
    # the harm: per-region occupied-30km-block support (the retired I10)
    for r in R:
        p = pos[pos.state == r]
        n = neg[neg.state == r]
        pb = set(zip(np.floor(p.x_5070/G).astype(int), np.floor(p.y_5070/G).astype(int)))
        nb = set(zip(np.floor(n.x_5070/G).astype(int), np.floor(n.y_5070/G).astype(int)))
        print(f"      HARM {r} 30 km blocks with positives but no negative: "
              f"{len(pb-nb)}/{len(pb)} = {len(pb-nb)/len(pb):.4f}")


report("A: FAIR", draw(()))
report("B: BREAK 1 - NH-only southern-half negative skew", draw(("NH",)))
