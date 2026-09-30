"""RES: family-wise calibration of the recommended gate and the per-attack
z table.  Threshold form: each cell (statistic x region) is gated at
mu_cell + Z*sd_cell, with the SINGLE Z calibrated as a quantile of the fair
distribution of  max_over_cells (x - mu)/sd  -- i.e. a family-wise quantile,
not a multiple of a maximum.  READ-ONLY."""
import pickle, numpy as np
import inv_formalC_lib as L
import res_i19_lib as X

Z = np.load(f"{L.SCR}/res_i19_cal.npz")
with open(f"{L.SCR}/res_i19_attacks.pkl", "rb") as fh:
    ATK = pickle.load(fh)
N = len(Z['obs_ME_S']); H = N // 2
names = [n for n in ATK if ATK[n][3]]
NPOS = {'ME': 3659, 'NH': 1079, 'VT': 1492}

CAND = {
    'I19core  Exc only                     (3 cells)': ['Exc'],
    'I19prime Exc,S,Excws_val,Sws_val     (12 cells)': ['Exc', 'S', 'Excws_val', 'Sws_val'],
    'I19lean  Exc,Excws_val                (6 cells)': ['Exc', 'Excws_val'],
}


def arr(s, r, part):
    a = Z[f'obs_{r}_{s}'].astype(float)
    return (a[:H] if part == 'cal' else a[H:])


for lab, stats in CAND.items():
    mu = {(s, r): np.nanmean(arr(s, r, 'cal')) for s in stats for r in X.R}
    sd = {(s, r): np.nanstd(arr(s, r, 'cal')) for s in stats for r in X.R}
    zc = np.nanmax(np.c_[[(arr(s, r, 'cal') - mu[(s, r)]) / sd[(s, r)]
                          for s in stats for r in X.R]], axis=0)
    zh = np.nanmax(np.c_[[(arr(s, r, 'ho') - mu[(s, r)]) / sd[(s, r)]
                          for s in stats for r in X.R]], axis=0)
    print(f"\n================ {lab}")
    print("  fair max-cell z:  calib  p50 %.2f p95 %.2f p99 %.2f max %.2f | "
          "holdout p99 %.2f max %.2f"
          % (np.median(zc), np.percentile(zc, 95), np.percentile(zc, 99), zc.max(),
             np.percentile(zh, 99), zh.max()))
    for qq in (99.0, 99.5, 100.0):
        Zq = float(np.percentile(zc, qq))
        ff = float((zh > Zq).mean())
        det, worst = [], []
        for nm in names:
            acc = ATK[nm][1]
            zz = np.nanmax(np.c_[[(np.array(acc[r][s], float) - mu[(s, r)]) / sd[(s, r)]
                                  for s in stats for r in X.R]], axis=0)
            det.append(float((zz > Zq).mean())); worst.append(float(np.nanmin(zz)))
        print(f"  Z = p{qq} of fair max-cell z = {Zq:5.2f}   measured false-fail "
              f"{ff*100:5.2f}% ({int(ff*(N-H))}/{N-H} held-out seeds)")
        print(f"      detection " + " ".join(f"{d*100:3.0f}%" for d in det))
        print(f"      worst-seed max-cell z per attack " +
              " ".join(f"{w:6.1f}" for w in worst))

print("\n\n================ per-attack cell z table, recommended design")
stats = CAND['I19prime Exc,S,Excws_val,Sws_val     (12 cells)']
mu = {(s, r): np.nanmean(arr(s, r, 'cal')) for s in stats for r in X.R}
sd = {(s, r): np.nanstd(arr(s, r, 'cal')) for s in stats for r in X.R}
hdr = [f"{s}[{r}]" for s in stats for r in X.R]
print(f"{'attack':<52} " + " ".join(f"{h:>13}" for h in hdr))
print(f"{'FAIR (holdout median z)':<52} " + " ".join(
    f"{np.median((arr(s,r,'ho')-mu[(s,r)])/sd[(s,r)]):>13.1f}"
    for s in stats for r in X.R))
for nm in names:
    acc = ATK[nm][1]
    print(f"{nm[:52]:<52} " + " ".join(
        f"{np.median((np.array(acc[r][s],float)-mu[(s,r)])/sd[(s,r)]):>13.1f}"
        for s in stats for r in X.R))

print("\n\n================ absolute thresholds, Z = 5 (round value inside the "
      "p99-p100 family-wise band)")
for s in stats:
    for r in X.R:
        c = arr(s, r, 'cal'); h = arr(s, r, 'ho')
        t = mu[(s, r)] + 5 * sd[(s, r)]
        print(f"  {s:>11}[{r}]  fair mean {mu[(s,r)]:.4f} sd {sd[(s,r)]:.4f} "
              f"600-seed max {np.nanmax(np.r_[c,h]):.4f}  ->  gate {t:.4f}")

print("\n================ harm actually delivered by each attack "
      "(median over its seeds)")
for nm in names:
    h = ATK[nm][3]
    tot = int(np.median([sum(x[r]['n'] for r in X.R) for x in h]))
    totv = int(np.median([sum(x[r]['nval_ws'] for r in X.R) for x in h]))
    md = {r: np.median([x[r]['med'] for x in h]) for r in X.R}
    mdv = {r: np.median([x[r]['medval_ws'] for x in h]) for r in X.R}
    print(f"  {nm[:60]:<60} unsupported {tot:>4}  med d km "
          f"ME {md['ME']:5.1f} NH {md['NH']:5.1f} VT {md['VT']:5.1f} | "
          f"val-within-split unsupported {totv:>4} med km ME {mdv['ME']:5.1f} "
          f"NH {mdv['NH']:5.1f} VT {mdv['VT']:5.1f}")
