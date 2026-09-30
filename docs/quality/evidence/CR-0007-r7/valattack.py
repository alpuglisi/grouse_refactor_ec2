"""Val-side attacks against the CR's frozen I19' absolute thresholds + C5-C9, C12-C16
(my implementations). Fair null = negative draws at the production positive split (seed 42)."""
import sys, numpy as np, pandas as pd
from scipy.stats import ks_2samp
sys.path.insert(0, "/tmp/claude-1000/-home-ec2-user-grouse2/f462782e-8989-4c4d-919a-db7e5946838a/scratchpad/cr0007_A")
from lib import *
F9 = ['ch', 'cc', 'tcc', 'road_dist', 'tsd', 'balive', 'tpa_live', 'qmd', 'carbon_dwn']
THR = {'Exc': {'ME': 1.2238, 'NH': 1.5143, 'VT': 0.7842}, 'S': {'ME': 0.5667, 'NH': 0.6431, 'VT': 0.4863},
       'Excws': {'ME': 5.1204, 'NH': 7.8778, 'VT': 4.0744}, 'Sws': {'ME': 0.7815, 'NH': 0.9358, 'VT': 0.7814}}
CG = {'C5': 0.074, 'C6': 0.105, 'C7_ME': 0.106, 'C7_NH': 0.168, 'C7_VT': 0.166, 'C8': 6.36,
      'C9': 0.0038, 'C12': 0.104, 'C13': 7.62, 'C15': 0.280, 'C16': 0.245}
pos = split_positives(pd.read_csv(f"{OUT}/pos_thinned.csv"))
P = pd.read_csv(f"{OUT}/pool_prebuffer_f9.csv", low_memory=False)
P = assign_neg_split(P[P.d_grouse > 300].reset_index(drop=True), pos)

def tv(a, b):
    k = set(a) | set(b); return 0.5 * sum(abs(a.get(x, 0) - b.get(x, 0)) for x in k)
def smd(a, b):
    return abs(a.mean() - b.mean()) / np.sqrt(a.var() / len(a) + b.var() / len(b) + 1e-12)
def wsmd(sel, pool):
    w = pool.weight.values / pool.weight.sum()
    out = 0
    for f in F9:
        mu = (w * pool[f].values).sum(); sd = np.sqrt((w * (pool[f].values - mu) ** 2).sum())
        out = max(out, abs(sel[f].mean() - mu) / (sd / np.sqrt(len(sel)) + 1e-12))
    return out

def gates(neg, pool):
    o = {}
    tr, va = neg[neg.split == 'train'], neg[neg.split == 'val']
    o['C5'] = max(ks_2samp(tr[f], va[f]).statistic for f in F9)
    h = neg[~neg.is_nonveg]; o['C6'] = max(ks_2samp(h[h.split == 'train'][f], h[h.split == 'val'][f]).statistic for f in F9)
    o['C8'] = 0; o['C9'] = 0; o['C12'] = 0; o['C13'] = 0; o['C15'] = 0; o['C16'] = 0
    for r in R:
        n = neg[neg.state == r]; t, v = n[n.split == 'train'], n[n.split == 'val']
        o[f'C7_{r}'] = max(ks_2samp(t[f], v[f]).statistic for f in F9)
        o['C8'] = max(o['C8'], max(smd(t[f], v[f]) for f in F9))
        o['C9'] = max(o['C9'], abs(t.is_nonveg.mean() - v.is_nonveg.mean()))
        for s in ['train', 'val']:
            ns = n[n.split == s]; pl = pool[(pool.state == r) & (pool.split == s)]
            hn, hp = ns[~ns.is_nonveg], pl[~pl.is_nonveg]
            exp = (hp.groupby('weight_basis').weight.sum() / hp.weight.sum()).to_dict()
            o['C12'] = max(o['C12'], tv(hn.weight_basis.value_counts(normalize=True).to_dict(), exp))
            o['C13'] = max(o['C13'], wsmd(hn, hp))
            o['C15'] = max(o['C15'], tv(ns[ns.is_nonveg].evt_phys.value_counts(normalize=True).to_dict(),
                                        pl[pl.is_nonveg].evt_phys.value_counts(normalize=True).to_dict()))
            expc = (pl.groupby('common_name').weight.sum() / pl.weight.sum()).to_dict()
            o['C16'] = max(o['C16'], tv(ns.common_name.value_counts(normalize=True).to_dict(), expc))
    return o

def evaluate(neg, pool):
    o = {**i19(pos, neg), **gates(neg, pool)}
    fired = [f"{k}_{r}" for k in THR for r in R if o[f"{k}_{r}"] > THR[k][r]]
    fired += [k for k, t in CG.items() if o[k] > t]
    # harm: val positives with no val negative within RF
    return o, fired

if __name__ == "__main__":
    NS = 40
    fair = [evaluate(draw(P, pos, s), P) for s in range(NS)]
    FF = pd.DataFrame([f for f, _ in fair])
    print("FAIR any-fire rate:", np.mean([len(x) > 0 for _, x in fair]), pd.Series(sum([x for _, x in fair], [])).value_counts().to_dict())
    print("FAIR C maxima:", FF[list(CG)].max().round(4).to_dict())
    base = {r: FF[f'Sws_{r}'].mean() for r in R}
    nval = {r: int(((pos.state == r) & (pos.split == 'val')).sum()) for r in R}
    def attack(name, poolA, poolRef=None):
        res = [evaluate(draw(poolA, pos, 2000 + s), poolRef if poolRef is not None else poolA) for s in range(20)]
        A = pd.DataFrame([a for a, _ in res]); fires = np.mean([len(x) > 0 for _, x in res])
        harm = sum((A[f'Sws_{r}'].mean() - base[r]) * nval[r] for r in R)
        excess = sum((A[f'Excws_{r}'].mean() - FF[f'Excws_{r}'].mean()) * nval[r] for r in R)
        print(f"{name}: fires {fires:.2f} [{pd.Series(sum([x for _, x in res], [])).value_counts().to_dict()}]  "
              f"+stranded val pos {harm:.0f}  +excess km {excess:.0f}  Sws {[round(A[f'Sws_{r}'].mean(),3) for r in R]}")
    for q in [0.1, 0.2, 0.3, 0.4]:
        # remove the northern q of VAL candidates in each region (pool damage, val split only)
        keep = np.ones(len(P), bool)
        for r in R:
            m = ((P.state == r) & (P.split == 'val')).values
            cut = np.quantile(P.loc[m, 'y_5070'], 1 - q)
            keep &= ~(m & (P.y_5070.values > cut))
        attack(f"val-north-strip q={q}", P[keep].reset_index(drop=True))
    for q in [0.1, 0.2, 0.3]:
        # val-only 'far from val positives' removal: drop val candidates within 3 km of a val positive with prob q
        from scipy.spatial import cKDTree
        keep = np.ones(len(P), bool); rng = np.random.default_rng(5)
        for r in R:
            pv = pos[(pos.state == r) & (pos.split == 'val')]
            m = ((P.state == r) & (P.split == 'val')).values
            d = cKDTree(pv[['x_5070', 'y_5070']].values).query(P.loc[m, ['x_5070', 'y_5070']].values)[0]
            idx = np.where(m)[0]
            keep[idx[(d < 3000) & (rng.random(len(idx)) < q)]] = False
        attack(f"val near-val-positive thinning q={q}", P[keep].reset_index(drop=True))
