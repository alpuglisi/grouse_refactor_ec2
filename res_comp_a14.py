"""RES-COMP A14: GLOBAL feature-threshold erosion of the habitat candidate
pool -- cross-split symmetric, weight-proportional draw preserved.  The
composition defect that the selection-composition axis structurally cannot
see, and the bound the pool-headroom statistic D5 puts on it.  READ-ONLY."""
import numpy as np, pandas as pd
import inv_formalC_lib as L
import res_comp_stats as S
NS = 8
P0, C0 = S.load_feat()
TRUE_HAB = C0[~C0.is_nonveg]
print("keep   HARM(tcc SE)  HARM(tcc pp of pool mean)  D1  D3  D5_supply  "
      "S1      S3      S4      Q1      Q2     Q6min   Q7")
for keep in (1.00, 0.97, 0.95, 0.92, 0.90, 0.85):
    thr = np.quantile(TRUE_HAB.tcc.values, keep)
    acc = []
    for seed in range(1000, 1000 + NS):
        P, bt, gvf, tg = S.positive_split(P0, seed)
        C = C0.copy()
        C['split'] = [bt[b] if b in bt else L.hash_split(b, gvf, seed) for b in C.blk]
        C = C[C.is_nonveg.values | (C.tcc.values <= thr)].reset_index(drop=True)
        neg = L.real_draw(C, tg, seed)
        g = S.comp_stats(P, C, neg, tg)
        sh = neg[~neg.is_nonveg]
        g['harm_SE'] = abs(sh.tcc.mean() - TRUE_HAB.tcc.mean()) / (TRUE_HAB.tcc.std()/np.sqrt(len(sh)))
        g['harm_pp'] = sh.tcc.mean() - TRUE_HAB.tcc.mean()
        acc.append(g)
    a = pd.DataFrame(acc)
    print(f"{keep:4.0%}   {a.harm_SE.min():10.1f}   {a.harm_pp.mean():+22.2f}  "
          f"{a.D1_nvexcess_max.max():3.0f} {a.D3_shortfall_max.max():3.0f} "
          f"{a.D5_hab_supply_min.min():9.3f}  {a.S1_ksneg_pooled.max():.4f}  "
          f"{a.S3_ksneghab_pooled.max():.4f}  {a.S4_ksneghab_region.max():.4f}  "
          f"{a.Q1_basis_tv_pool.max():.4f}  {a.Q2_smd_pool_max.max():6.2f}  "
          f"{a.Q6_wratio_min.min():.4f}  {a.Q7_species_tv_pool.max():.4f}", flush=True)
