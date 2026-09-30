"""Candidate detection statistics for a spatially-biased validation block
draw (CR-0007 I14/I15 hole).  Fair-draw envelope over >=60 seeds vs a
battery of distinct defective draws.  READ-ONLY."""
import os, sys, itertools, math, json
import numpy as np, pandas as pd
from scipy.spatial import cKDTree
from scipy.stats import ks_2samp
os.chdir("/home/ec2-user/grouse2"); sys.path.insert(0, ".")
SP = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
R = ["ME", "NH", "VT"]; SZ = 3000.0; VF = 0.2
base = pd.read_csv(SP + "/base.csv")
feat = pd.read_csv(SP + "/feat.csv")
CONT = list(feat.columns)
CATS = ["evt", "evh", "evc", "sclass", "fdist", "evt_phys", "evt_group"]
for c in CONT: base[c] = feat[c].values
blk = base.blk.values
blocks = pd.Index(sorted(base.blk.unique()))
bi = pd.Series(np.arange(len(blocks)), index=blocks)          # block -> idx
base['bidx'] = bi[blk].values
bcount = np.bincount(base.bidx, minlength=len(blocks))        # records per block
bxy = np.array([[int(b.split('_')[0]), int(b.split('_')[1])] for b in blocks])
bcen = bxy * SZ + SZ / 2.0                                    # block centres (m)
# block -> region (plurality of its records); 4 of 3861 blocks are mixed-state
breg = base.groupby('bidx')['state'].agg(lambda s: s.value_counts().idxmax()).reindex(range(len(blocks))).values
rec_state = base.state.values
TOT = len(base); NREG = {r: int((rec_state == r).sum()) for r in R}

# ---------- fixed spatial structures (block set never changes) ----------
knn = cKDTree(bcen).query(bcen, k=9)[1][:, 1:]                 # 8 nearest blocks
lat = {(int(x), int(y)): i for i, (x, y) in enumerate(bxy)}
adj = [[] for _ in blocks]
for i, (x, y) in enumerate(bxy):
    for dx, dy in itertools.product((-1, 0, 1), repeat=2):
        if dx == dy == 0: continue
        j = lat.get((x + dx, y + dy))
        if j is not None: adj[i].append(j)
adj_pairs = np.array([(i, j) for i, nb in enumerate(adj) for j in nb if j > i])
def coarse(cells):    # coarse-cell id per record, cells = n blocks per side
    return (base.bx // cells).astype(str) + "_" + (base.by // cells).astype(str)
CG = {c: coarse(c).values for c in (4, 10)}                    # 12 km, 30 km

# ---------- draws: return a set of block indices ----------
def d_fair(seed, vf=VF):
    bc = pd.Series(bcount, index=range(len(blocks))).sort_values(ascending=False)
    order = bc.sample(frac=1, random_state=seed).index.tolist()
    t = int(round(vf * TOT)); vb = set(); run = 0
    for b in order:
        if run >= t: break
        vb.add(b); run += bcount[b]
    return vb

def _perregion_eligible(seed, key, frac=0.5, hi=True, vf=VF):
    """per region: draw val blocks uniformly at random from the `frac`
    fraction of that region's blocks with highest (or lowest) `key`."""
    rng = np.random.default_rng(seed); vb = set()
    for r in R:
        idx = np.where(breg == r)[0]
        k = key[idx]
        cut = np.quantile(k, 1 - frac if hi else frac)
        elig = idx[k >= cut] if hi else idx[k <= cut]
        elig = rng.permutation(elig)
        t = int(round(vf * NREG[r])); run = 0
        for b in elig:
            if run >= t: break
            vb.add(int(b)); run += bcount[b]
    return vb

bmeanfeat = {c: base.groupby('bidx')[c].mean().reindex(range(len(blocks))).values for c in CONT}
d_east  = lambda s: _perregion_eligible(s, bxy[:, 0].astype(float), 0.5, True)
d_east75= lambda s: _perregion_eligible(s, bxy[:, 0].astype(float), 0.75, True)
d_north = lambda s: _perregion_eligible(s, bxy[:, 1].astype(float), 0.5, True)
d_hitcc = lambda s: _perregion_eligible(s, bmeanfeat['tcc'], 0.5, True)
d_loroad= lambda s: _perregion_eligible(s, bmeanfeat['road_dist'], 0.5, False)
d_hiqmd = lambda s: _perregion_eligible(s, bmeanfeat['qmd'], 0.5, True)

def d_east_local(seed, cells=10, vf=VF):
    """the I10-style rescaling: eastern half of each 30 km superblock."""
    rng = np.random.default_rng(seed); vb = set()
    sup = (bxy[:, 0] // cells) * 10000 + (bxy[:, 1] // cells)
    key = np.zeros(len(blocks))
    for s in np.unique(sup):
        m = sup == s
        key[m] = (bxy[m, 0] >= np.median(bxy[m, 0])).astype(float)
    for r in R:
        idx = np.where(breg == r)[0]
        elig = rng.permutation(idx[key[idx] > 0])
        t = int(round(vf * NREG[r])); run = 0
        for b in elig:
            if run >= t: break
            vb.add(int(b)); run += bcount[b]
    return vb

def d_onereg(seed, vf=VF):
    """pooled 20% of records, all val blocks inside ME."""
    rng = np.random.default_rng(seed)
    elig = rng.permutation(np.where(breg == "ME")[0])
    t = int(round(vf * TOT)); vb = set(); run = 0
    for b in elig:
        if run >= t: break
        vb.add(int(b)); run += bcount[b]
    return vb

def _grow(seed, nseed_per_region, vf=VF):
    rng = np.random.default_rng(seed); vb = set()
    for r in R:
        idx = np.where(breg == r)[0]
        t = int(round(vf * NREG[r])); run = 0
        frontiers = [[int(b)] for b in rng.choice(idx, size=nseed_per_region, replace=False)]
        used = set()
        while run < t and any(frontiers):
            for fr in frontiers:
                if run >= t: break
                while fr:
                    b = fr.pop(0)
                    if b in used or breg[b] != r: continue
                    used.add(b); vb.add(b); run += bcount[b]
                    fr.extend([j for j in adj[b] if j not in used and breg[j] == r])
                    break
            if not any(frontiers): break
    return vb
d_clust1 = lambda s: _grow(s, 1)
d_clust10 = lambda s: _grow(s, 10)
d_clust40 = lambda s: _grow(s, 40)

def d_dense(seed, vf=VF):                     # the I14 attack (no shuffle)
    order = pd.Series(bcount).sort_values(ascending=False).index.tolist()
    t = int(round(vf * TOT)); vb = set(); run = 0
    for b in order:
        if run >= t: break
        vb.add(int(b)); run += bcount[b]
    return vb

# record-level split for the no-blocking control is handled specially
def split_from_blocks(vb):
    v = np.zeros(len(blocks), dtype=bool); v[list(vb)] = True
    return v[base.bidx.values]                 # bool per record: is val

def split_random_points(seed, vf=VF):
    rng = np.random.default_rng(seed)
    m = np.zeros(TOT, dtype=bool)
    m[rng.choice(TOT, size=int(round(vf * TOT)), replace=False)] = True
    return m

# ---------- statistics on a record-level boolean val mask ----------
x, y = base.x_5070.values, base.y_5070.values
def mx(a):
    a=np.asarray(a,dtype=float)
    return float(np.nanmax(a)) if np.any(np.isfinite(a)) else np.nan

def stats(isval):
    S = {}
    v, t = isval, ~isval
    S['val_frac_pp'] = 100 * v.mean()
    # existing CR gates
    S['I7_worst_pp'] = max(abs(100 * v[rec_state == r].mean() - 100 * VF) for r in R)
    bv = np.unique(base.bidx.values[v]); S['n_val_blocks'] = len(bv)
    S['I15_disp_pp'] = abs(100 * len(bv) / len(blocks) - 100 * v.mean())
    S['rec_per_valblk'] = v.sum() / max(len(bv), 1)
    both = base.groupby('bidx')['blk'].count().index[[
        len(set(isval[base.bidx.values == b])) > 1 for b in range(len(blocks))]] if False else None
    # blocks holding both splits (I2/(c)) -- vectorised
    agg = pd.DataFrame({'b': base.bidx.values, 'v': isval}).groupby('b')['v'].agg(['min', 'max'])
    S['blocks_both_splits'] = int((agg['min'] != agg['max']).sum())
    # coordinate distribution, per region then max
    ksx, ksy, ksp, msx, msy, msxn = [], [], [], [], [], []
    angs = np.arange(8) * np.pi / 8
    for r in R:
        m = rec_state == r
        xv, xt = x[m & v], x[m & t]; yv, yt = y[m & v], y[m & t]
        ksx.append(ks_2samp(xv, xt).statistic); ksy.append(ks_2samp(yv, yt).statistic)
        iqx = np.subtract(*np.percentile(x[m], [75, 25])); iqy = np.subtract(*np.percentile(y[m], [75, 25]))
        msx.append(abs(np.median(xv) - np.median(xt)) / 1000.0)
        msy.append(abs(np.median(yv) - np.median(yt)) / 1000.0)
        msxn.append(max(abs(np.median(xv) - np.median(xt)) / iqx, abs(np.median(yv) - np.median(yt)) / iqy))
        for a in angs:
            p = x[m] * np.cos(a) + y[m] * np.sin(a)
            ksp.append(ks_2samp(p[v[m]], p[t[m]]).statistic)
    S['ks_x_max'] = mx(ksx); S['ks_y_max'] = mx(ksy)
    S['ks_proj_max'] = mx(ksp)
    S['medshift_km_max'] = mx(msx+msy); S['medshift_iqr_max'] = mx(msxn)
    # block-level coordinate KS (occupancy-free)
    isv_b = np.zeros(len(blocks), dtype=bool); isv_b[bv] = True
    kb = []
    for r in R:
        mb = breg == r
        for a in angs:
            p = bcen[mb, 0] * np.cos(a) + bcen[mb, 1] * np.sin(a)
            if isv_b[mb].sum() > 4: kb.append(ks_2samp(p[isv_b[mb]], p[~isv_b[mb]]).statistic)
    S['ks_blkproj_max'] = max(kb) if kb else np.nan
    # Moran's I of the val indicator over occupied blocks (8-NN, row-standardised)
    z = isv_b.astype(float) - isv_b.mean()
    S['moran_I'] = float((z[:, None] * z[knn]).sum() / (len(blocks) * (z ** 2).sum() / len(blocks)) / 8.0) \
        if (z ** 2).sum() > 0 else np.nan
    # queen-adjacency join count: observed val-val pairs / expected
    a_, b_ = adj_pairs[:, 0], adj_pairs[:, 1]
    p = isv_b.mean()
    S['joincount_ratio'] = float((isv_b[a_] & isv_b[b_]).mean() / max(p * p, 1e-12))
    # coarse-grid quadrat deviation of the val RECORD fraction
    for cells, name in ((4, 'q12km'), (10, 'q30km')):
        g = pd.DataFrame({'c': CG[cells], 'v': isval}).groupby('c')['v'].agg(['mean', 'size'])
        g = g[g['size'] >= 20]
        S[name + '_maxdev_pp'] = float((100 * (g['mean'] - VF)).abs().max())
        S[name + '_chi2_per_cell'] = float((((g['mean'] - VF) ** 2 / (VF * (1 - VF) / g['size']))).mean())
        S[name + '_frac_zero'] = float((g['mean'] == 0).mean())
    # feature-space divergence
    kf = {}
    for c in CONT:
        vals = base[c].values; ok = np.isfinite(vals)
        kf[c] = ks_2samp(vals[ok & v], vals[ok & t]).statistic
    S['ks_feat_max'] = max(kf.values()); S['ks_feat_arg'] = max(kf, key=kf.get)
    S.update({'ksf_' + c: kf[c] for c in CONT})
    kfr = []
    for r in R:
        m = rec_state == r
        for c in CONT:
            vals = base[c].values
            kfr.append(ks_2samp(vals[m & v], vals[m & t]).statistic)
    S['ks_feat_reg_max'] = mx(kfr)
    tv = {}
    for c in CATS:
        a1 = base[c].values[v]; a2 = base[c].values[t]
        cats = pd.Index(pd.unique(base[c].values))
        p1 = pd.Series(a1).value_counts(normalize=True).reindex(cats).fillna(0)
        p2 = pd.Series(a2).value_counts(normalize=True).reindex(cats).fillna(0)
        tv[c] = 0.5 * float((p1 - p2).abs().sum())
    S['tvd_cat_max'] = max(tv.values()); S['tvd_cat_arg'] = max(tv, key=tv.get)
    S['tvd_evt'] = tv['evt']
    # separation: val record -> nearest train record
    tr = cKDTree(np.c_[x[t], y[t]])
    d = tr.query(np.c_[x[v], y[v]], k=1)[0]
    S['nn_train_med_km'] = float(np.median(d) / 1000); S['nn_train_p10_km'] = float(np.percentile(d, 10) / 1000)
    return S

DRAWS = {
    'east(half)': d_east, 'east(75%)': d_east75, 'north(half)': d_north,
    'hi_tcc': d_hitcc, 'lo_road_dist': d_loroad, 'hi_qmd': d_hiqmd,
    'east_local_30km': d_east_local, 'one_region(ME)': d_onereg,
    'cluster_1/region': d_clust1, 'cluster_10/region': d_clust10,
    'cluster_40/region': d_clust40, 'dense_first(I14)': d_dense,
}
SEEDS = list(range(1, 61)) + [101, 202, 303, 404]   # 64 seeds
rows = {}
print("computing fair envelope over", len(SEEDS), "seeds ...", flush=True)
fair = pd.DataFrame([stats(split_from_blocks(d_fair(s))) for s in SEEDS])
rows['fair'] = fair
print("no-blocking random-point control ...", flush=True)
rows['randpoint'] = pd.DataFrame([stats(split_random_points(s)) for s in SEEDS[:10]])
for name, fn in DRAWS.items():
    print("attack:", name, flush=True)
    sds = SEEDS[:10] if name != 'dense_first(I14)' else [42]
    rows[name] = pd.DataFrame([stats(split_from_blocks(fn(s))) for s in sds])
import pickle
pickle.dump(rows, open(SP + "/rows.pkl", "wb"))
print("saved rows.pkl")
