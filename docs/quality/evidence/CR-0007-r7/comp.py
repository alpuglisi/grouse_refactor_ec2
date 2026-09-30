"""Composition rows computable without the 9 continuous features (C1, C9, C12, C14,
C15, C16, C17) + I19' two-sided view, fair vs A1 (buffer removed) and A3p
(near-grouse draw-probability tamper, weight column untouched)."""
import sys, numpy as np, pandas as pd
sys.path.insert(0, "/tmp/claude-1000/-home-ec2-user-grouse2/f462782e-8989-4c4d-919a-db7e5946838a/scratchpad/cr0007_A")
from lib import *
pos = split_positives(pd.read_csv(f"{OUT}/pos_thinned.csv"))
P = pd.read_csv(f"{OUT}/pool_prebuffer.csv", low_memory=False)
P = assign_neg_split(P, pos)
fair_pool = P[P.d_grouse > 300].copy()

def tv(a, b):
    k = set(a) | set(b)
    return 0.5 * sum(abs(a.get(x, 0) - b.get(x, 0)) for x in k)

def comp(neg, pool):
    o = {'C12': 0, 'C15': 0, 'C16': 0, 'C14min': 9, 'C9': 0, 'C17': 99}
    for r in R:
        sh = []
        for s in ['train', 'val']:
            n = neg[(neg.state == r) & (neg.split == s)]; pl = pool[(pool.state == r) & (pool.split == s)]
            hn = n[~n.is_nonveg]; hp = pl[~pl.is_nonveg]
            exp = (hp.groupby('weight_basis').weight.sum() / hp.weight.sum()).to_dict()
            o['C12'] = max(o['C12'], tv(hn.weight_basis.value_counts(normalize=True).to_dict(), exp))
            o['C14min'] = min(o['C14min'], hn.weight.mean() / hp.weight.mean())
            nn = n[n.is_nonveg]; npl = pl[pl.is_nonveg]
            o['C15'] = max(o['C15'], tv(nn.evt_phys.value_counts(normalize=True).to_dict(),
                                        npl.evt_phys.value_counts(normalize=True).to_dict()))
            expc = (pl.groupby('common_name').weight.sum() / pl.weight.sum()).to_dict()
            o['C16'] = max(o['C16'], tv(n.common_name.value_counts(normalize=True).to_dict(), expc))
            nt = int(((pos.state == r) & (pos.split == s)).sum())
            o['C17'] = min(o['C17'], len(hp) / (nt - round(nt * 0.3)))
            sh.append(n.is_nonveg.mean())
        o['C9'] = max(o['C9'], abs(sh[0] - sh[1]))
    return o

def draw_p(pool, seed, mult):
    pool = pool.copy(); w0 = pool.weight.copy()
    pool['weight'] = w0 * mult
    n = draw(pool, pos, seed)
    return n

rows = []
for s in range(200):
    n = draw(fair_pool, pos, s); rows.append({**comp(n, fair_pool), **i19(pos, n)})
F = pd.DataFrame(rows)
cells = [c for c in F.columns if c.split('_')[0] in ('S', 'Exc', 'Sws', 'Excws')]
mu, sd = F[cells].mean(), F[cells].std()
print("FAIR max/min:", {k: (round(F[k].min(), 4), round(F[k].max(), 4)) for k in ['C9', 'C12', 'C14min', 'C15', 'C16', 'C17']})
for name, pool, mult in [("A1 no buffer", P, None),
                         ("A3p near-grouse x20 prob (weight col intact)", fair_pool,
                          np.where(fair_pool.d_grouse < 1000, 20.0, 1.0))]:
    rr = []
    for s in range(1000, 1020):
        if mult is None:
            n = draw(pool, pos, s)
        else:
            n = draw_p(pool, s, mult)
            # restore stored weight column (pipeline writes build_weight output)
            key = pool.set_index(['longitude', 'latitude']).weight
            n['weight'] = key.reindex(pd.MultiIndex.from_frame(n[['longitude', 'latitude']])).values
        rr.append({**comp(n, pool), **i19(pos, n)})
    A = pd.DataFrame(rr); z = (A[cells] - mu) / sd
    print(f"\n{name}: I19' max z med {z.max(axis=1).median():.2f} (fires {(z.max(axis=1)>5).mean():.2f}); min z med {z.min(axis=1).median():.2f}")
    print("  medians:", {k: round(A[k].median(), 4) for k in ['C9', 'C12', 'C14min', 'C15', 'C16', 'C17']})
