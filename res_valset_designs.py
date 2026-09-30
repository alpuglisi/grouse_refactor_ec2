"""Phase 2: alternative DESIGNS (stratified block draws) vs alternative
GATES, plus harm proxies on UNMODELLED spatial covariates.  READ-ONLY."""
import os, sys, itertools, pickle
import numpy as np, pandas as pd
from scipy.spatial import cKDTree
from scipy.stats import ks_2samp
os.chdir("/home/ec2-user/grouse2"); sys.path.insert(0, ".")
SP = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
R = ["ME", "NH", "VT"]; SZ = 3000.0; VF = 0.2
base = pd.read_csv(SP + "/base.csv")
feat = pd.read_csv(SP + "/feat.csv"); unmod = pd.read_csv(SP + "/unmod.csv")
CONT = list(feat.columns)
UNMOD = ["slope", "lidar_elev", "spatial_density"]
for c in CONT: base[c] = feat[c].values
for c in UNMOD: base[c] = unmod[c].values
blocks = pd.Index(sorted(base.blk.unique())); NB = len(blocks)
bi = pd.Series(np.arange(NB), index=blocks); base['bidx'] = bi[base.blk.values].values
bcount = np.bincount(base.bidx, minlength=NB)
bxy = np.array([[int(b.split('_')[0]), int(b.split('_')[1])] for b in blocks])
bcen = bxy * SZ + SZ / 2.0
breg = base.groupby('bidx')['state'].agg(lambda s: s.value_counts().idxmax()).reindex(range(NB)).values
bzone = base.groupby('bidx')['spatial_zone'].agg(lambda s: s.value_counts().idxmax()).reindex(range(NB)).values
rec_state = base.state.values; TOT = len(base)
NREG = {r: int((rec_state == r).sum()) for r in R}
knn = cKDTree(bcen).query(bcen, k=9)[1][:, 1:]
lat = {(int(a), int(b)): i for i, (a, b) in enumerate(bxy)}
adj = [[j for j in (lat.get((x + dx, y + dy)) for dx, dy in itertools.product((-1, 0, 1), repeat=2)
        if (dx, dy) != (0, 0)) if j is not None] for x, y in bxy]
x, y = base.x_5070.values, base.y_5070.values
cell = lambda n: (bxy[:, 0] // n) * 100000 + (bxy[:, 1] // n)          # coarse cell per BLOCK
rcell = lambda n: (base.bx.values // n) * 100000 + (base.by.values // n)

# ---------------- generic stratified greedy block draw ----------------
def strat_draw(seed, strata, vf=VF, target='records'):
    """strata: array of length NB giving each BLOCK's stratum.  Within each
    stratum, shuffle blocks and take them until vf of that stratum's records
    are held.  strata=None -> one global stratum (= today's design)."""
    rng = np.random.default_rng(seed); vb = set()
    st = np.zeros(NB, dtype=int) if strata is None else pd.factorize(np.asarray(strata))[0]
    for s in np.unique(st):
        idx = np.where(st == s)[0]
        tot = bcount[idx].sum()
        t = int(round(vf * tot)); run = 0
        for b in rng.permutation(idx):
            if run >= t: break
            vb.add(int(b)); run += bcount[b]
    return vb

def fair_asis(seed, vf=VF):                 # the real prepare_training_data code path
    bc = pd.Series(bcount, index=range(NB)).sort_values(ascending=False)
    order = bc.sample(frac=1, random_state=seed).index.tolist()
    t = int(round(vf * TOT)); vb = set(); run = 0
    for b in order:
        if run >= t: break
        vb.add(b); run += bcount[b]
    return vb

# per-region strata defined by RECORD state (the BUG-0027 hazard): a block
# holding records of two states can be val in one region's draw and not in
# the other's, so the split must then be assigned per RECORD.
def region_record_strat(seed, vf=VF):
    rng = np.random.default_rng(seed)
    isval = np.zeros(TOT, dtype=bool)
    for r in R:
        m = rec_state == r
        sub = base.bidx.values[m]
        bl = np.unique(sub); cnt = pd.Series(sub).value_counts()
        t = int(round(vf * m.sum())); run = 0; chosen = set()
        for b in rng.permutation(bl):
            if run >= t: break
            chosen.add(int(b)); run += cnt[b]
        isval[m] = np.isin(sub, list(chosen))
    return isval

def _grow(seed, nblob, vf=VF):
    """contiguous-blob val draw; re-seeds when a blob's connected component
    is exhausted, so the record target is always met."""
    rng = np.random.default_rng(seed); vb = set(); nb_used = 0
    for r in R:
        idx = np.where(breg == r)[0]
        t = int(round(vf * NREG[r])); run = 0; used = set()
        seeds = list(rng.permutation(idx))
        blobs = []
        while run < t:
            while len(blobs) < nblob and seeds:
                s0 = int(seeds.pop())
                if s0 not in used: blobs.append([s0]); nb_used += 1
            if not blobs: break
            prog = False
            for fr in list(blobs):
                if run >= t: break
                while fr:
                    b = fr.pop(0)
                    if b in used or breg[b] != r: continue
                    used.add(b); vb.add(b); run += bcount[b]; prog = True
                    fr.extend([j for j in adj[b] if j not in used and breg[j] == r])
                    break
                if not fr: blobs.remove(fr)
            if not prog and not seeds: break
    return vb

def east_within(seed, cells, vf=VF):
    """val blocks only from the eastern half of each `cells`-block cell,
    balanced per region."""
    rng = np.random.default_rng(seed); vb = set()
    c = cell(cells); key = np.zeros(NB)
    for s in np.unique(c):
        m = c == s; key[m] = (bxy[m, 0] >= np.median(bxy[m, 0])).astype(float)
    for r in R:
        idx = np.where((breg == r) & (key > 0))[0]
        t = int(round(vf * NREG[r])); run = 0
        for b in rng.permutation(idx):
            if run >= t: break
            vb.add(int(b)); run += bcount[b]
    return vb

def tomask(vb):
    v = np.zeros(NB, dtype=bool); v[list(vb)] = True
    return v[base.bidx.values]

# ---------------- statistics ----------------
ANG = np.arange(8) * np.pi / 8
def mx(a):
    a = np.asarray(a, float)
    return float(np.nanmax(a)) if np.any(np.isfinite(a)) else np.nan
def stats(isval):
    S = {}; v = isval; t = ~isval
    S['val_frac_pp'] = 100 * v.mean()
    S['I7_worst_pp'] = mx([abs(100 * v[rec_state == r].mean() - 20) for r in R])
    bv = np.unique(base.bidx.values[v]); S['n_val_blocks'] = len(bv)
    S['I15_disp_pp'] = abs(100 * len(bv) / NB - 100 * v.mean())
    S['rec_per_valblk'] = v.sum() / max(len(bv), 1)
    agg = pd.DataFrame({'b': base.bidx.values, 'v': isval}).groupby('b')['v'].agg(['min', 'max'])
    S['blocks_both_splits'] = int((agg['min'] != agg['max']).sum())
    tr = cKDTree(np.c_[x[t], y[t]]); d = tr.query(np.c_[x[v], y[v]], k=1)[0]
    S['n_val_within_3km_of_train'] = int((d < 3000).sum())
    S['n_val_within_30m_of_train'] = int((d < 30).sum())
    S['nn_train_med_km'] = float(np.median(d) / 1000)
    S['nn_train_p10_km'] = float(np.percentile(d, 10) / 1000)
    ksp = []; kb = []
    for r in R:
        m = rec_state == r
        for a in ANG:
            p = x[m] * np.cos(a) + y[m] * np.sin(a)
            ksp.append(ks_2samp(p[v[m]], p[t[m]]).statistic)
        mb = breg == r; isv_b = np.zeros(NB, bool); isv_b[bv] = True
        if 4 < isv_b[mb].sum() < mb.sum() - 4:
            for a in ANG:
                p = bcen[mb, 0] * np.cos(a) + bcen[mb, 1] * np.sin(a)
                kb.append(ks_2samp(p[isv_b[mb]], p[~isv_b[mb]]).statistic)
    S['ks_proj_max'] = mx(ksp); S['ks_blkproj_max'] = mx(kb)
    isv_b = np.zeros(NB, bool); isv_b[bv] = True
    z = isv_b.astype(float) - isv_b.mean()
    S['moran_I'] = float((z[:, None] * z[knn]).sum() / (z ** 2).sum() / 8.0)
    for n, nm in ((10, 'q30km'), (4, 'q12km')):
        g = pd.DataFrame({'c': rcell(n), 'v': isval}).groupby('c')['v'].agg(['mean', 'size'])
        g = g[g['size'] >= 20]
        S[nm + '_frac_zero'] = float((g['mean'] == 0).mean())
        S[nm + '_chi2_per_cell'] = float((((g['mean'] - VF) ** 2 / (VF * .8 / g['size']))).mean())
        S[nm + '_maxdev_pp'] = float((100 * (g['mean'] - VF)).abs().max())
    kf = [ks_2samp(base[c].values[v], base[c].values[t]).statistic for c in CONT]
    S['ks_feat_max'] = mx(kf)
    kfr = [ks_2samp(base[c].values[(rec_state == r) & v], base[c].values[(rec_state == r) & t]).statistic
           for r in R for c in CONT]
    S['ks_feat_reg_max'] = mx(kfr)
    ku = {}
    for c in UNMOD:
        vv = base[c].values; ok = np.isfinite(vv)
        ku[c] = ks_2samp(vv[ok & v], vv[ok & t]).statistic
        pr = [ks_2samp(vv[ok & v & (rec_state == r)], vv[ok & t & (rec_state == r)]).statistic
              for r in R if (ok & (rec_state == r)).sum() > 50]
        ku[c + '_reg'] = mx(pr)
    S.update({'ksu_' + k: vv2 for k, vv2 in ku.items()})
    S['ks_unmod_max'] = mx([ku[c] for c in UNMOD])
    S['ks_unmod_reg_max'] = mx([ku[c + '_reg'] for c in UNMOD])
    return S

SEEDS = list(range(1, 61)) + [101, 202, 303, 404]
DESIGNS = {
    'A_global (today)':        lambda s: tomask(fair_asis(s)),
    'A_global_shuffle':        lambda s: tomask(strat_draw(s, None)),
    'B_strat_region_block':    lambda s: tomask(strat_draw(s, breg)),
    'B_strat_region_RECORD':   lambda s: region_record_strat(s),
    'C_strat_30km_cell':       lambda s: tomask(strat_draw(s, cell(10))),
    'C_strat_60km_cell':       lambda s: tomask(strat_draw(s, cell(20))),
    'C_strat_12km_cell':       lambda s: tomask(strat_draw(s, cell(4))),
    'CB_strat_30km_x_region':  lambda s: tomask(strat_draw(s, [f"{a}_{b}" for a, b in zip(cell(10), breg)])),
    'D_strat_zone_x_region':   lambda s: tomask(strat_draw(s, [f"{a}_{b}" for a, b in zip(bzone, breg)])),
}
ATTACKS = {
    'ATK east-half (per region)':   lambda s: tomask(east_within(s, 10 ** 6)),
    'ATK east-half of 60km cell':   lambda s: tomask(east_within(s, 20)),
    'ATK east-half of 30km cell':   lambda s: tomask(east_within(s, 10)),
    'ATK east-half of 12km cell':   lambda s: tomask(east_within(s, 4)),
    'ATK cluster 1 blob/region':    lambda s: tomask(_grow(s, 1)),
    'ATK cluster 10 blobs/region':  lambda s: tomask(_grow(s, 10)),
    'ATK cluster 50 blobs/region':  lambda s: tomask(_grow(s, 50)),
}
res = {}
for nm, fn in DESIGNS.items():
    print("design", nm, flush=True)
    res[nm] = pd.DataFrame([stats(fn(s)) for s in SEEDS])
for nm, fn in ATTACKS.items():
    print("attack", nm, flush=True)
    res[nm] = pd.DataFrame([stats(fn(s)) for s in SEEDS[:12]])
pickle.dump(res, open(SP + "/designs.pkl", "wb"))
print("saved")
