"""The stratified draw's val-fraction overshoot, and the fix.  READ-ONLY."""
import os, sys
import numpy as np, pandas as pd
os.chdir("/home/ec2-user/grouse2")
SP = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
base = pd.read_csv(SP + "/base.csv")
R = ["ME", "NH", "VT"]; VF = 0.2
blocks = pd.Index(sorted(base.blk.unique())); NB = len(blocks)
bi = pd.Series(np.arange(NB), index=blocks); base['bidx'] = bi[base.blk.values].values
bcount = np.bincount(base.bidx, minlength=NB)
bxy = np.array([[int(b.split('_')[0]), int(b.split('_')[1])] for b in blocks])
breg = base.groupby('bidx')['state'].agg(lambda s: s.value_counts().idxmax()).reindex(range(NB)).values
TOT = len(base)
cell = lambda n: (bxy[:, 0] // n) * 100000 + (bxy[:, 1] // n)

def draw(seed, strata, rule, vf=VF):
    rng = np.random.default_rng(seed); vb = set()
    st = pd.factorize(np.asarray(strata))[0]
    for s in np.unique(st):
        idx = np.where(st == s)[0]
        t = vf * bcount[idx].sum(); run = 0
        for b in rng.permutation(idx):
            if rule == 'greedy_overshoot':
                if run >= t: break
                vb.add(int(b)); run += bcount[b]
            else:   # 'nearest': take the block only if it gets us closer to t
                if abs(run + bcount[b] - t) < abs(run - t):
                    vb.add(int(b)); run += bcount[b]
                elif run >= t:
                    break
    return vb
def frac(vb):
    v = np.zeros(NB, bool); v[list(vb)] = True
    isval = v[base.bidx.values]
    per = [100 * isval[(base.state == r).values].mean() for r in R]
    return 100 * isval.mean(), max(abs(p - 20) for p in per)

for nm, strata in [('region', breg), ('30km x region', [f"{a}_{b}" for a, b in zip(cell(10), breg)]),
                   ('12km x region', [f"{a}_{b}" for a, b in zip(cell(4), breg)])]:
    for rule in ['greedy_overshoot', 'nearest']:
        f = np.array([frac(draw(s, strata, rule)) for s in range(1, 41)])
        print(f"{nm:15s} {rule:16s} val_frac mean {f[:,0].mean():6.3f}%  max {f[:,0].max():6.3f}%"
              f"   per-region worst dev mean {f[:,1].mean():.3f} pp max {f[:,1].max():.3f} pp"
              f"   n_strata {len(set(map(str,strata)))}")
