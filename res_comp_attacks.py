"""RES-COMP: the NEGATIVE-class composition attacks, scored on the same
statistics as the fair calibration.  Every attack goes through
L.real_draw UNCHANGED -- only the candidate pool / its `weight` column /
the positive-free block split is perturbed, which is exactly where a real
defect would live.  READ-ONLY (scratch only).
usage: python res_comp_attacks.py NSEEDS OUT.csv"""
import sys, time, numpy as np, pandas as pd
from scipy.spatial import cKDTree
import inv_formalC_lib as L
import res_comp_stats as S

NS = int(sys.argv[1]); OUT = sys.argv[2]
P0, C0 = S.load_feat()
PBLOCKS = set(P0.blk.unique())
FREE = C0.loc[~C0.blk.isin(PBLOCKS)]
FB = FREE.groupby('blk').agg({f: 'mean' for f in S.CONT})
FB['x'] = L.bcentre(FB.index.values)[:, 0]; FB['y'] = L.bcentre(FB.index.values)[:, 1]
_, KNN = cKDTree(FB[['x', 'y']].values).query(FB[['x', 'y']].values, k=9)
WET = ['Swamp Sparrow', 'Northern Waterthrush', 'Common Yellowthroat',
       'Alder Flycatcher']


def free_split_extremum(feat, gvf, seed):
    """BREAK 10B: send the LOCAL extremum of `feat` inside every 9-NN cluster
    of positive-free blocks to validation.  Salt-and-pepper -> Moran ~ 0."""
    nval = int(round(gvf * len(FB)))
    v = FB[feat].values
    rank = np.array([(v[i] >= v[KNN[i]]).mean() for i in range(len(FB))])
    sel = set(FB.index.values[np.argsort(-rank)[:nval]])
    return {b: ('val' if b in sel else 'train') for b in FB.index}


def build(seed, attack, arg=None):
    P, bt, gvf, tg = S.positive_split(P0, seed)
    C = C0.copy()
    if attack == 'B10B':
        fs = free_split_extremum(arg, gvf, seed)
        C['split'] = [bt[b] if b in bt else fs[b] for b in C.blk]
    else:
        C['split'] = [bt[b] if b in bt else L.hash_split(b, gvf, seed) for b in C.blk]
    hab = ~C.is_nonveg.values
    shadow = None
    if attack == 'B10C':
        rng = np.random.default_rng(7 + seed)
        h = C[hab]; nv = C[~hab]
        k = h.iloc[rng.choice(len(h), int(arg * len(h)), replace=False)]
        C = pd.concat([k, nv], ignore_index=True)
    elif attack == 'A7':                     # cross-split habitat feature skew
        f = arg; z = (C[f] - C[f].mean()) / C[f].std()
        sgn = np.where(C.split.values == 'val', 1.0, -1.0)
        C.loc[hab, 'weight'] = (C.loc[hab, 'weight'].values
                                * np.exp(3.0 * (z.values * sgn)[hab]))
    elif attack == 'A8':                     # weight sign inversion (1/w)
        C.loc[hab, 'weight'] = 1.0 / C.loc[hab, 'weight'].values
    elif attack == 'A8b':
        # the SAMPLING PROBABILITY is inverted while the recorded `weight`
        # column stays canonical -- invisible to any recompute-the-column gate.
        shadow = C['weight'].values.copy()
        shadow[hab] = 1.0 / shadow[hab]
    elif attack == 'A9':                     # weights collapse to neutral 1.0
        C.loc[hab, 'weight'] = 1.0
    elif attack == 'A10':                    # NonVeg monoculture inside the cap
        keepc = C.loc[~hab, 'evt_phys'].value_counts().index[0]
        bad = (~hab) & (C.evt_phys.values != keepc)
        C.loc[bad, 'weight'] = 1e-6
    elif attack == 'A11':                    # wetland-species monoculture
        bad = hab & (~C.common_name.isin(WET).values)
        C.loc[bad, 'weight'] = 1e-6
    elif attack == 'A12':                    # envelope monoculture (top-3 ids)
        top = C.loc[hab, 'envelope_id'].value_counts().index[:3]
        bad = hab & (~C.envelope_id.isin(top).values)
        C.loc[bad, 'weight'] = 1e-6
    elif attack == 'B10B_NH':                # single-region variant of 10B
        fs = free_split_extremum(arg, gvf, seed)
        C['split'] = [(bt[b] if b in bt else
                       (fs[b] if st == 'NH' else L.hash_split(b, gvf, seed)))
                      for b, st in zip(C.blk, C.state)]
    elif attack == 'A7_NH':                  # single-region variant of A7
        f = arg; z = (C[f] - C[f].mean()) / C[f].std()
        sgn = np.where(C.split.values == 'val', 1.0, -1.0)
        m = hab & (C.state.values == 'NH')
        C.loc[m, 'weight'] = (C.loc[m, 'weight'].values
                              * np.exp(3.0 * (z.values * sgn)[m]))
    if shadow is not None:
        CS = C.copy(); CS['weight'] = shadow
        neg = L.real_draw(CS, tg, seed)
        neg['weight'] = neg['weight_true'].values
    else:
        neg = L.real_draw(C, tg, seed)
    return P, C, neg, tg


ATK = [('fair', None),
       ('B10B', 'tcc'), ('B10B', 'road_dist'), ('B10B_NH', 'tcc'),
       ('B10C', 0.90), ('B10C', 0.80), ('B10C', 0.70), ('B10C', 0.50),
       ('B10C', 0.25), ('B10C', 0.10),
       ('A7', 'tcc'), ('A7', 'balive'), ('A7_NH', 'tcc'),
       ('A8', None), ('A8b', None), ('A9', None),
       ('A10', None), ('A11', None), ('A12', None)]
rows = []
t0 = time.time()
for name, arg in ATK:
    for i, seed in enumerate(range(1000, 1000 + NS)):
        P, C, neg, tg = build(seed, name, arg)
        g = S.comp_stats(P, C, neg, tg)
        g['attack'] = f"{name}({arg})" if arg is not None else name
        g['seed'] = seed
        if i == 0:
            gr = L.gate_report(P, neg, pool_blocks=C.drop_duplicates('blk')[['blk', 'split']],
                               label=g['attack'], quiet=True)
            L.TARGETS = tg
            gr['I8'] = all(int(((neg.state == r) & (neg.split == s)).sum()) == n
                           for (r, s), n in tg.items())
            for k in ('I1', 'I2', 'I3', 'I4_pos', 'I4_neg', 'I6', 'I8', 'I15',
                      'I16_k4', 'I16_k8', 'I16b_sel_k4', 'I16b_sel_k8',
                      'I16b_pool_k4', 'I16b_pool_k8', 'I18', 'I19_worst'):
                g['CR_' + k] = gr.get(k)
            # I17 as the CR specifies it: POSITIVES only
            from scipy.stats import ks_2samp
            g['CR_I17_pos'] = max(
                ks_2samp(P.loc[P.split == 'val', f].dropna(),
                         P.loc[P.split == 'train', f].dropna()).statistic
                for f in S.CONT)
        rows.append(g)
    print(f"  {g['attack']:>18}  {time.time()-t0:.0f}s", flush=True)
pd.DataFrame(rows).to_csv(OUT, index=False)
print("saved", OUT)
