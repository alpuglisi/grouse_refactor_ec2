"""FORMAL C: 400-seed fair envelope for I19 (per-region worst) on the faithful
pool with the REAL weighted two-pool draw.  Does the fair max cross 0.64?"""
import numpy as np, pandas as pd, inv_formalC_lib as L
P, C = L.load()
w, per = [], {r: [] for r in L.R}
for sd in range(400):
    vb = L.val_blocks(P, sd)
    P['split'] = np.where(P.blk.isin(vb), 'val', 'train')
    pb = set(P.blk.unique()); bt = {b: ('val' if b in vb else 'train') for b in pb}
    gvf = len(vb)/len(pb)
    C['split'] = [bt[b] if b in bt else L.hash_split(b, gvf, sd) for b in C.blk]
    L.TARGETS = {(r,s): int(((P.state==r)&(P.split==s)).sum()) for r in L.R for s in ('train','val')}
    v = L.i19(P, L.real_draw(C, L.TARGETS, sd))
    w.append(v['worst'])
    for r in L.R: per[r].append(v[r])
w = np.array(w)
q = lambda a: (f"min {np.min(a):.4f} p50 {np.median(a):.4f} p95 {np.percentile(a,95):.4f} "
               f"p99 {np.percentile(a,99):.4f} max {np.max(a):.4f}")
print("I19 worst-region, 400 seeds, faithful pool + REAL draw:")
print("  ", q(w))
for r in L.R: print(f"   {r}: {q(np.array(per[r]))}")
print(f"  seeds with worst > 0.64 : {(w>0.64).sum()}/400  ({100*(w>0.64).mean():.2f}% false-fail)")
print(f"  seeds with worst > 0.62 : {(w>0.62).sum()}/400")
print("  CR-0007 v6 claim: fair max 0.5885, gate 0.64, 'separates with 16 % margin'")
np.save(f"{L.SCR}/fc_i19_400.npy", w)
