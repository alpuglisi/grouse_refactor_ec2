"""RES-COMP: the SCOPING question.  The same KS statistic read over three
record sets -- positives only (CR-0007's I17), selected negatives only
(proposed), and the two classes POOLED -- under a fair draw and under two
negative-class composition attacks.  READ-ONLY."""
import numpy as np, pandas as pd
from scipy.spatial import cKDTree
import inv_formalC_lib as L
import res_comp_stats as S

NS = 12
P0, C0 = S.load_feat()
PB = set(P0.blk.unique())
FREE = C0.loc[~C0.blk.isin(PB)]
FB = FREE.groupby('blk').agg({f: 'mean' for f in S.CONT})
FB['x'] = L.bcentre(FB.index.values)[:, 0]; FB['y'] = L.bcentre(FB.index.values)[:, 1]
_, KNN = cKDTree(FB[['x', 'y']].values).query(FB[['x', 'y']].values, k=9)

def ksmax(df):
    m = 0.0
    for f in S.CONT:
        d, _ = S._ks(df.loc[df.split == 'val', f].values,
                     df.loc[df.split == 'train', f].values)
        m = max(m, d)
    return m

def one(seed, kind):
    P, bt, gvf, tg = S.positive_split(P0, seed)
    C = C0.copy()
    if kind == 'B10B':
        nval = int(round(gvf * len(FB))); v = FB['tcc'].values
        rk = np.array([(v[i] >= v[KNN[i]]).mean() for i in range(len(FB))])
        sel = set(FB.index.values[np.argsort(-rk)[:nval]])
        fs = {b: ('val' if b in sel else 'train') for b in FB.index}
        C['split'] = [bt[b] if b in bt else fs[b] for b in C.blk]
    else:
        C['split'] = [bt[b] if b in bt else L.hash_split(b, gvf, seed) for b in C.blk]
    if kind == 'A7':
        hab = ~C.is_nonveg.values
        z = ((C.tcc - C.tcc.mean()) / C.tcc.std()).values
        sgn = np.where(C.split.values == 'val', 1.0, -1.0)
        C.loc[hab, 'weight'] = C.loc[hab, 'weight'].values * np.exp(3.0 * (z * sgn)[hab])
    neg = L.real_draw(C, tg, seed)
    pooled = pd.concat([P.assign(cls='pos'), neg.assign(cls='neg')], ignore_index=True)
    return dict(pos_only=ksmax(P), neg_only=ksmax(neg), pooled=ksmax(pooled),
                neg_hab_only=ksmax(neg[~neg.is_nonveg]))

print(f"{'record set':16} {'fair min':>9} {'fair max':>9} | "
      f"{'B10B min':>9} {'fires?':>7} | {'A7 min':>9} {'fires?':>7}")
res = {k: pd.DataFrame([one(s, k) for s in range(3000, 3000 + NS)])
       for k in ('fair', 'B10B', 'A7')}
for col in ('pos_only', 'neg_only', 'neg_hab_only', 'pooled'):
    f = res['fair'][col].values; t = 1.30 * f.max()
    b = res['B10B'][col].values; a = res['A7'][col].values
    print(f"{col:16} {f.min():9.4f} {f.max():9.4f} | {b.min():9.4f} "
          f"{('YES' if (b>t).all() else ('some' if (b>t).any() else 'NO')):>7} | "
          f"{a.min():9.4f} {('YES' if (a>t).all() else ('some' if (a>t).any() else 'NO')):>7}"
          f"   gate<= {t:.4f}")
