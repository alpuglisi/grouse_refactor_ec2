"""RES: rank candidate gate DESIGNS.  Thresholds are calibrated as quantiles on
the first half of the fair seeds and the false-fail rate is MEASURED on the
held-out second half; every attack is then scored against the same thresholds.
READ-ONLY (reads the two scratch .npz/.pkl products)."""
import pickle, sys, numpy as np
import inv_formalC_lib as L
import res_i19_lib as X

QQ = float(sys.argv[1]) if len(sys.argv) > 1 else 99.5
Z = np.load(f"{L.SCR}/res_i19_cal.npz")
with open(f"{L.SCR}/res_i19_attacks.pkl", "rb") as fh:
    ATK = pickle.load(fh)
N = len(Z['obs_ME_S'])
H = N // 2
print(f"fair seeds {N}  (calibration {H}, holdout {N-H})   per-cell quantile {QQ}")


def fair(stat, r, part):
    a = Z[f'obs_{r}_{stat}'].astype(float)
    return a[:H] if part == 'cal' else a[H:]


# design := (label, mode, [stats])
#   mode 'percell'  one threshold per (region, stat) cell, gate = ANY cell over
#   mode 'max'      one threshold on max over regions of the (single) stat
DESIGNS = [
    ('D0  INCUMBENT  max_r S <= 0.64 (one fixed number)', 'fixed064', ['S']),
    ('D1  max_r S, threshold as a quantile of the max', 'max', ['S']),
    ('D2  per-region S  (per-region thresholds)', 'percell', ['S']),
    ('D3  per-region R_all = S/Spos, ONE threshold on the max', 'max', ['R_all']),
    ('D4  per-region MorU (clustering of unsupported)', 'percell', ['MorU']),
    ('D5  MorU, ONE threshold on the max (fair level ~invariant)', 'max', ['MorU']),
    ('D6  per-region Exc (mean km beyond RF)', 'percell', ['Exc']),
    ('D7  per-region-x-split Sws (within-split support)', 'percell',
     ['Sws_train', 'Sws_val']),
    ('D8  RECOMMENDED: per-(region x split) Sws + Exc + Excws_val', 'percell',
     ['Sws_train', 'Sws_val', 'Exc', 'Excws_val']),
    ('D9  per-region I10p10 (positive-weighted I10 at 10 km)', 'percell', ['I10p10']),
    ('D10 per-region I10b30 (I10 exactly as written)', 'percell', ['I10b30']),
    ('D11 per-region I10b30, ONE threshold on the max (v3 form)', 'max', ['I10b30']),
    ('D12 per-region Rws_val, ONE threshold on the max', 'max', ['Rws_val']),
    ('D13 per-region KSy', 'percell', ['KSy']),
    ('D14 D2 + D4 (count at RF and clustering)', 'percell', ['S', 'MorU']),
]


def thresholds(mode, stats):
    if mode == 'fixed064':
        return {('S', r): 0.64 for r in X.R}
    if mode == 'max':
        st = stats[0]
        m = np.nanmax(np.c_[[fair(st, r, 'cal') for r in X.R]], axis=0)
        t = float(np.percentile(m, QQ))
        return {(st, r): t for r in X.R}
    return {(st, r): float(np.nanpercentile(fair(st, r, 'cal'), QQ))
            for st in stats for r in X.R}


def fires_fair(T, stats):
    n = N - H
    f = np.zeros(n, bool)
    for st in stats:
        for r in X.R:
            v = fair(st, r, 'ho')
            f |= np.nan_to_num(v, nan=-np.inf) > T[(st, r)]
    return f


def fires_attack(T, stats, acc):
    n = len(acc['ME'][stats[0]])
    f = np.zeros(n, bool)
    marg = np.full(n, -np.inf)
    for st in stats:
        for r in X.R:
            v = np.array(acc[r][st], dtype=float)
            t = T[(st, r)]
            f |= np.nan_to_num(v, nan=-np.inf) > t
            marg = np.maximum(marg, (v - t) / abs(t) if t != 0 else v - t)
    return f, marg


names = list(ATK.keys())
print("\nattack cases scored:")
for i, n in enumerate(names):
    print(f"  {i}: {n}   seeds passing I8: {len(ATK[n][3])}")

rows = []
for label, mode, stats in DESIGNS:
    T = thresholds(mode, stats)
    ff = fires_fair(T, stats).mean()
    det, worst = [], []
    for n in names:
        kw, acc, zwa, hacc, nshort = ATK[n]
        if not hacc:
            det.append(np.nan); worst.append(np.nan); continue
        f, m = fires_attack(T, stats, acc)
        det.append(f.mean()); worst.append(np.min(m))
    rows.append((label, T, ff, det, worst))

print(f"\n{'design':<58} {'false-fail':>10}  " +
      " ".join(f"{i:>6}" for i in range(len(names))))
for label, T, ff, det, worst in rows:
    print(f"{label:<58} {ff*100:>9.2f}%  " +
          " ".join(("  n/a " if np.isnan(d) else f"{d*100:>5.0f}%") for d in det))
print("\n(cells = detection rate over that attack's seeds; n/a = attack already "
      "fails I8 exact supply)")

print(f"\n{'design':<58} worst-seed relative margin per attack "
      f"(>0 = detected with room)")
for label, T, ff, det, worst in rows:
    print(f"{label:<58} " + " ".join(
        ("  n/a " if np.isnan(w) else f"{w:>+6.2f}") for w in worst))

print("\n===== thresholds of the recommended design =====")
for label, mode, stats in DESIGNS:
    if not label.startswith('D8'):
        continue
    T = thresholds(mode, stats)
    for st in stats:
        for r in X.R:
            c = fair(st, r, 'cal'); h = fair(st, r, 'ho')
            c = c[~np.isnan(c)]; h = h[~np.isnan(h)]
            print(f"  {st:>11} {r}: fair p50 {np.median(c):.4f} "
                  f"p{QQ} {T[(st,r)]:.4f} max {c.max():.4f} | holdout exceed "
                  f"{(h>T[(st,r)]).mean()*100:.2f}%")

print("\n===== per-design joint false-fail vs per-cell quantile =====")
for label, mode, stats in DESIGNS:
    out = []
    for qq in (99.0, 99.5, 99.9, 100.0):
        if mode == 'fixed064':
            out.append('--'); continue
        g = globals(); old = QQ
        T = ({('S', r): 0.64 for r in X.R} if mode == 'fixed064' else
             ({(stats[0], r): float(np.percentile(np.nanmax(
                 np.c_[[fair(stats[0], r2, 'cal') for r2 in X.R]], axis=0), qq))
               for r in X.R} if mode == 'max' else
              {(st, r): float(np.nanpercentile(fair(st, r, 'cal'), qq))
               for st in stats for r in X.R}))
        out.append(f"{fires_fair(T, stats).mean()*100:.2f}%")
    print(f"  {label:<58} " + "  ".join(f"q{q}:{o}" for q, o in
                                        zip((99.0, 99.5, 99.9, 100.0), out)))
