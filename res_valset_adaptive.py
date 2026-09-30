"""Phase 5: ADAPTIVE attack -- maximise location bias SUBJECT TO passing the
proposed Moran's-I gate.  Gives a BOUND on the residual harm a gated draw
still permits, instead of one more enumerated bad outcome.  READ-ONLY."""
import os, sys, pickle
import numpy as np, pandas as pd
from scipy.spatial import cKDTree
from scipy.stats import ks_2samp
os.chdir("/home/ec2-user/grouse2")
SP = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
R = ["ME", "NH", "VT"]; SZ = 3000.0; VF = 0.2
base = pd.read_csv(SP + "/base.csv"); unmod = pd.read_csv(SP + "/unmod.csv")
feat = pd.read_csv(SP + "/feat.csv")
base['lidar_elev'] = unmod.lidar_elev.values; base['slope'] = unmod.slope.values
base['spatial_density_'] = unmod.spatial_density.values
for c in feat.columns: base[c] = feat[c].values
blocks = pd.Index(sorted(base.blk.unique())); NB = len(blocks)
bi = pd.Series(np.arange(NB), index=blocks); base['bidx'] = bi[base.blk.values].values
bcount = np.bincount(base.bidx, minlength=NB)
bxy = np.array([[int(b.split('_')[0]), int(b.split('_')[1])] for b in blocks]); bcen = bxy * SZ + SZ / 2
breg = base.groupby('bidx')['state'].agg(lambda s: s.value_counts().idxmax()).reindex(range(NB)).values
belev = base.groupby('bidx')['lidar_elev'].mean().reindex(range(NB)).values
rec_state = base.state.values; TOT = len(base); NREG = {r: int((rec_state == r).sum()) for r in R}
knn8 = cKDTree(bcen).query(bcen, k=9)[1][:, 1:]
x, y = base.x_5070.values, base.y_5070.values
FIELDS = ["lidar_elev", "slope", "spatial_density_", "tcc", "road_dist", "qmd"]

def moran(isv_b, nn=knn8):
    z = isv_b.astype(float) - isv_b.mean()
    return float((z[:, None] * z[nn]).sum() / (z ** 2).sum() / nn.shape[1])

def grad_draw(seed, key, beta, vf=VF):
    """per region, sample blocks WITHOUT replacement with probability
    proportional to exp(beta * standardised key), until vf of records."""
    rng = np.random.default_rng(seed); vb = set()
    for r in R:
        idx = np.where(breg == r)[0]
        k = key[idx].astype(float)
        if np.isnan(k).any(): k = np.where(np.isnan(k), np.nanmean(k), k)
        ks = (k - k.mean()) / (k.std() + 1e-9)
        logw = beta * ks
        g = logw + rng.gumbel(size=len(idx))            # Gumbel top-k = weighted sample w/o replacement
        order = idx[np.argsort(-g)]
        t = int(round(vf * NREG[r])); run = 0
        for b in order:
            if run >= t: break
            vb.add(int(b)); run += bcount[b]
    return vb

def measure(vb):
    isv_b = np.zeros(NB, bool); isv_b[list(vb)] = True
    isval = isv_b[base.bidx.values]; v = isval; t = ~isval
    S = {'moran_k8': moran(isv_b), 'val_frac_pp': 100 * v.mean(),
         'n_val_blocks': int(isv_b.sum())}
    S['I7_worst_pp'] = max(abs(100 * v[rec_state == r].mean() - 20) for r in R)
    S['medshift_x_km'] = max(abs(np.median(x[v & (rec_state == r)]) -
                                 np.median(x[t & (rec_state == r)])) / 1000 for r in R)
    kb = []
    for r in R:
        mb = breg == r
        for a in np.arange(8) * np.pi / 8:
            p = bcen[mb, 0] * np.cos(a) + bcen[mb, 1] * np.sin(a)
            kb.append(ks_2samp(p[isv_b[mb]], p[~isv_b[mb]]).statistic)
    S['ks_blkproj_max'] = max(kb)
    rc = (base.bx.values // 10) * 100000 + (base.by.values // 10)
    g = pd.DataFrame({'c': rc, 'v': isval}).groupby('c')['v'].agg(['mean', 'size']); g = g[g['size'] >= 20]
    S['q30km_frac_zero'] = float((g['mean'] == 0).mean())
    for c in FIELDS:
        vv = base[c].values; ok = np.isfinite(vv)
        pop = vv[ok].mean(); se = vv[ok].std(ddof=1) / np.sqrt((ok & v).sum())
        S['zbias_' + c] = float((vv[ok & v].mean() - pop) / se)
        S['ks_' + c] = ks_2samp(vv[ok & v], vv[ok & t]).statistic
    S['max_abs_zbias'] = max(abs(S['zbias_' + c]) for c in FIELDS)
    S['max_ks_field'] = max(S['ks_' + c] for c in FIELDS)
    return S

rows = []
for nm, key in [('x (east gradient)', bxy[:, 0].astype(float)),
                ('y (north gradient)', bxy[:, 1].astype(float)),
                ('elev (unmodelled)', belev)]:
    for beta in [0.0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0]:
        for s in range(1, 13):
            d = measure(grad_draw(s, key, beta)); d['key'] = nm; d['beta'] = beta; rows.append(d)
    print("done", nm, flush=True)
D = pd.DataFrame(rows)
D.to_csv(SP + "/adaptive.csv", index=False)
COLS = ['moran_k8', 'ks_blkproj_max', 'q30km_frac_zero', 'I7_worst_pp', 'medshift_x_km',
        'max_abs_zbias', 'max_ks_field', 'zbias_lidar_elev', 'ks_lidar_elev']
g = D.groupby(['key', 'beta'])[COLS].agg(['mean', 'max'])
pd.set_option('display.width', 300); pd.set_option('display.max_columns', 50)
print(g.round(3).to_string())
