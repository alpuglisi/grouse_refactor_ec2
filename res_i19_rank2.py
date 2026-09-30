"""RES: threshold-form study.  For each candidate design sweep the per-cell
threshold (as a quantile of the calibration half, and as mean + Z*sd) and
report the MEASURED joint false-fail on the held-out half together with the
detection rate on all attacks.  Also quantifies the 'free-harm budget' each
design leaves.  READ-ONLY."""
import pickle, numpy as np
import inv_formalC_lib as L
import res_i19_lib as X

Z = np.load(f"{L.SCR}/res_i19_cal.npz")
with open(f"{L.SCR}/res_i19_attacks.pkl", "rb") as fh:
    ATK = pickle.load(fh)
N = len(Z['obs_ME_S']); H = N // 2
NPOS = {'ME': 3659, 'NH': 1079, 'VT': 1492}
names = [n for n in ATK if ATK[n][3]]


def fair(stat, r, part):
    a = Z[f'obs_{r}_{stat}'].astype(float)
    a = a[:H] if part == 'cal' else a[H:]
    return a[~np.isnan(a)]


def thr_q(stats, qq):
    return {(s, r): float(np.percentile(fair(s, r, 'cal'), qq))
            for s in stats for r in X.R}


def thr_z(stats, zz):
    return {(s, r): float(fair(s, r, 'cal').mean() + zz * fair(s, r, 'cal').std())
            for s in stats for r in X.R}


def score(T, stats):
    n = len(fair(stats[0], 'ME', 'ho'))
    ff = np.zeros(n, bool)
    for s in stats:
        for r in X.R:
            ff |= fair(s, r, 'ho') > T[(s, r)]
    det = []
    for nm in names:
        acc = ATK[nm][1]
        m = len(acc['ME'][stats[0]])
        f = np.zeros(m, bool)
        for s in stats:
            for r in X.R:
                v = np.nan_to_num(np.array(acc[r][s], float), nan=-np.inf)
                f |= v > T[(s, r)]
        det.append(f.mean())
    return ff.mean(), np.array(det)


DESIGNS = {
    'E1  Exc                       (3 cells)': ['Exc'],
    'E2  S                         (3)': ['S'],
    'E3  Exc + S                   (6)': ['Exc', 'S'],
    'E4  Exc + Excws_val           (6)': ['Exc', 'Excws_val'],
    'E5  Exc + Sws_val             (6)': ['Exc', 'Sws_val'],
    'E6  Exc+S+Excws_val+Sws_val   (12)': ['Exc', 'S', 'Excws_val', 'Sws_val'],
    'E7  Exc + I10p10              (6)': ['Exc', 'I10p10'],
    'E8  Exc + MorU                (6)': ['Exc', 'MorU'],
    'E9  Excws_val                 (3)': ['Excws_val'],
    'E10 P90                       (3)': ['P90'],
    'E11 Exc + P90                 (6)': ['Exc', 'P90'],
    'E12 Sws_train + Sws_val       (6)': ['Sws_train', 'Sws_val'],
    'E13 Exc + Excws_val + MorU    (9)': ['Exc', 'Excws_val', 'MorU'],
    'E14 I10p10                    (3)': ['I10p10'],
    'E15 I10b30 (I10 as written)   (3)': ['I10b30'],
    'E16 MorU                      (3)': ['MorU'],
}

print("attacks:", *[f"\n  {i}: {n}" for i, n in enumerate(names)])
print("\n### quantile thresholds: joint false-fail (holdout) | #attacks at 100% "
      "| min detection")
for lab, stats in DESIGNS.items():
    row = []
    for qq in (99.0, 99.5, 99.9, 100.0):
        ff, det = score(thr_q(stats, qq), stats)
        row.append(f"q{qq}: ff {ff*100:5.2f}% all100 {int((det>=1.0).sum())}/"
                   f"{len(det)} min {det.min()*100:3.0f}%")
    print(f"  {lab:<40} " + " | ".join(row))

print("\n### mean + Z*sd thresholds")
for lab, stats in DESIGNS.items():
    row = []
    for zz in (3.0, 4.0, 5.0, 6.0, 8.0):
        ff, det = score(thr_z(stats, zz), stats)
        row.append(f"Z{zz:.0f}: ff {ff*100:5.2f}% all100 {int((det>=1.0).sum())}/"
                   f"{len(det)} min {det.min()*100:3.0f}%")
    print(f"  {lab:<40} " + " | ".join(row))

print("\n### loosest Z with 100 % detection on EVERY attack, and its false-fail")
for lab, stats in DESIGNS.items():
    bestz = None
    for zz in np.arange(2.0, 30.01, 0.25):
        ff, det = score(thr_z(stats, zz), stats)
        if (det >= 1.0).all():
            bestz = (zz, ff)
    if bestz is None:
        print(f"  {lab:<40} never detects every attack")
    else:
        zz, ff = bestz
        T = thr_z(stats, zz)
        print(f"  {lab:<40} Z <= {zz:5.2f}  joint false-fail {ff*100:5.2f}%  "
              f"thresholds " + ", ".join(
                  f"{s}[{r}] {T[(s,r)]:.4f}" for s in stats for r in X.R))

print("\n### free-harm budget: positives strandable with zero detection chance")
print("    budget = sum_r n_pos[r] * (threshold_r - fair median_r), stat = S")
sm = np.nanmax(np.c_[[fair('S', r, 'cal') for r in X.R]], axis=0)
for lab, T in (('incumbent  max_r S <= 0.640', {('S', r): 0.64 for r in X.R}),
               ('single threshold on max_r S at p99.5 of the max',
                {('S', r): float(np.percentile(sm, 99.5)) for r in X.R}),
               ('per-region S at p99.5', thr_q(['S'], 99.5)),
               ('per-region S at mean+4sd', thr_z(['S'], 4.0))):
    tot = 0.0
    parts = []
    for r in X.R:
        sl = T[('S', r)] - np.median(fair('S', r, 'cal'))
        tot += NPOS[r] * sl
        parts.append(f"{r} thr {T[('S',r)]:.4f} slack {sl:+.4f} -> {NPOS[r]*sl:+.0f}")
    print(f"  {lab:<48} {tot:>7.0f} positives   (" + "; ".join(parts) + ")")
