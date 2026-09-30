import pickle, numpy as np, pandas as pd
pd.set_option('display.width', 400); pd.set_option('display.max_columns', 100)
SP = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
A = pickle.load(open(SP + "/calib.pkl", "rb")); F = A['fair x1000']
C = ['moran_k4', 'moran_k8', 'moran_k16', 'moran_k32', 'moran_k64', 'moran_z_k8',
     'ks_blkproj_max', 'q30km_frac_zero', 'q30km_chi2', 'nn_train_med_km',
     'frac_val_within_RF', 'frac_val_within_halfRF', 'n_val_blocks', 'val_frac_pp']
print("=== FAIR DESIGN, 1000 seeds: quantiles ===")
Q = pd.DataFrame({q: F[C].quantile(q) for q in [0, .01, .05, .5, .95, .99, .999, 1]})
Q.columns = ['min', 'p1', 'p5', 'med', 'p95', 'p99', 'p99.9', 'max']
print(Q.round(4).to_string())
print()
names = [k for k in A if k != 'fair x1000']
atk = [k for k in names if not k.startswith('DESIGN')]
des = [k for k in names if k.startswith('DESIGN')]
print("=== ATTACKS: min over seeds (the value closest to fair) ===")
T = pd.DataFrame({k: A[k][C].min() for k in atk}, index=C)
T.insert(0, 'fair_max', F[C].max()); T.insert(1, 'fair_p999', F[C].quantile(.999))
print(T.round(3).to_string())
print("\n=== ATTACKS: separation = (attack min) / (fair p99.9), for the upper-tail stats ===")
UP = ['moran_k4', 'moran_k8', 'moran_k16', 'moran_k32', 'moran_k64', 'ks_blkproj_max',
      'q30km_frac_zero', 'q30km_chi2']
S = pd.DataFrame({k: A[k][UP].min() / F[UP].quantile(.999) for k in atk}, index=UP)
print(S.round(2).to_string())
print("\n=== ALTERNATIVE DESIGNS: median / p99.9 over 100 seeds ===")
D = {}
for k in des:
    D[k + ' med'] = A[k][C].median(); D[k + ' max'] = A[k][C].max()
DD = pd.DataFrame(D); DD.insert(0, 'fair med', F[C].median()); DD.insert(1, 'fair max', F[C].max())
print(DD.round(4).to_string())
