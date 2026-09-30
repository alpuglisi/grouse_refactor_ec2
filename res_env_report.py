"""RESEARCH (read-only): quantile report for the faithful FAIR envelope and
every attack, on identical statistics."""
import sys
import numpy as np, pandas as pd
import res_env_core as K

SCR = K.SCR
F = pd.read_csv(f"{SCR}/res_fair_1000.csv")
QS = [0, 1, 5, 50, 95, 99, 99.9, 100]
STATS = (['I19_ME', 'I19_NH', 'I19_VT', 'I19_worst', 'I19_pooled']
         + ['med_ME', 'med_NH', 'med_VT', 'med_pooled']
         + ['I16b_pool_k4', 'I16b_pool_k8', 'I16b_sel_k4', 'I16b_sel_k8',
            'I16_pos_k4', 'I16_pos_k8']
         + ['I2', 'I3', 'I4_neg', 'I8_short', 'I8_exact']
         + ['I7neg_ME', 'I7neg_NH', 'I7neg_VT', 'I7neg_worst', 'I7neg_pooled']
         + ['I10_ME', 'I10_NH', 'I10_VT', 'I10_worst']
         + ['nv_share', 'nv_ME', 'nv_NH', 'nv_VT', 'nv_val', 'nv_train',
            'nv_valtrain_gap', 'wb_nonveg', 'wb_prop']
         + ['ksneg_max', 'kspos_max', 'gvf'])


def qrow(a):
    a = np.asarray(a, float)
    return [np.percentile(a, q) for q in QS] + [a.mean(), a.std()]


print(f"n seeds = {len(F)}")
print(f"{'stat':20} " + " ".join(f"{('p'+str(q)) if 0<q<100 else ('min' if q==0 else 'max'):>10}"
                                 for q in QS) + f"{'mean':>11}{'sd':>11}")
for s in STATS:
    print(f"{s:20} " + " ".join(f"{v:>10.5f}" for v in qrow(F[s])))

print("\n=== I16b nulls (mean / sd) and the implied one-sided z<=5.0 ceiling ===")
for key in ['I16b_pool_k4', 'I16b_pool_k8', 'I16b_sel_k4', 'I16b_sel_k8',
            'I16_pos_k4', 'I16_pos_k8']:
    m, sd = F[key].mean(), F[key].std()
    print(f"  {key:16} mean {m:+.6f}  sd {sd:.6f}  -> I <= {m+5*sd:.4f}"
          f"   max observed {F[key].max():+.4f} (z {(F[key].max()-m)/sd:+.2f})")
print(f"  block counts: pool-occupied {F.I16b_npool.iloc[0]:.0f}, "
      f"selected-record mean {F.I16b_nsel.mean():.0f} "
      f"[{F.I16b_nsel.min():.0f},{F.I16b_nsel.max():.0f}]")

try:
    A = pd.read_csv(f"{SCR}/res_attacks_40.csv")
except FileNotFoundError:
    sys.exit(0)
KEY = ['I19_worst', 'I19_ME', 'I19_NH', 'I19_VT', 'I19_pooled',
       'I16b_pool_k8', 'I16b_sel_k8', 'I16b_pool_k4', 'I16b_sel_k4',
       'ksneg_max', 'kspos_max', 'nv_share', 'nv_valtrain_gap',
       'I10_worst', 'I7neg_worst', 'I8_exact', 'I2', 'I3', 'I4_neg',
       'med_pooled', 'I16b_nsel']
print("\n=== ATTACKS (40 seeds each): min / median / max of each statistic ===")
for name, g in A.groupby('attack'):
    print(f"\n-- {name}   pool_n {g.pool_n.iloc[0]}  supply_ok "
          f"{g.supply_ok.mean():.2f}")
    for s in KEY:
        print(f"     {s:16} min {g[s].min():+.5f}  p50 {g[s].median():+.5f}  "
              f"max {g[s].max():+.5f}")
