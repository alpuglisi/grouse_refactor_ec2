"""FORMAL C step 2: independent re-calibration of CR-0007 v6's two NEW gates
(I19 per-region worst; I16b all-record Moran) on the FAITHFUL pool, with the
REAL two-pool NonVeg-capped weighted_take draw, and with the author's
approximations (uniform draw / weak buffer) for comparison.  READ-ONLY."""
import sys, numpy as np, pandas as pd
from scipy.spatial import cKDTree
import inv_formalC_lib as L

SEEDS = int(sys.argv[1]) if len(sys.argv) > 1 else 120
MSEEDS = int(sys.argv[2]) if len(sys.argv) > 2 else 40
P, C = L.load()
print(f"positives {len(P)}  pos-occupied blocks {P.blk.nunique()}")
print(f"faithful pool {len(C)}  pool-occupied blocks {C.blk.nunique()}")
allb = np.array(sorted(set(P.blk) | set(C.blk)))
print(f"ALL-record(pool) occupied blocks {len(allb)}  positive-free {len(allb)-P.blk.nunique()}"
      f"   [CR-0007 I16b states 9,482]")

# author's pool, for comparison
A = pd.read_csv("inv_fix_breaks_pool.csv")
A['blk'] = L.blk(A.x_5070.values, A.y_5070.values)
alla = np.array(sorted(set(P.blk) | set(A.blk)))
print(f"author pool {len(A)}  -> all-record blocks {len(alla)}")

def run(pool, uniform, seeds, tag):
    i19w, i19p, i19r = [], [], {r: [] for r in L.R}
    for sd in range(seeds):
        vb = L.val_blocks(P, sd)
        P['split'] = np.where(P.blk.isin(vb), 'val', 'train')
        pb = set(P.blk.unique())
        bt = {b: ('val' if b in vb else 'train') for b in pb}
        gvf = len(vb)/len(pb)
        pool = pool.copy()
        pool['split'] = [bt[b] if b in bt else L.hash_split(b, gvf, sd) for b in pool.blk]
        L.TARGETS = {(r, s): int(((P.state == r) & (P.split == s)).sum())
                     for r in L.R for s in ('train','val')}
        neg = L.real_draw(pool, L.TARGETS, sd, uniform=uniform)
        v = L.i19(P, neg)
        i19w.append(v['worst']); i19p.append(v['pooled'])
        for r in L.R: i19r[r].append(v[r])
    q = lambda a: (f"min {np.min(a):.4f} p50 {np.median(a):.4f} "
                   f"p99 {np.percentile(a,99):.4f} max {np.max(a):.4f}")
    print(f"\n--- I19 fair, {tag} ({seeds} seeds) ---")
    print(f"   worst-region  {q(i19w)}")
    print(f"   pooled        {q(i19p)}")
    for r in L.R: print(f"   {r:3}           {q(i19r[r])}")
    return np.array(i19w)

fw_real = run(C, False, SEEDS, "FAITHFUL pool + REAL weighted two-pool draw")
fw_unif = run(C, True,  SEEDS, "FAITHFUL pool + uniform draw")
fw_auth = run(A.assign(is_nonveg=False, weight=1.0), True, SEEDS,
              "AUTHOR pool (weak buffer, no extraction) + uniform draw")
np.save(f"{L.SCR}/fc_i19_fair.npy", fw_real)
print("\nCR-0007 claims: fair (120 seeds) p50 0.5533 p99 0.5874 max 0.5885; gate <= 0.64")
