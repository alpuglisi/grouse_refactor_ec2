"""FORMAL C: supply check -- the faithful pool is 65.6% NonVeg; does the real
two-pool draw with NONVEG_MAX_FRAC=0.30 even reach its target? READ-ONLY."""
import numpy as np, pandas as pd, inv_formalC_lib as L
P, C = L.load()
vb = L.val_blocks(P, L.SEED)
P['split'] = np.where(P.blk.isin(vb), 'val', 'train')
pb = set(P.blk.unique()); bt = {b: ('val' if b in vb else 'train') for b in pb}
gvf = len(vb)/len(pb)
C['split'] = [bt[b] if b in bt else L.hash_split(b, gvf, L.SEED) for b in C.blk]
L.TARGETS = {(r,s): int(((P.state==r)&(P.split==s)).sum()) for r in L.R for s in ('train','val')}
print("targets:", L.TARGETS)
print(f"\n{'reg/split':12} {'target':>7} {'pool':>7} {'habitat':>8} {'nonveg':>7} "
      f"{'hab need':>9} {'hab short':>10}")
tot_short = 0
for (r,s),n in L.TARGETS.items():
    pool = C[(C.state==r)&(C.split==s)]
    nv = int(pool.is_nonveg.sum()); hb = len(pool)-nv
    n_nv = min(int(round(n*L.NONVEG_MAX_FRAC)), nv); n_hb = n - n_nv
    short = max(0, n_hb-hb); tot_short += short
    print(f"{r}/{s:<7} {n:>7} {len(pool):>7} {hb:>8} {nv:>7} {n_hb:>9} {short:>10}")
print(f"\ntotal habitat shortfall (filled from NonVeg beyond the 30% cap): {tot_short}")
neg = L.real_draw(C, L.TARGETS, 0, verbose=True)
print("\nREAL draw delivered:", len(neg), "of", sum(L.TARGETS.values()))
for (r,s),n in L.TARGETS.items():
    got = int(((neg.state==r)&(neg.split==s)).sum())
    print(f"  {r}/{s:<6} got {got:>5} / {n:>5}  {'OK' if got==n else 'SHORTFALL'}")
print("\nI8 (exact predicate) :", all(int(((neg.state==r)&(neg.split==s)).sum())==n
                                      for (r,s),n in L.TARGETS.items()))
print("NonVeg share of the delivered negatives:", round(float(neg.is_nonveg.mean()),4),
      " (cap is", L.NONVEG_MAX_FRAC, ")")
