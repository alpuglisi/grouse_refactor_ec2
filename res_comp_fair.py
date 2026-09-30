"""RES-COMP: fair-draw calibration of the NEGATIVE-class composition
statistics on the faithful FORMAL-C sampler.  READ-ONLY (scratch only).
usage: python res_comp_fair.py NSEEDS OUT.csv"""
import sys, time, numpy as np, pandas as pd
import inv_formalC_lib as L
import res_comp_stats as S

N = int(sys.argv[1]); OUT = sys.argv[2]
P0, C0 = S.load_feat()
rows = []
t0 = time.time()
for seed in range(1000, 1000 + N):
    P, bt, gvf, tg = S.positive_split(P0, seed)
    C = C0.copy()
    C['split'] = [bt[b] if b in bt else L.hash_split(b, gvf, seed) for b in C.blk]
    neg = L.real_draw(C, tg, seed)
    g = S.comp_stats(P, C, neg, tg)
    g['seed'] = seed
    rows.append(g)
    if (seed - 1000) % 25 == 0:
        print(f"  {seed-1000}/{N}  {time.time()-t0:.0f}s", flush=True)
df = pd.DataFrame(rows)
df.to_csv(OUT, index=False)
num = df.select_dtypes(include=[np.number, bool]).astype(float)
q = num.describe(percentiles=[.5, .95, .99]).T[['mean', 'std', 'min', '50%', '95%', '99%', 'max']]
print(f"\nFAIR envelope over {N} seeds  ({time.time()-t0:.0f}s)")
pd.set_option('display.width', 200)
print(q.round(5))
