"""ATTACK C, part 2.

(1) Show the same escape arises from a one-line PLAUSIBLE MISTAKE, not only an
    adversarial rule: with global block ids of the form "bx_by", iterating the
    positive-free blocks in SORTED ID ORDER and taking the first val_fraction
    of them is a geographic cut in x, because sorting the id sorts on bx.
(2) Score I17 (ks_feat_max over continuous FEATURE_SPEC features) both ways -
    positives-only and pooled - by actually sampling the rasters.

READ-ONLY: samples rasters, writes nothing.
"""
import numpy as np
import pandas as pd
import rasterio
from scipy.spatial import cKDTree
from scipy.stats import ks_2samp

from inv_formalA_harness import R, BS, SEED, blk, val_blocks_fair, hash_split

SCR = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
pos = pd.read_pickle(f"{SCR}/pos.pkl").copy()
cand = pd.read_pickle(f"{SCR}/cand.pkl").copy()

vb = val_blocks_fair(pos, SEED)
pos['split'] = np.where(pos['blk'].isin(vb), 'val', 'train')
posblocks = set(pos['blk'].unique())
blocktab = {b: ('val' if b in vb else 'train') for b in posblocks}
gvf = len(vb) / len(posblocks)
targets = {(r, s): int(((pos.state == r) & (pos.split == s)).sum())
           for r in R for s in ('train', 'val')}

free_ids = sorted(set(cand['blk']) - posblocks)          # int key == bx*1e5+by
n_val_free = int(round(gvf * len(free_ids)))
sorted_val = set(free_ids[:n_val_free])                   # "first 20 % by id"


def assign(mode):
    out = []
    for b in cand['blk']:
        if b in blocktab:
            out.append(blocktab[b])
        elif mode == 'fair':
            out.append(hash_split(b, gvf, SEED))
        else:
            out.append('val' if b in sorted_val else 'train')
    return np.array(out)


def draw(nsplit, seed=0):
    rng = np.random.default_rng(seed)
    out = []
    for (r, s), n in targets.items():
        pool = cand[(cand.state.values == r) & (nsplit == s)].assign(split=s)
        out.append(pool.iloc[rng.choice(len(pool), size=min(n, len(pool)), replace=False)])
    return pd.concat(out, ignore_index=True)


CONT = ["ch", "cc", "tcc", "road_dist", "tsd", "balive", "tpa_live", "qmd", "carbon_dwn"]
VINTAGE = 2022


def sample_feats(df):
    """Point-sample the 2022 vintage of each continuous FEATURE_SPEC raster."""
    vals = {f: np.full(len(df), np.nan) for f in CONT}
    for r in R:
        m = (df.state.values == r)
        if not m.any():
            continue
        pts = list(zip(df.loc[m, 'longitude'].values, df.loc[m, 'latitude'].values))
        for f in CONT:
            p = f"data/landfire/{r}_{VINTAGE}_{f}.tif"
            try:
                with rasterio.open(p) as src:
                    v = np.array([x[0] for x in src.sample(pts)], dtype=float)
                    v[v <= -9990] = np.nan
                    vals[f][m] = v
            except Exception as e:
                print(f"    (skip {p}: {e})")
    return pd.DataFrame(vals, index=df.index)


def ks_feat_max(df):
    F = sample_feats(df)
    best, who = 0.0, None
    for f in CONT:
        a = F.loc[(df.split == 'val').values, f].dropna()
        b = F.loc[(df.split == 'train').values, f].dropna()
        if len(a) > 20 and len(b) > 20:
            d = ks_2samp(a, b).statistic
            if d > best:
                best, who = d, f
    return best, who


for label, mode in (("FAIR (hash)", 'fair'),
                    ("MISTAKE (positive-free blocks split in sorted-block-id order)", 'sorted')):
    neg = draw(assign(mode))
    rec = pd.concat([pos.assign(cls='pos'), neg.assign(cls='neg')], ignore_index=True)
    print(f"\n########## {label} ##########")
    g = rec.groupby('blk')['split'].nunique()
    trb = set(rec.loc[rec.split == 'train', 'blk'])
    vn = rec[(rec.split == 'val') & (rec.cls == 'neg')]
    print(f"  I2 {int((g>1).sum())}   I3 {100*vn.blk.isin(trb).mean():.2f}%   I6 {len(pos)}")
    for tag, sub in (("positive-occupied", pos), ("all-record-occupied", rec)):
        bl = sub.drop_duplicates('blk')[['blk', 'split']].copy()
        XY = np.c_[(bl.blk // 100000 + .5) * BS, (bl.blk % 100000 + .5) * BS]
        y = (bl.split == 'val').values.astype(float)
        z = y - y.mean()
        for k in (4, 8):
            _, idx = cKDTree(XY).query(XY, k=k+1)
            I = (z[idx[:, 1:]].mean(axis=1) * z).sum() / (z**2).sum()
            print(f"  I16 [{tag:19}] k={k}  I={I:+.4f}")
    for tag, sub in (("pos only", pos), ("pooled", rec), ("neg only", neg)):
        t = sub[sub.split == 'train'][['x_5070', 'y_5070']].values
        v = sub[sub.split == 'val'][['x_5070', 'y_5070']].values
        d, _ = cKDTree(t).query(v, k=1)
        print(f"  I18 [{tag:8}] median val->nearest train {np.median(d)/1000:.3f} km")
    d, _ = cKDTree(neg[['x_5070', 'y_5070']].values).query(pos[['x_5070', 'y_5070']].values, k=1)
    print(f"  I19 {(d>1920).mean():.4f}")
    for tag, sub in (("pos only", pos), ("pooled", rec), ("neg only", neg)):
        b, who = ks_feat_max(sub)
        print(f"  I17 [{tag:8}] ks_feat_max {b:.3f} ({who})   gate <= 0.095")
    vx = neg[neg.split == 'val'].x_5070.mean()
    tx = neg[neg.split == 'train'].x_5070.mean()
    print(f"  HARM val-neg minus train-neg mean x_5070: {(vx-tx)/1000:+.1f} km   "
          f"KS(x) {ks_2samp(neg[neg.split=='val'].x_5070, neg[neg.split=='train'].x_5070).statistic:.3f}")
