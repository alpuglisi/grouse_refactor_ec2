import pickle, numpy as np, pandas as pd
pd.set_option('display.width', 300); pd.set_option('display.max_columns', 80)
SP = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
res = pickle.load(open(SP + "/designs.pkl", "rb"))
KEY = ['val_frac_pp', 'I7_worst_pp', 'n_val_blocks', 'I15_disp_pp', 'rec_per_valblk',
       'blocks_both_splits', 'n_val_within_3km_of_train', 'n_val_within_30m_of_train',
       'nn_train_med_km', 'nn_train_p10_km', 'moran_I', 'ks_proj_max', 'ks_blkproj_max',
       'q30km_frac_zero', 'q30km_chi2_per_cell', 'q12km_chi2_per_cell',
       'ks_feat_max', 'ks_feat_reg_max', 'ks_unmod_max', 'ks_unmod_reg_max',
       'ksu_slope', 'ksu_lidar_elev', 'ksu_spatial_density',
       'ksu_slope_reg', 'ksu_lidar_elev_reg', 'ksu_spatial_density_reg']
def summ(df, q):
    return pd.Series({k: df[k].quantile(q) if k in df else np.nan for k in KEY})
out = {}
for nm, df in res.items():
    out[nm + ' med'] = summ(df, .5)
    out[nm + ' p99' if nm.startswith(('A', 'B', 'C', 'D')) else nm + ' min'] = \
        summ(df, .99) if nm.startswith(('A', 'B', 'C', 'D')) else summ(df, 0.0)
T = pd.DataFrame(out)
print("=== designs: median and p99 over 64 seeds | attacks: median and MIN over 12 seeds ===")
print(T.round(3).to_string())
