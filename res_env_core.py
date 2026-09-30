"""RESEARCH (read-only): score EVERY negative-dependent CR-0007 acceptance
statistic on the FAITHFUL sampler (inv_formalC_pool2 pool + inv_formalC_lib
real two-pool weighted NonVeg-capped draw).  No project file is written.
"""
import numpy as np, pandas as pd
from scipy.spatial import cKDTree
from scipy.stats import ks_2samp
import inv_formalC_lib as L

CONT = ["ch", "cc", "tcc", "road_dist", "tsd", "balive", "tpa_live", "qmd",
        "carbon_dwn"]
SCR = L.SCR


def load_all():
    P, C = L.load()
    FP = pd.read_csv(f"{SCR}/fc_feat_pos.csv")
    FC = pd.read_csv(f"{SCR}/fc_feat_pool.csv")
    assert len(FP) == len(P) and len(FC) == len(C)
    P = pd.concat([P, FP], axis=1)
    C = pd.concat([C, FC], axis=1)
    return P, C


def assign(P, C, seed, free_rule=None):
    """The intended pipeline's split: val blocks drawn over the
    positive-occupied block set; positive-free blocks hashed
    (split_for_unassigned) at the GLOBAL block-level val rate."""
    vb = L.val_blocks(P, seed)
    P = P.copy()
    P['split'] = np.where(P.blk.isin(vb), 'val', 'train')
    pb = set(P.blk.unique())
    bt = {b: ('val' if b in vb else 'train') for b in pb}
    gvf = len(vb) / len(pb)
    C = C.copy()
    if free_rule is None:
        C['split'] = [bt[b] if b in bt else L.hash_split(b, gvf, seed)
                      for b in C.blk]
    else:
        free = np.array(sorted(set(C.blk.values) - pb))
        fs = free_rule(C, free, gvf, seed)
        C['split'] = [bt[b] if b in bt else fs[b] for b in C.blk]
    tg = {(r, s): int(((P.state == r) & (P.split == s)).sum())
          for r in L.R for s in ('train', 'val')}
    return P, C, tg, gvf


def score(P, Cp, neg, tg):
    g = {}
    # ---- I19 + the median pos->nearest-neg distance it replaced
    for r in L.R:
        p = P[P.state == r][['x_5070', 'y_5070']].values
        n = neg[neg.state == r][['x_5070', 'y_5070']].values
        if len(n) == 0:
            g[f'I19_{r}'] = 1.0; g[f'med_{r}'] = np.inf; continue
        d, _ = cKDTree(n).query(p, k=1)
        g[f'I19_{r}'] = float((d > L.RF).mean())
        g[f'med_{r}'] = float(np.median(d))
    d, _ = cKDTree(neg[['x_5070', 'y_5070']].values).query(
        P[['x_5070', 'y_5070']].values, k=1)
    g['I19_pooled'] = float((d > L.RF).mean())
    g['med_pooled'] = float(np.median(d))
    g['I19_worst'] = max(g[f'I19_{r}'] for r in L.R)

    rec = pd.concat([P[['blk', 'split', 'longitude', 'latitude']].assign(cls='pos'),
                     neg[['blk', 'split', 'longitude', 'latitude']].assign(cls='neg')],
                    ignore_index=True)
    # ---- I2 / I3 / I4(neg): the monotone-under-deletion predicates
    g['I2'] = int((rec.groupby('blk')['split'].nunique() > 1).sum())
    trb = set(rec.loc[rec.split == 'train', 'blk'])
    vn = rec[(rec.split == 'val') & (rec.cls == 'neg')]
    g['I3'] = float(vn.blk.isin(trb).mean()) if len(vn) else 0.0
    s = rec[rec.cls == 'neg']
    kt = set(map(tuple, np.round(s.loc[s.split == 'train',
                                       ['longitude', 'latitude']].values, 5)))
    kv = list(map(tuple, np.round(s.loc[s.split == 'val',
                                        ['longitude', 'latitude']].values, 5)))
    g['I4_neg'] = sum(1 for k in kv if k in kt)

    # ---- I7 (OBS): negative-class validation fraction, per region
    dv = []
    for r in L.R:
        sub = neg[neg.state == r]
        v = abs(100 * (sub.split == 'val').mean() - 20.0) if len(sub) else 20.0
        g[f'I7neg_{r}'] = v; dv.append(v)
    g['I7neg_worst'] = max(dv)
    g['I7neg_pooled'] = abs(100 * (neg.split == 'val').mean() - 20.0)

    # ---- I8 exact predicate
    short = 0
    for (r, sp), n in tg.items():
        short += max(0, n - int(((neg.state == r) & (neg.split == sp)).sum()))
    g['I8_short'] = short
    g['I8_exact'] = int(short == 0 and len(neg) == sum(tg.values()))

    # ---- I10 (OBS): 30 km pos-occupied blocks holding no negative
    for r in L.R:
        p = P[P.state == r]; n = neg[neg.state == r]
        pbk = set(zip(np.floor(p.x_5070 / 30000).astype(int),
                      np.floor(p.y_5070 / 30000).astype(int)))
        nbk = set(zip(np.floor(n.x_5070 / 30000).astype(int),
                      np.floor(n.y_5070 / 30000).astype(int)))
        g[f'I10_{r}'] = len(pbk - nbk) / max(len(pbk), 1)
    g['I10_worst'] = max(g[f'I10_{r}'] for r in L.R)

    # ---- I16b, BOTH readings of "positives union negatives"
    ub = np.array(sorted(set(P.blk.values) | set(Cp.blk.values)))
    bsp = dict(zip(Cp.blk.values, Cp.split.values))
    bsp.update(dict(zip(P.blk.values, P.split.values)))
    isv = np.array([bsp[b] == 'val' for b in ub])
    g['I16b_npool'] = len(ub)
    for k in (4, 8):
        g[f'I16b_pool_k{k}'] = L.moran(ub, isv, k)
    ar = rec.drop_duplicates('blk')
    g['I16b_nsel'] = len(ar)
    for k in (4, 8):
        g[f'I16b_sel_k{k}'] = L.moran(ar.blk.values, (ar.split == 'val').values, k)
    # positives-only reading (I16), for reference
    pbk2 = P.drop_duplicates('blk')
    for k in (4, 8):
        g[f'I16_pos_k{k}'] = L.moran(pbk2.blk.values, (pbk2.split == 'val').values, k)

    # ---- composition of the DELIVERED negatives (ungated today)
    g['nv_share'] = float(neg.is_nonveg.mean())
    for r in L.R:
        sub = neg[neg.state == r]
        g[f'nv_{r}'] = float(sub.is_nonveg.mean()) if len(sub) else np.nan
    g['nv_val'] = float(neg[neg.split == 'val'].is_nonveg.mean())
    g['nv_train'] = float(neg[neg.split == 'train'].is_nonveg.mean())
    g['nv_valtrain_gap'] = abs(g['nv_val'] - g['nv_train'])
    wb = neg.weight_basis.value_counts(normalize=True)
    g['wb_nonveg'] = float(wb.get('NonVeg (hard negative)', 0.0))
    g['wb_prop'] = float(wb.get('Proportional', 0.0))

    # ---- I17 on the NEGATIVES (the reading the CR leaves out) and on
    #      the positives (the reading it specifies)
    for tag, df in (('neg', neg), ('pos', P)):
        ks = {}
        for f in CONT:
            a = df.loc[df.split == 'val', f].dropna()
            b = df.loc[df.split == 'train', f].dropna()
            ks[f] = float(ks_2samp(a, b).statistic) if len(a) > 1 and len(b) > 1 else 0.0
        g[f'ks{tag}_max'] = max(ks.values())
        g[f'ks{tag}_arg'] = max(ks, key=ks.get)
    return g


KEYS_NUM = None


def fair_seed(P, C, sd):
    Pa, Ca, tg, gvf = assign(P, C, sd)
    neg = L.real_draw(Ca, tg, sd)
    g = score(Pa, Ca, neg, tg)
    g['seed'] = sd; g['gvf'] = gvf
    return g
