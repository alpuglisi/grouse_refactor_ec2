"""Phase 3: correct per-region half-plane attacks + HARM quantification.
For a spatially smooth field q, how far is the validation-set mean of q from
the population mean (bias), and how variable is it across seeds (variance)?
Expressed in units of the i.i.d. standard error popSD/sqrt(n_val) -- i.e. a
survey design effect and a bias-to-noise ratio.  READ-ONLY."""
import os, sys, itertools, pickle
import numpy as np, pandas as pd
from scipy.spatial import cKDTree
from scipy.stats import ks_2samp
os.chdir("/home/ec2-user/grouse2"); sys.path.insert(0, ".")
SP = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
R = ["ME", "NH", "VT"]; SZ = 3000.0; VF = 0.2
base = pd.read_csv(SP + "/base.csv"); feat = pd.read_csv(SP + "/feat.csv"); unmod = pd.read_csv(SP + "/unmod.csv")
CONT = list(feat.columns); UNMOD = ["slope", "lidar_elev", "spatial_density"]
for c in CONT: base[c] = feat[c].values
for c in UNMOD: base[c] = unmod[c].values
blocks = pd.Index(sorted(base.blk.unique())); NB = len(blocks)
bi = pd.Series(np.arange(NB), index=blocks); base['bidx'] = bi[base.blk.values].values
bcount = np.bincount(base.bidx, minlength=NB)
bxy = np.array([[int(b.split('_')[0]), int(b.split('_')[1])] for b in blocks]); bcen = bxy * SZ + SZ / 2
breg = base.groupby('bidx')['state'].agg(lambda s: s.value_counts().idxmax()).reindex(range(NB)).values
rec_state = base.state.values; TOT = len(base); NREG = {r: int((rec_state == r).sum()) for r in R}
knn = cKDTree(bcen).query(bcen, k=9)[1][:, 1:]
adjlat = {(int(a), int(b)): i for i, (a, b) in enumerate(bxy)}
adj = [[j for j in (adjlat.get((x + dx, y + dy)) for dx, dy in itertools.product((-1, 0, 1), repeat=2)
        if (dx, dy) != (0, 0)) if j is not None] for x, y in bxy]
x, y = base.x_5070.values, base.y_5070.values
bmean = {c: base.groupby('bidx')[c].mean().reindex(range(NB)).values for c in CONT + UNMOD}

def tomask(vb):
    v = np.zeros(NB, bool); v[list(vb)] = True; return v[base.bidx.values]

def fair(seed, vf=VF):
    bc = pd.Series(bcount, index=range(NB)).sort_values(ascending=False)
    order = bc.sample(frac=1, random_state=seed).index.tolist()
    t = int(round(vf * TOT)); vb = set(); run = 0
    for b in order:
        if run >= t: break
        vb.add(b); run += bcount[b]
    return vb

def half(seed, axis=0, hi=True, cells=None, vf=VF):
    """per region, val blocks drawn uniformly from the half of that region's
    blocks on one side of the median of `axis`; if cells is given the median
    is taken WITHIN each cells-block superblock."""
    rng = np.random.default_rng(seed); vb = set()
    key = np.zeros(NB, bool)
    if cells is None:
        for r in R:
            m = breg == r
            key[m] = (bxy[m, axis] >= np.median(bxy[m, axis])) if hi else (bxy[m, axis] <= np.median(bxy[m, axis]))
    else:
        c = (bxy[:, 0] // cells) * 100000 + (bxy[:, 1] // cells)
        for s in np.unique(c):
            m = c == s
            key[m] = (bxy[m, axis] >= np.median(bxy[m, axis])) if hi else (bxy[m, axis] <= np.median(bxy[m, axis]))
    for r in R:
        idx = np.where((breg == r) & key)[0]
        t = int(round(vf * NREG[r])); run = 0
        for b in rng.permutation(idx):
            if run >= t: break
            vb.add(int(b)); run += bcount[b]
    return vb

def featbias(seed, col, hi=True, vf=VF):
    rng = np.random.default_rng(seed); vb = set()
    for r in R:
        idx = np.where(breg == r)[0]; k = bmean[col][idx]
        cut = np.nanmedian(k)
        elig = idx[k >= cut] if hi else idx[k <= cut]
        t = int(round(vf * NREG[r])); run = 0
        for b in rng.permutation(elig):
            if run >= t: break
            vb.add(int(b)); run += bcount[b]
    return vb

def grow(seed, nblob, vf=VF):
    rng = np.random.default_rng(seed); vb = set()
    for r in R:
        idx = np.where(breg == r)[0]; t = int(round(vf * NREG[r])); run = 0
        used = set(); seeds = list(rng.permutation(idx)); blobs = []
        while run < t:
            while len(blobs) < nblob and seeds:
                s0 = int(seeds.pop())
                if s0 not in used: blobs.append([s0])
            if not blobs: break
            prog = False
            for fr in list(blobs):
                if run >= t: break
                while fr:
                    b = fr.pop(0)
                    if b in used or breg[b] != r: continue
                    used.add(b); vb.add(b); run += bcount[b]; prog = True
                    fr.extend([j for j in adj[b] if j not in used and breg[j] == r]); break
                if not fr: blobs.remove(fr)
            if not prog and not seeds: break
    return vb

def dense(seed, vf=VF):
    order = pd.Series(bcount).sort_values(ascending=False).index.tolist()
    t = int(round(vf * TOT)); vb = set(); run = 0
    for b in order:
        if run >= t: break
        vb.add(int(b)); run += bcount[b]
    return vb

ANG = np.arange(8) * np.pi / 8
mx = lambda a: float(np.nanmax(np.asarray(a, float))) if np.any(np.isfinite(np.asarray(a, float))) else np.nan
QFIELD = ["slope", "lidar_elev", "spatial_density", "tcc", "road_dist", "qmd"]
def stats(isval):
    S = {}; v = isval; t = ~isval
    S['val_frac_pp'] = 100 * v.mean()
    S['I7_worst_pp'] = mx([abs(100 * v[rec_state == r].mean() - 20) for r in R])
    bv = np.unique(base.bidx.values[v]); S['n_val_blocks'] = len(bv)
    S['I15_disp_pp'] = abs(100 * len(bv) / NB - 100 * v.mean())
    isv_b = np.zeros(NB, bool); isv_b[bv] = True
    z = isv_b.astype(float) - isv_b.mean()
    S['moran_I'] = float((z[:, None] * z[knn]).sum() / (z ** 2).sum() / 8.0)
    ksp = []; kb = []
    for r in R:
        m = rec_state == r; mb = breg == r
        for a in ANG:
            p = x[m] * np.cos(a) + y[m] * np.sin(a)
            ksp.append(ks_2samp(p[v[m]], p[t[m]]).statistic)
            if 4 < isv_b[mb].sum() < mb.sum() - 4:
                pb = bcen[mb, 0] * np.cos(a) + bcen[mb, 1] * np.sin(a)
                kb.append(ks_2samp(pb[isv_b[mb]], pb[~isv_b[mb]]).statistic)
    S['ks_proj_max'] = mx(ksp); S['ks_blkproj_max'] = mx(kb)
    rc = (base.bx.values // 10) * 100000 + (base.by.values // 10)
    g = pd.DataFrame({'c': rc, 'v': isval}).groupby('c')['v'].agg(['mean', 'size']); g = g[g['size'] >= 20]
    S['q30km_frac_zero'] = float((g['mean'] == 0).mean())
    S['q30km_chi2_per_cell'] = float(((g['mean'] - VF) ** 2 / (VF * .8 / g['size'])).mean())
    tr = cKDTree(np.c_[x[t], y[t]]); d = tr.query(np.c_[x[v], y[v]], k=1)[0]
    S['nn_train_med_km'] = float(np.median(d) / 1000)
    S['ks_feat_max'] = mx([ks_2samp(base[c].values[v], base[c].values[t]).statistic for c in CONT])
    ku = {}
    for c in UNMOD:
        vv = base[c].values; ok = np.isfinite(vv)
        ku[c] = ks_2samp(vv[ok & v], vv[ok & t]).statistic
    S['ks_unmod_max'] = mx(list(ku.values())); S.update({'ksu_' + k: w for k, w in ku.items()})
    # HARM: val-set mean of a smooth field vs population mean, in iid-SE units
    for c in QFIELD:
        vv = base[c].values; ok = np.isfinite(vv)
        pop = vv[ok].mean(); se = vv[ok].std(ddof=1) / np.sqrt((ok & v).sum())
        S['zbias_' + c] = float((vv[ok & v].mean() - pop) / se)
    return S

SEEDS = list(range(1, 61)) + [101, 202, 303, 404]
DRAWS = {
    'fair (today)':            lambda s: tomask(fair(s)),
    'ATK east half/region':    lambda s: tomask(half(s, 0, True)),
    'ATK north half/region':   lambda s: tomask(half(s, 1, True)),
    'ATK east half of 60km':   lambda s: tomask(half(s, 0, True, 20)),
    'ATK east half of 30km':   lambda s: tomask(half(s, 0, True, 10)),
    'ATK east half of 12km':   lambda s: tomask(half(s, 0, True, 4)),
    'ATK hi tcc':              lambda s: tomask(featbias(s, 'tcc', True)),
    'ATK lo road_dist':        lambda s: tomask(featbias(s, 'road_dist', False)),
    'ATK hi elev(unmodelled)': lambda s: tomask(featbias(s, 'lidar_elev', True)),
    'ATK cluster 1/region':    lambda s: tomask(grow(s, 1)),
    'ATK cluster 10/region':   lambda s: tomask(grow(s, 10)),
    'ATK cluster 50/region':   lambda s: tomask(grow(s, 50)),
    'ATK dense-first (I14)':   lambda s: tomask(dense(s)),
}
res = {}
for nm, fn in DRAWS.items():
    n = len(SEEDS) if nm == 'fair (today)' else 20
    print(nm, flush=True)
    res[nm] = pd.DataFrame([stats(fn(s)) for s in SEEDS[:n]])
pickle.dump(res, open(SP + "/harm.pkl", "wb"))
print("saved")
