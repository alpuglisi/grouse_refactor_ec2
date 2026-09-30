"""RES-COMP: PER-REGION nulls for the cross-split composition statistics.
CR-0007's Break 1 lesson (a pooled statistic hides a one-region skew) applies
to this axis too: a max-over-regions statistic judged against a POOLED null is
dominated by ME.  Each region needs its own envelope.  Also re-tests the
single-region 10B variant with block-consistent split assignment (the earlier
version tripped I2 on border blocks, which is an artefact, not a gate).
READ-ONLY.  usage: python res_comp_region.py NFAIR NATK"""
import sys, time, numpy as np, pandas as pd
from scipy.spatial import cKDTree
from scipy.stats import ks_2samp
import inv_formalC_lib as L
import res_comp_stats as S

NF = int(sys.argv[1]); NA = int(sys.argv[2])
SCR = L.SCR
P0, C0 = S.load_feat()
PBLOCKS = set(P0.blk.unique())
BLK_STATE = C0.groupby('blk')['state'].agg(lambda x: x.value_counts().index[0])
FREE = C0.loc[~C0.blk.isin(PBLOCKS)]
FB = FREE.groupby('blk').agg({f: 'mean' for f in S.CONT})
FB['x'] = L.bcentre(FB.index.values)[:, 0]; FB['y'] = L.bcentre(FB.index.values)[:, 1]
_, KNN = cKDTree(FB[['x', 'y']].values).query(FB[['x', 'y']].values, k=9)
FB_STATE = BLK_STATE.reindex(FB.index).values


def extremum(feat, gvf, only=None):
    """positive-free blocks: send each 9-NN cluster's top-ranked block to val."""
    m = np.ones(len(FB), bool) if only is None else (FB_STATE == only)
    nval = int(round(gvf * m.sum()))
    v = FB[feat].values
    rank = np.array([(v[i] >= v[KNN[i]]).mean() for i in range(len(FB))])
    rank = np.where(m, rank, -1.0)
    sel = set(FB.index.values[np.argsort(-rank)[:nval]])
    return {b: ('val' if b in sel else 'train') for b in FB.index.values[m]}


def pr_stats(neg):
    """the cross-split composition statistics, BROKEN OUT per region."""
    g = {}
    for r in L.R:
        sub = neg[neg.state == r]
        hab = sub[~sub.is_nonveg]
        for tag, d in (('all', sub), ('hab', hab)):
            dm = sm = 0.0; ds = []; ss = []
            for f in S.CONT:
                a = d.loc[d.split == 'val', f].values
                b = d.loc[d.split == 'train', f].values
                dd, _ = S._ks(a, b); dm = max(dm, dd); ds.append(dd)
                v = S._smd(a, b); sm = max(sm, v); ss.append(v)
            g[f'ks_{tag}_{r}'] = dm
            g[f'smd_{tag}_{r}'] = sm
            # AGGREGATE forms: 10B/A7 shift 7 of 9 features at once, so an
            # aggregate over features buys back the power that max-over-9
            # spends on multiplicity.
            g[f'rms_{tag}_{r}'] = float(np.sqrt(np.mean(np.square(ss))))
            g[f'mks_{tag}_{r}'] = float(np.mean(ds))
    return g


def run(tag, seeds, kind=None, arg=None, only=None):
    rows = []
    for seed in seeds:
        P, bt, gvf, tg = S.positive_split(P0, seed)
        C = C0.copy()
        if kind == 'B10B':
            fs = extremum(arg, gvf, only)
            C['split'] = [bt[b] if b in bt else
                          (fs[b] if b in fs else L.hash_split(b, gvf, seed))
                          for b in C.blk]
        else:
            C['split'] = [bt[b] if b in bt else L.hash_split(b, gvf, seed) for b in C.blk]
        if kind == 'A7':
            hab = ~C.is_nonveg.values
            z = ((C[arg] - C[arg].mean()) / C[arg].std()).values
            sgn = np.where(C.split.values == 'val', 1.0, -1.0)
            m = hab if only is None else (hab & (C.state.values == only))
            C.loc[m, 'weight'] = C.loc[m, 'weight'].values * np.exp(3.0 * (z * sgn)[m])
        neg = L.real_draw(C, tg, seed)
        g = pr_stats(neg)
        # block-consistency of the split, to show the attack is artefact-free
        rec = pd.concat([P.assign(cls='pos'), neg.assign(cls='neg')], ignore_index=True)
        g['I2'] = int((rec.groupby('blk')['split'].nunique() > 1).sum())
        g['D6'] = S.weight_mismatches(neg)
        g['tag'] = tag; g['seed'] = seed
        rows.append(g)
    return pd.DataFrame(rows)


t0 = time.time()
import os
if False:
    _P = pd.read_csv(f"{SCR}/rc_region.csv"); F = _P[_P.tag == 'fair'].copy()
else:
    F = run('fair', range(2000, 2000 + NF))
print(f"fair {NF} seeds in {time.time()-t0:.0f}s")
cols = [c for c in F.columns if c.startswith(('ks_','smd_','rms_','mks_'))]
q = F[cols].describe(percentiles=[.5, .99]).T[['min', '50%', '99%', 'max']]
q['GATE(1.30x max)'] = (1.30 * q['max']).round(4)
print("\n=== PER-REGION FAIR NULLS (own null per region) ===")
print(q.round(4).to_string())

ATT = [('B10B_ME(tcc)', 'B10B', 'tcc', 'ME'), ('B10B_NH(tcc)', 'B10B', 'tcc', 'NH'),
       ('B10B_VT(tcc)', 'B10B', 'tcc', 'VT'), ('B10B_all(tcc)', 'B10B', 'tcc', None),
       ('A7_NH(tcc)', 'A7', 'tcc', 'NH'), ('A7_VT(tcc)', 'A7', 'tcc', 'VT')]
out = [F]
for tag, kind, arg, only in ATT:
    A = run(tag, range(2000, 2000 + NA), kind, arg, only); out.append(A)
    print(f"  {tag} done {time.time()-t0:.0f}s", flush=True)
ALL = pd.concat(out, ignore_index=True)
ALL.to_csv(f"{SCR}/rc_region.csv", index=False)

print("\n=== SEPARATION vs each region's OWN null.  cell = attack min/median ===")
print("   free (positive-free candidate) blocks per state: "
      + str(pd.Series(FB_STATE).value_counts().to_dict()))
rows = []
for c in cols + ['I2', 'D6']:
    t = 1.30 * F[c].max() if c in cols else 0
    r = {'stat': c, 'gate': round(float(t), 4)}
    for tag, *_ in ATT:
        v = ALL.loc[ALL.tag == tag, c].values.astype(float)
        nf = int((v > t).sum())
        r[tag] = (f"{v.min():.3g}/{np.median(v):.3g}"
                  f"{'*' if nf == len(v) else ('~' if nf else ' ')}")
    rows.append(r)
T = pd.DataFrame(rows).set_index('stat')
pd.set_option('display.width', 250)
print(T.to_string())
