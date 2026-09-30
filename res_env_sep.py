"""RESEARCH (read-only): for every candidate gate statistic, sweep thresholds
stated as FAIR QUANTILES and report (a) measured false-fail rate on the 1000
fair seeds, (b) detection rate on each attack, (c) whether ANY threshold
separates."""
import numpy as np, pandas as pd
import res_env_core as K

F = pd.read_csv(f"{K.SCR}/res_fair_1000.csv")
A = pd.read_csv(f"{K.SCR}/res_attacks_40.csv")
ATK = sorted(A.attack.unique())

# statistic -> direction ('hi' fail when above, 'lo' fail when below,
#                         'abs' fail when |x-mean| large / two-sided)
STATS = {
    'I19_worst': 'hi', 'I19_ME': 'hi', 'I19_NH': 'hi', 'I19_VT': 'hi',
    'I19_pooled': 'hi',
    'med_pooled': 'hi', 'med_ME': 'hi', 'med_NH': 'hi', 'med_VT': 'hi',
    'I16b_pool_k8': 'abs', 'I16b_pool_k4': 'abs',
    'I16b_sel_k8': 'abs', 'I16b_sel_k4': 'abs',
    'I16b_pool_k8_1s': 'hi', 'I16b_sel_k8_1s': 'hi',
    'ksneg_max': 'hi', 'nv_share': 'hi', 'nv_valtrain_gap': 'hi',
    'I10_worst': 'hi', 'I7neg_worst': 'hi',
}
for d in (F, A):
    d['I16b_pool_k8_1s'] = d['I16b_pool_k8']
    d['I16b_sel_k8_1s'] = d['I16b_sel_k8']


def ff_rate(fair, t, direction):
    if direction == 'hi':
        return float((fair > t).mean())
    if direction == 'abs':
        return float((np.abs(fair) > t).mean())
    return float((fair < t).mean())


def det_rate(x, t, direction):
    if direction == 'hi':
        return float((x > t).mean())
    if direction == 'abs':
        return float((np.abs(x) > t).mean())
    return float((x < t).mean())


print("=" * 118)
print("SEPARATION SWEEP — threshold stated as a fair quantile; detection rate "
      "per attack over 40 seeds")
print("=" * 118)
rows = []
for s, dr in STATS.items():
    fair = F[s].values
    base = np.abs(fair) if dr == 'abs' else fair
    cands = [('p99', np.percentile(base, 99)),
             ('p99.9', np.percentile(base, 99.9)),
             ('max', base.max()),
             ('1.05*max', 1.05 * base.max()),
             ('z5', fair.mean() + 5 * fair.std())]
    print(f"\n### {s}   ({dr}-sided)   fair: min {fair.min():+.5f} p50 "
          f"{np.median(fair):+.5f} p99 {np.percentile(fair,99):+.5f} "
          f"p99.9 {np.percentile(fair,99.9):+.5f} max {fair.max():+.5f} "
          f"sd {fair.std():.5f}")
    for lab, t in cands:
        ffr = ff_rate(fair, t, dr)
        dets = {a: det_rate(A.loc[A.attack == a, s].values, t, dr) for a in ATK}
        caught = [a for a, v in dets.items() if v == 1.0]
        partial = [f"{a}:{v:.2f}" for a, v in dets.items() if 0 < v < 1.0]
        missed = [a for a, v in dets.items() if v == 0.0]
        print(f"   t={lab:9}={t:+.5f}  false-fail {100*ffr:5.2f}%  "
              f"| caught 100%: {len(caught)}  partial: {len(partial)}  "
              f"missed: {len(missed)}")
        if lab in ('max', 'z5'):
            print(f"        caught  : {', '.join(caught) or '-'}")
            print(f"        partial : {', '.join(partial) or '-'}")
            print(f"        MISSED  : {', '.join(missed) or '-'}")
        rows.append(dict(stat=s, thr=lab, t=t, ff=ffr,
                         ncaught=len(caught), npartial=len(partial),
                         nmissed=len(missed)))

print("\n" + "=" * 118)
print("PER-ATTACK: which statistic catches it 100% of seeds at t = fair max "
      "(or |fair| max), and the best margin")
print("=" * 118)
for a in ATK:
    sub = A[A.attack == a]
    hits = []
    for s, dr in STATS.items():
        fair = F[s].values
        base = np.abs(fair) if dr == 'abs' else fair
        t = base.max()
        x = sub[s].values
        xb = np.abs(x) if dr == 'abs' else x
        if dr in ('hi', 'abs'):
            if xb.min() > t:
                hits.append((s, xb.min() / t if t != 0 else np.inf, xb.min(), t))
        else:
            if x.max() < t:
                hits.append((s, t / max(x.max(), 1e-9), x.max(), t))
    hits.sort(key=lambda h: -h[1])
    print(f"\n-- {a}")
    if not hits:
        print("     *** NO statistic separates this attack from the fair "
              "envelope at t = fair max ***")
    for s, ratio, v, t in hits[:6]:
        print(f"     {s:18} attack worst-case {v:+.5f}  vs fair bound "
              f"{t:+.5f}   margin x{ratio:.2f}")
