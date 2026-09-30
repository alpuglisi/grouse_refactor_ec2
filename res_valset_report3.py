import pickle, numpy as np, pandas as pd
pd.set_option('display.width', 400); pd.set_option('display.max_columns', 100)
SP = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
res = pickle.load(open(SP + "/harm.pkl", "rb")); fair = res['fair (today)']
DET = ['moran_I', 'ks_blkproj_max', 'ks_proj_max', 'q30km_frac_zero', 'q30km_chi2_per_cell',
       'nn_train_med_km', 'ks_feat_max', 'ks_unmod_max', 'I7_worst_pp', 'I15_disp_pp', 'n_val_blocks']
HARM = [c for c in fair.columns if c.startswith('zbias_')] + ['ksu_slope', 'ksu_lidar_elev', 'ksu_spatial_density']
print("=== FAIR ENVELOPE (%d seeds) ===" % len(fair))
env = pd.DataFrame({'min': fair.min(), 'p1': fair.quantile(.01), 'med': fair.median(),
                    'p99': fair.quantile(.99), 'max': fair.max(),
                    'absmax': fair.abs().max()})
print(env.loc[DET + HARM].round(4).to_string())
atk = [k for k in res if k.startswith('ATK')]
print("\n=== DETECTORS: median [worst-case over 20 seeds, i.e. the value closest to fair] ===")
T = pd.DataFrame({k: res[k][DET].median() for k in atk}, index=DET)
T.insert(0, 'fair_p99', fair[DET].quantile(.99)); T.insert(0, 'fair_med', fair[DET].median())
print(T.round(3).to_string())
print("\n=== DETECTORS: attack MINIMUM over 20 seeds vs fair MAXIMUM (the honest gate test) ===")
M = pd.DataFrame({k: res[k][DET].min() for k in atk}, index=DET)
M.insert(0, 'fair_max', fair[DET].max())
print(M.round(3).to_string())
print("\n=== HARM: bias of the val-set mean of each field, in iid-SE units (mean over seeds) ===")
H = pd.DataFrame({k: res[k][HARM].mean() for k in atk}, index=HARM)
H.insert(0, 'fair_mean', fair[HARM].mean()); H.insert(1, 'fair_sd', fair[HARM].std())
print(H.round(2).to_string())
print("\n=== HARM: |bias| averaged over seeds (systematic) and SD across seeds (variance) ===")
zb = [c for c in HARM if c.startswith('zbias_')]
rows = {}
for k in ['fair (today)'] + atk:
    d = res[k][zb]
    rows[k] = pd.Series({'mean|z| (systematic bias)': d.abs().mean().mean(),
                         'max|mean z| (worst field)': d.mean().abs().max(),
                         'SD of z across seeds (design effect)': d.std().mean(),
                         'RMS z': np.sqrt((d ** 2).mean().mean())})
print(pd.DataFrame(rows).T.round(2).to_string())
