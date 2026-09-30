"""Phase 4: tight calibration of the recommended statistic.
1000 fair draws -> quantiles; Moran's I at several neighbourhood sizes;
analytic randomisation null for portability; receptive-field overlap.
READ-ONLY."""
import os, sys, itertools, pickle
import numpy as np, pandas as pd
from scipy.spatial import cKDTree
from scipy.stats import ks_2samp
os.chdir("/home/ec2-user/grouse2"); sys.path.insert(0, ".")
SP = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
R = ["ME", "NH", "VT"]; SZ = 3000.0; VF = 0.2
base = pd.read_csv(SP + "/base.csv"); unmod = pd.read_csv(SP + "/unmod.csv")
base['lidar_elev'] = unmod.lidar_elev.values
blocks = pd.Index(sorted(base.blk.unique())); NB = len(blocks)
bi = pd.Series(np.arange(NB), index=blocks); base['bidx'] = bi[base.blk.values].values
bcount = np.bincount(base.bidx, minlength=NB)
bxy = np.array([[int(b.split('_')[0]), int(b.split('_')[1])] for b in blocks]); bcen = bxy * SZ + SZ / 2
breg = base.groupby('bidx')['state'].agg(lambda s: s.value_counts().idxmax()).reindex(range(NB)).values
belev = base.groupby('bidx')['lidar_elev'].mean().reindex(range(NB)).values
rec_state = base.state.values; TOT = len(base); NREG = {r: int((rec_state == r).sum()) for r in R}
KS_ = [4, 8, 16, 32, 64]
NN = {k: cKDTree(bcen).query(bcen, k=k + 1)[1][:, 1:] for k in KS_}
adjlat = {(int(a), int(b)): i for i, (a, b) in enumerate(bxy)}
adj = [[j for j in (adjlat.get((x + dx, y + dy)) for dx, dy in itertools.product((-1, 0, 1), repeat=2)
        if (dx, dy) != (0, 0)) if j is not None] for x, y in bxy]
x, y = base.x_5070.values, base.y_5070.values
ANG = np.arange(8) * np.pi / 8
RF = 1920.0   # receptive field width quoted in CR-0007 (64 px @ 30 m)

def moran(isv_b, k):
    z = isv_b.astype(float) - isv_b.mean()
    return float((z[:, None] * z[NN[k]]).sum() / (z ** 2).sum() / k)

def moran_z(I, k, nval):
    """analytic randomisation null for a row-standardised k-NN weight matrix
    on a binary variable: E[I] = -1/(n-1); Var from Cliff & Ord."""
    n = NB; S0 = float(n)
    W = np.zeros((0,))
    # S1 = .5*sum_ij (w_ij + w_ji)^2 ; S2 = sum_i (sum_j w_ij + sum_j w_ji)^2
    w = 1.0 / k
    rowsum = np.ones(n)
    colsum = np.bincount(NN[k].ravel(), minlength=n) * w
    # build sparse-ish accumulation for S1
    import collections
    M = collections.Counter()
    for i in range(n):
        for j in NN[k][i]:
            M[(i, j)] += w
    S1 = 0.5 * sum((M[(i, j)] + M.get((j, i), 0.0)) ** 2 for (i, j) in M)
    S2 = float(((rowsum + colsum) ** 2).sum())
    p = nval / n
    v = np.zeros(n); v[:nval] = 1.0
    z = v - v.mean(); m2 = (z ** 2).sum() / n; m4 = (z ** 4).sum() / n
    b2 = m4 / m2 ** 2
    EI = -1.0 / (n - 1)
    A = n * ((n * n - 3 * n + 3) * S1 - n * S2 + 3 * S0 ** 2)
    B = b2 * ((n * n - n) * S1 - 2 * n * S2 + 6 * S0 ** 2)
    VI = (A - B) / ((n - 1) * (n - 2) * (n - 3) * S0 ** 2) - EI ** 2
    return (I - EI) / np.sqrt(VI), EI, np.sqrt(VI)

def fair(seed, vf=VF):
    bc = pd.Series(bcount, index=range(NB)).sort_values(ascending=False)
    order = bc.sample(frac=1, random_state=seed).index.tolist()
    t = int(round(vf * TOT)); vb = set(); run = 0
    for b in order:
        if run >= t: break
        vb.add(b); run += bcount[b]
    return vb
def half(seed, axis=0, cells=None, vf=VF):
    rng = np.random.default_rng(seed); vb = set(); key = np.zeros(NB, bool)
    if cells is None:
        for r in R:
            m = breg == r; key[m] = bxy[m, axis] >= np.median(bxy[m, axis])
    else:
        c = (bxy[:, 0] // cells) * 100000 + (bxy[:, 1] // cells)
        for s in np.unique(c):
            m = c == s; key[m] = bxy[m, axis] >= np.median(bxy[m, axis])
    for r in R:
        idx = np.where((breg == r) & key)[0]; t = int(round(vf * NREG[r])); run = 0
        for b in rng.permutation(idx):
            if run >= t: break
            vb.add(int(b)); run += bcount[b]
    return vb
def hielev(seed, vf=VF):       # ME/NH only (no VT lidar raster) -- noted as such
    rng = np.random.default_rng(seed); vb = set()
    for r in ["ME", "NH"]:
        idx = np.where(breg == r)[0]; k = belev[idx]; cut = np.nanmedian(k)
        elig = idx[k >= cut]; t = int(round(vf * NREG[r])); run = 0
        for b in rng.permutation(elig):
            if run >= t: break
            vb.add(int(b)); run += bcount[b]
    idx = np.where(breg == "VT")[0]; t = int(round(vf * NREG["VT"])); run = 0
    for b in rng.permutation(idx):
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
def strat(seed, strata, vf=VF):
    rng = np.random.default_rng(seed); vb = set(); st = pd.factorize(np.asarray(strata))[0]
    for s in np.unique(st):
        idx = np.where(st == s)[0]; t = int(round(vf * bcount[idx].sum())); run = 0
        for b in rng.permutation(idx):
            if run >= t: break
            vb.add(int(b)); run += bcount[b]
    return vb
cell = lambda n: (bxy[:, 0] // n) * 100000 + (bxy[:, 1] // n)

def stats(vb):
    isv_b = np.zeros(NB, bool); isv_b[list(vb)] = True
    isval = isv_b[base.bidx.values]
    S = {'n_val_blocks': int(isv_b.sum()), 'val_frac_pp': 100 * isval.mean()}
    for k in KS_:
        S[f'moran_k{k}'] = moran(isv_b, k)
    S['moran_z_k8'] = moran_z(S['moran_k8'], 8, int(isv_b.sum()))[0]
    kb = []
    for r in R:
        mb = breg == r
        if 4 < isv_b[mb].sum() < mb.sum() - 4:
            for a in ANG:
                p = bcen[mb, 0] * np.cos(a) + bcen[mb, 1] * np.sin(a)
                kb.append(ks_2samp(p[isv_b[mb]], p[~isv_b[mb]]).statistic)
    S['ks_blkproj_max'] = max(kb) if kb else np.nan
    rc = (base.bx.values // 10) * 100000 + (base.by.values // 10)
    g = pd.DataFrame({'c': rc, 'v': isval}).groupby('c')['v'].agg(['mean', 'size']); g = g[g['size'] >= 20]
    S['q30km_frac_zero'] = float((g['mean'] == 0).mean())
    S['q30km_chi2'] = float(((g['mean'] - VF) ** 2 / (VF * .8 / g['size'])).mean())
    tr = cKDTree(np.c_[x[~isval], y[~isval]]); d = tr.query(np.c_[x[isval], y[isval]], k=1)[0]
    S['nn_train_med_km'] = float(np.median(d) / 1000)
    S['frac_val_within_RF'] = float((d < RF).mean())
    S['frac_val_within_halfRF'] = float((d < RF / 2).mean())
    return S

NFAIR = 1000
print("calibrating fair design over", NFAIR, "seeds", flush=True)
F = pd.DataFrame([stats(fair(s)) for s in range(1, NFAIR + 1)])
A = {'fair x1000': F}
for nm, fn, ns in [
        ('east half/region', lambda s: half(s, 0), 50),
        ('north half/region', lambda s: half(s, 1), 50),
        ('east half of 60km', lambda s: half(s, 0, 20), 50),
        ('east half of 30km', lambda s: half(s, 0, 10), 50),
        ('east half of 12km', lambda s: half(s, 0, 4), 50),
        ('hi elev ME/NH', hielev, 50),
        ('cluster 1/region', lambda s: grow(s, 1), 30),
        ('cluster 10/region', lambda s: grow(s, 10), 30),
        ('cluster 50/region', lambda s: grow(s, 50), 30),
        ('cluster 150/region', lambda s: grow(s, 150), 30),
        ('dense-first (I14)', dense, 1),
        ('DESIGN strat region', lambda s: strat(s, breg), 100),
        ('DESIGN strat 30km', lambda s: strat(s, cell(10)), 100),
        ('DESIGN strat 30kmXregion', lambda s: strat(s, [f"{a}_{b}" for a, b in zip(cell(10), breg)]), 100),
        ('DESIGN strat 60kmXregion', lambda s: strat(s, [f"{a}_{b}" for a, b in zip(cell(20), breg)]), 100),
        ('DESIGN strat 12kmXregion', lambda s: strat(s, [f"{a}_{b}" for a, b in zip(cell(4), breg)]), 100)]:
    print(nm, flush=True)
    A[nm] = pd.DataFrame([stats(fn(s)) for s in range(1, ns + 1)])
pickle.dump(A, open(SP + "/calib.pkl", "wb"))
I, k, nv = F.moran_k8.median(), 8, int(F.n_val_blocks.median())
zz, EI, SD = moran_z(I, k, nv)
print(f"\nanalytic randomisation null for Moran k=8: E[I]={EI:.6f} SD={SD:.6f}")
print(f"empirical over {NFAIR} fair draws: mean={F.moran_k8.mean():.6f} sd={F.moran_k8.std():.6f}")
print("saved calib.pkl")
