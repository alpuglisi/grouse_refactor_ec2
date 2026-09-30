import pickle, numpy as np, pandas as pd
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 60)
SP = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
rows = pickle.load(open(SP + "/rows.pkl", "rb"))
fair = rows['fair']
NUM = [c for c in fair.columns if not str(fair[c].dtype).startswith('object') and c not in ('ks_feat_arg','tvd_cat_arg')]
q = pd.DataFrame({'min': fair[NUM].min(), 'p1': fair[NUM].quantile(.01), 'med': fair[NUM].median(),
                  'p99': fair[NUM].quantile(.99), 'max': fair[NUM].max()})
print("=== FAIR-DRAW ENVELOPE, %d seeds ===" % len(fair))
print(q.round(4).to_string())
print()
order = ['east(half)', 'east(75%)', 'north(half)', 'one_region(ME)', 'hi_tcc', 'lo_road_dist',
         'hi_qmd', 'cluster_1/region', 'cluster_10/region', 'cluster_40/region',
         'east_local_30km', 'dense_first(I14)', 'randpoint']
KEY = ['I7_worst_pp', 'I15_disp_pp', 'rec_per_valblk', 'blocks_both_splits', 'ks_proj_max',
       'ks_blkproj_max', 'ks_x_max', 'ks_y_max', 'medshift_km_max', 'medshift_iqr_max',
       'moran_I', 'joincount_ratio', 'q30km_maxdev_pp', 'q30km_chi2_per_cell', 'q30km_frac_zero',
       'q12km_chi2_per_cell', 'ks_feat_max', 'ks_feat_reg_max', 'tvd_cat_max', 'tvd_evt',
       'nn_train_med_km', 'nn_train_p10_km']
tab = pd.DataFrame({k: [rows[k][c].median() for c in KEY] for k in order if k in rows}, index=KEY)
tab.insert(0, 'fair_p99', [fair[c].quantile(.99) for c in KEY])
tab.insert(0, 'fair_med', [fair[c].median() for c in KEY])
print("=== MEDIAN VALUE UNDER EACH DEFECTIVE DRAW (10 seeds each; dense=1) ===")
print(tab.round(3).to_string())
print()
print("=== SEPARATION: (attack median) / (fair p99), ratio>1 means detectable ===")
sep = tab[[c for c in tab.columns if c not in ('fair_med', 'fair_p99')]].div(tab['fair_p99'].replace(0, np.nan), axis=0)
print(sep.round(2).to_string())
print()
print("=== worst-of-10-seed MIN for each attack (weakest realisation) vs fair max ===")
mn = pd.DataFrame({k: [rows[k][c].min() for c in KEY] for k in order if k in rows}, index=KEY)
mn.insert(0, 'fair_max', [fair[c].max() for c in KEY])
print(mn.round(3).to_string())
print()
print("=== which feature moves most ===")
for k in order:
    if k in rows:
        print(f"{k:20s} ks_feat_arg={rows[k]['ks_feat_arg'].mode()[0]:11s} tvd_cat_arg={rows[k]['tvd_cat_arg'].mode()[0]}")
print()
ks_cols = [c for c in fair.columns if c.startswith('ksf_')]
cmp = pd.DataFrame({k: rows[k][ks_cols].median() for k in order if k in rows})
cmp.insert(0, 'fair_p99', fair[ks_cols].quantile(.99)); cmp.insert(0, 'fair_med', fair[ks_cols].median())
print("=== per-feature KS (val vs train), pooled ===")
print(cmp.round(3).to_string())
