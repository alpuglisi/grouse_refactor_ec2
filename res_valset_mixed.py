"""The 4 mixed-state 3 km blocks, and what a RECORD-level per-region
stratified draw does to them (BUG-0027's signature).  READ-ONLY."""
import os, sys
import numpy as np, pandas as pd
from scipy.spatial import cKDTree
os.chdir("/home/ec2-user/grouse2")
SP = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
base = pd.read_csv(SP + "/base.csv")
mix = base.groupby('blk')['state'].nunique()
mb = mix[mix > 1].index
print("mixed-state blocks:", list(mb))
for b in mb:
    s = base[base.blk == b]
    xy = s[['x_5070', 'y_5070']].values
    d = np.hypot(*(xy[:, None, :] - xy[None, :, :]).transpose(2, 0, 1))
    cross = [d[i, j] for i in range(len(s)) for j in range(len(s))
             if s.state.values[i] != s.state.values[j]]
    print(f"  {b}: n={len(s)} states={dict(s.state.value_counts())} "
          f"min cross-state distance = {min(cross):.0f} m, max {max(cross):.0f} m")
# record-level per-region stratified draw: how often does a block end up
# holding both splits, and how close are the two records?
R = ["ME", "NH", "VT"]
viol = []
for seed in range(1, 201):
    rng = np.random.default_rng(seed)
    isval = np.zeros(len(base), bool)
    for r in R:
        m = (base.state == r).values
        sub = base.blk.values[m]; cnt = pd.Series(sub).value_counts()
        t = int(round(.2 * m.sum())); run = 0; ch = set()
        for b in rng.permutation(cnt.index.values):
            if run >= t: break
            ch.add(b); run += cnt[b]
        isval[m] = np.isin(sub, list(ch))
    g = pd.DataFrame({'b': base.blk.values, 'v': isval}).groupby('b')['v'].agg(['min', 'max'])
    bad = g.index[g['min'] != g['max']]
    nd = []
    for b in bad:
        s = base[base.blk.values == b]; vv = isval[base.blk.values == b]
        a = s[['x_5070', 'y_5070']].values
        nd.append(cKDTree(a[~vv]).query(a[vv], k=1)[0].min())
    viol.append((len(bad), min(nd) if nd else np.nan))
V = pd.DataFrame(viol, columns=['blocks_both_splits', 'min_cross_split_m'])
print("\nRECORD-level per-region stratified draw, 200 seeds:")
print("  seeds with >=1 block holding both splits:",
      int((V.blocks_both_splits > 0).sum()), "/ 200")
print("  blocks_both_splits: mean %.2f  max %d" % (V.blocks_both_splits.mean(), V.blocks_both_splits.max()))
print("  min cross-split distance inside such a block: min %.0f m  median %.0f m"
      % (V.min_cross_split_m.min(), V.min_cross_split_m.median()))
print("\n  (CR-0007 assertion (c) / I2 requires blocks_both_splits == 0)")
