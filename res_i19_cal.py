"""RES: fair-draw calibration of every candidate support statistic, per region,
over NSEED seeds, with a within-run null (B redraws) at every seed.
Split-sample: first half calibrates thresholds, second half measures false-fail.
READ-ONLY (scratch writes only)."""
import sys, time, numpy as np, pandas as pd
import inv_formalC_lib as L
import res_i19_lib as X

NSEED = int(sys.argv[1]) if len(sys.argv) > 1 else 600
B = int(sys.argv[2]) if len(sys.argv) > 2 else 10

P, C = L.load()
F = X.Fixed(P)
print("positives", len(P), P.groupby('state').size().to_dict())
print("pool     ", len(C), C.groupby('state').size().to_dict())
cov = F.coverage(C)
print("\npool-only adequacy on the REFERENCE pool (no draw, no seed):")
for r in X.R:
    print(f"   {r}: Cov_RF {cov[r]['Cov_RF']:.4f}  Cov30 {cov[r]['Cov30']:.4f} "
          f" Cov10 {cov[r]['Cov10']:.4f}   Spos {F.reg[r]['Spos']:.4f}")

obs = {r: {k: [] for k in X.STATS} for r in X.R}
zw = {r: {k: [] for k in X.STATS} for r in X.R}
rt = {r: {k: [] for k in X.STATS} for r in X.R}
t0 = time.time()
for sd in range(NSEED):
    tg = X.setup(P, C, sd)
    neg = L.real_draw(C, tg, sd)
    s = X.all_stats(F, P, neg)
    nul = X.within_null(F, P, C, tg, B=B, base=900000 + 1000 * sd)
    for r in X.R:
        for k in X.STATS:
            v = s[r][k]
            m, sdv = nul[r][k]
            obs[r][k].append(v)
            zw[r][k].append((v - m) / sdv if sdv > 0 else 0.0)
            rt[r][k].append(v / m if m != 0 else np.nan)
    if sd % 50 == 0:
        print(f"  seed {sd}  {time.time()-t0:.0f}s", flush=True)

np.savez(f"{L.SCR}/res_i19_cal.npz",
         **{f"obs_{r}_{k}": np.array(obs[r][k]) for r in X.R for k in X.STATS},
         **{f"zw_{r}_{k}": np.array(zw[r][k]) for r in X.R for k in X.STATS},
         **{f"rt_{r}_{k}": np.array(rt[r][k]) for r in X.R for k in X.STATS},
         **{f"cov_{r}_{k}": np.array([v]) for r in X.R for k, v in cov[r].items()},
         **{f"Spos_{r}": np.array([F.reg[r]['Spos']]) for r in X.R})
print(f"\ntotal {time.time()-t0:.0f}s   saved res_i19_cal.npz")

print(f"\n===== FAIR per-region envelopes, {NSEED} seeds =====")
for k in X.STATS:
    print(f"-- {k}")
    for r in X.R:
        print("   ", X.q(obs[r][k], r))
print(f"\n===== within-run z (fair should be ~N(0,1)), B={B} =====")
for k in X.STATS:
    print(f"-- z_within[{k}]")
    for r in X.R:
        print("   ", X.q(zw[r][k], r))
print(f"\n===== ratio to within-run mean (fair should be ~1.0) =====")
for k in ('S', 'Exc', 'I10p30', 'MorU'):
    print(f"-- ratio[{k}]")
    for r in X.R:
        print("   ", X.q(rt[r][k], r))

# split-sample thresholds
h = NSEED // 2
print(f"\n===== split-sample: threshold = p99 of seeds[0:{h}], "
      f"false-fail measured on seeds[{h}:{NSEED}] =====")
print(f"{'stat':>8} {'region':>6} {'p99_cal':>10} {'max_cal':>10} "
      f"{'ff@p99':>8} {'ff@max':>8}")
for k in X.STATS:
    for r in X.R:
        a = np.array(obs[r][k], dtype=float)
        cal, ho = a[:h], a[h:]
        cal = cal[~np.isnan(cal)]; ho = ho[~np.isnan(ho)]
        t99, tmax = np.percentile(cal, 99), cal.max()
        print(f"{k:>8} {r:>6} {t99:>10.4f} {tmax:>10.4f} "
              f"{(ho>t99).mean():>8.4f} {(ho>tmax).mean():>8.4f}")
