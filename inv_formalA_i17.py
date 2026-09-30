"""I17 (ks_feat_max over continuous FEATURE_SPEC features) for the fair draw
and for ATTACK C, measured on the real rasters in each region's own local
Albers CRS.  READ-ONLY."""
import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer
from scipy.stats import ks_2samp

from inv_formalA_harness import R, BS, SEED, val_blocks_fair, hash_split

SCR = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
pos = pd.read_pickle(f"{SCR}/pos.pkl").copy()
cand = pd.read_pickle(f"{SCR}/cand.pkl").copy()
CONT = ["ch", "cc", "tcc", "road_dist", "tsd", "balive", "tpa_live", "qmd", "carbon_dwn"]
VINTAGE = 2022

_tf = {}
for r in R:
    with rasterio.open(f"data/landfire/{r}_{VINTAGE}_road_dist.tif") as s:
        _tf[r] = Transformer.from_crs("EPSG:4326", s.crs, always_xy=True)


def sample_feats(df):
    vals = {f: np.full(len(df), np.nan) for f in CONT}
    for r in R:
        m = (df.state.values == r)
        if not m.any():
            continue
        xs, ys = _tf[r].transform(df.loc[m, 'longitude'].values,
                                  df.loc[m, 'latitude'].values)
        pts = list(zip(xs, ys))
        for f in CONT:
            with rasterio.open(f"data/landfire/{r}_{VINTAGE}_{f}.tif") as src:
                v = np.array([x[0] for x in src.sample(pts)], dtype=float)
                v[v <= -9990] = np.nan
                vals[f][m] = v
    return pd.DataFrame(vals, index=range(len(df)))


def ksmax(df, verbose=False):
    F = sample_feats(df)
    va = (df.split == 'val').values
    res = {}
    for f in CONT:
        a = F.loc[va, f].dropna()
        b = F.loc[~va, f].dropna()
        res[f] = ks_2samp(a, b).statistic if (len(a) > 20 and len(b) > 20) else np.nan
    if verbose:
        print("      " + "  ".join(f"{k}={v:.3f}" for k, v in res.items()))
    k = max(res, key=lambda x: (res[x] if res[x] == res[x] else -1))
    return res[k], k


vb = val_blocks_fair(pos, SEED)
pos['split'] = np.where(pos['blk'].isin(vb), 'val', 'train')
pb = set(pos['blk'].unique())
bt = {b: ('val' if b in vb else 'train') for b in pb}
gvf = len(vb) / len(pb)
targets = {(r, s): int(((pos.state == r) & (pos.split == s)).sum())
           for r in R for s in ('train', 'val')}
cand['bx'] = np.floor(cand.x_5070.values / BS).astype(np.int64)
free = cand.loc[~cand['blk'].isin(pb), ['blk', 'bx']].drop_duplicates('blk')
atk = set(free.sort_values('bx', ascending=False).blk.values[:int(round(gvf*len(free)))])


def assign(mode):
    return np.array([bt[b] if b in bt else
                     (hash_split(b, gvf, SEED) if mode == 'fair'
                      else ('val' if b in atk else 'train')) for b in cand['blk']])


def draw(ns, seed=0):
    rng = np.random.default_rng(seed)
    out = []
    for (r, s), n in targets.items():
        pool = cand[(cand.state.values == r) & (ns == s)].assign(split=s)
        out.append(pool.iloc[rng.choice(len(pool), size=min(n, len(pool)), replace=False)])
    return pd.concat(out, ignore_index=True)


for lbl, mode in (("FAIR", 'fair'), ("ATTACK C (eastern-half of positive-free blocks)", 'atk')):
    neg = draw(assign(mode))
    rec = pd.concat([pos.assign(cls='pos'), neg.assign(cls='neg')], ignore_index=True)
    print(f"--- {lbl} ---   val-neg minus train-neg mean x_5070 "
          f"{(neg[neg.split=='val'].x_5070.mean()-neg[neg.split=='train'].x_5070.mean())/1000:+.1f} km")
    for tag, sub in (("pos only", pos), ("pooled", rec), ("neg only", neg)):
        b, w = ksmax(sub, verbose=True)
        print(f"   I17 [{tag:8}] ks_feat_max {b:.4f} ({w})   gate <= 0.095")
