"""(a) reproduce the reviewer's pooled-longitude numbers; (b) calibrate the
CR's proposed HARD gate I7 (+/-2 pp per region) against the fair draw it is
supposed to accept.  READ-ONLY."""
import os, numpy as np, pandas as pd
from scipy.stats import ks_2samp
os.chdir("/home/ec2-user/grouse2")
SP = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
base = pd.read_csv(SP + "/base.csv"); R = ["ME", "NH", "VT"]; VF = .2
blocks = pd.Index(sorted(base.blk.unique())); NB = len(blocks)
bi = pd.Series(np.arange(NB), index=blocks); base['bidx'] = bi[base.blk.values].values
bcount = np.bincount(base.bidx, minlength=NB)
bxy = np.array([[int(b.split('_')[0]), int(b.split('_')[1])] for b in blocks])
breg = base.groupby('bidx')['state'].agg(lambda s: s.value_counts().idxmax()).reindex(range(NB)).values
TOT = len(base); NREG = {r: int((base.state == r).sum()) for r in R}
def fair(seed):
    bc = pd.Series(bcount, index=range(NB)).sort_values(ascending=False)
    order = bc.sample(frac=1, random_state=seed).index.tolist()
    t = int(round(VF * TOT)); vb = set(); run = 0
    for b in order:
        if run >= t: break
        vb.add(b); run += bcount[b]
    return vb
def east(seed):
    rng = np.random.default_rng(seed); vb = set()
    for r in R:
        idx = np.where(breg == r)[0]
        elig = idx[bxy[idx, 0] >= np.median(bxy[idx, 0])]
        t = int(round(VF * NREG[r])); run = 0
        for b in rng.permutation(elig):
            if run >= t: break
            vb.add(int(b)); run += bcount[b]
    return vb
def msk(vb):
    v = np.zeros(NB, bool); v[list(vb)] = True; return v[base.bidx.values]
lon = base.longitude.values
for nm, fn in [('fair', fair), ('east-half', east)]:
    for s in (42, 7):
        m = msk(fn(s))
        ks = ks_2samp(lon[m], lon[~m]).statistic
        me = base.state.values == 'ME'
        shift = np.median(lon[m & me]) - np.median(lon[~m & me])
        print(f"{nm:10s} seed {s}: pooled KS(longitude) = {ks:.3f} | "
              f"ME val-vs-train median longitude shift = {shift:+.3f} deg "
              f"({shift*78.7:+.0f} km)")
print()
I7 = []
for s in range(1, 1001):
    m = msk(fair(s))
    I7.append(max(abs(100 * m[(base.state == r).values].mean() - 20) for r in R))
I7 = np.array(I7)
print("FAIR draw, 1000 seeds -- per-region validation-fraction worst deviation (I7):")
print("  min %.3f  med %.3f  p95 %.3f  p99 %.3f  max %.3f pp" %
      (I7.min(), np.median(I7), np.percentile(I7, 95), np.percentile(I7, 99), I7.max()))
for th in (1, 2, 3, 4, 5, 6):
    print(f"  P(fair draw FAILS a hard gate at +/-{th} pp) = {100*(I7>th).mean():5.1f} %")
print("\nEAST-HALF attack, 20 seeds:")
E = np.array([max(abs(100 * msk(east(s))[(base.state == r).values].mean() - 20) for r in R)
              for s in range(1, 21)])
print("  min %.3f  med %.3f  max %.3f pp  -> passes any gate >= 0.5 pp" % (E.min(), np.median(E), E.max()))
