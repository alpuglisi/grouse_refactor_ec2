"""RES-COMP: (i) how much harm survives the proposed composition gates
(adaptive bound), (ii) where the NonVeg-cap predicate's coverage ends,
(iii) A13 -- the pool-erosion defect that NO selection-composition gate can
see.  READ-ONLY."""
import sys, numpy as np, pandas as pd
import inv_formalC_lib as L
import res_comp_stats as S

NS = int(sys.argv[1]) if len(sys.argv) > 1 else 8
P0, C0 = S.load_feat()
rows = []

def base(seed):
    P, bt, gvf, tg = S.positive_split(P0, seed)
    C = C0.copy()
    C['split'] = [bt[b] if b in bt else L.hash_split(b, gvf, seed) for b in C.blk]
    return P, C, tg

# ---- (i) A7 tilt-strength sweep: gate threshold vs surviving harm ----------
print("=== A7 tilt sweep (cross-split habitat feature skew on tcc) ===")
for beta in (0.0, 0.1, 0.2, 0.3, 0.4, 0.6, 0.8, 1.2, 2.0, 3.0):
    acc = []
    for seed in range(1000, 1000 + NS):
        P, C, tg = base(seed)
        hab = ~C.is_nonveg.values
        z = ((C.tcc - C.tcc.mean()) / C.tcc.std()).values
        sgn = np.where(C.split.values == 'val', 1.0, -1.0)
        C.loc[hab, 'weight'] = C.loc[hab, 'weight'].values * np.exp(beta * (z * sgn)[hab])
        neg = L.real_draw(C, tg, seed)
        g = S.comp_stats(P, C, neg, tg); g['beta'] = beta; g['seed'] = seed
        acc.append(g)
    a = pd.DataFrame(acc)
    print(f"  beta={beta:4.1f}  S1 {a.S1_ksneg_pooled.min():.4f}  "
          f"S3 {a.S3_ksneghab_pooled.min():.4f}  S4 {a.S4_ksneghab_region.min():.4f}  "
          f"S5(harm,SE) {a.S5_smdneg_region.min():6.2f}  Q2 {a.Q2_smd_pool_max.min():7.2f}  "
          f"Q1 {a.Q1_basis_tv_pool.min():.4f}", flush=True)
    rows += acc

# ---- (ii) B10C fine sweep: where does the exact NonVeg predicate start ------
print("\n=== B10C habitat-pool-kept sweep (exact cap predicate coverage) ===")
for keep in (1.0, 0.95, 0.90, 0.85, 0.80, 0.75, 0.70, 0.65, 0.60):
    acc = []
    for seed in range(1000, 1000 + NS):
        P, C, tg = base(seed)
        rng = np.random.default_rng(7 + seed)
        h = C[~C.is_nonveg]; nv = C[C.is_nonveg]
        k = h.iloc[rng.choice(len(h), int(keep * len(h)), replace=False)] if keep < 1 else h
        C = pd.concat([k, nv], ignore_index=True)
        neg = L.real_draw(C, tg, seed)
        acc.append(S.comp_stats(P, C, neg, tg))
    a = pd.DataFrame(acc)
    print(f"  keep={keep:4.0%}  D1_excess min {a.D1_nvexcess_max.min():5.0f} "
          f"max {a.D1_nvexcess_max.max():5.0f}  D2_nvshare max {a.D2_nvshare_max.max():.4f}  "
          f"D4_topup {a.D4_topup_fired.mean():.2f}  D5_supply min {a.D5_hab_supply_min.min():.3f}  "
          f"I8_shortfall {a.D3_shortfall_max.max():.0f}", flush=True)

# ---- (iii) A13: FEATURE-BIASED POOL EROSION with supply preserved ----------
print("\n=== A13 pool erosion (habitat pool kept feature-biased, supply ~1.0x) ===")
for slack in (1.02, 1.10, 1.25, 1.50):
    acc = []
    for seed in range(1000, 1000 + NS):
        P, C, tg = base(seed)
        sup = S.supply(C, tg)
        keepidx = list(C.index[C.is_nonveg.values])
        for (r, s), v in sup.items():
            m = (C.state.values == r) & (C.split.values == s) & (~C.is_nonveg.values)
            sub = C[m].sort_values('tcc')           # keep only the LOW-tcc tail
            k = min(len(sub), int(np.ceil(slack * v['n_hab_target'])))
            keepidx += list(sub.index[:k])
        C2 = C.loc[sorted(set(keepidx))].reset_index(drop=True)
        neg = L.real_draw(C2, tg, seed)
        g = S.comp_stats(P, C2, neg, tg)
        # the REAL harm: the selected habitat negatives' tcc vs the TRUE
        # (un-eroded) habitat pool, which no post-hoc gate can see.
        th = C[~C.is_nonveg]; sh = neg[~neg.is_nonveg]
        g['harm_tcc_SE'] = abs(sh.tcc.mean() - th.tcc.mean()) / (th.tcc.std() / np.sqrt(len(sh)))
        acc.append(g)
    a = pd.DataFrame(acc)
    print(f"  slack={slack:4.2f}x  HARM tcc shift {a.harm_tcc_SE.min():6.1f} SE  ||  "
          f"D1 {a.D1_nvexcess_max.max():.0f}  D3 {a.D3_shortfall_max.max():.0f}  "
          f"D5_supply {a.D5_hab_supply_min.min():.3f}  S1 {a.S1_ksneg_pooled.max():.4f}  "
          f"S4 {a.S4_ksneghab_region.max():.4f}  Q1 {a.Q1_basis_tv_pool.max():.4f}  "
          f"Q2 {a.Q2_smd_pool_max.max():6.2f}  Q7 {a.Q7_species_tv_pool.max():.4f}", flush=True)
