"""RES (read-only): candidate positive/negative spatial-support gates.

Built on the validated FORMAL C harness (inv_formalC_lib / inv_formalC_pool2):
real weighted_take two-pool NonVeg-capped draw, real 300 m buffer, real
extraction.  Nothing here writes outside the scratchpad.

Candidate statistic families, all computed PER REGION (and per region x split
where noted):

  S        I19 as specified: frac(pos -> nearest same-region neg > 1920 m)
  Exc      mean over positives of max(0, d-1920)/1000   [km of excess]
  Med,P90  median / p90 of d, km
  MorU     Moran's I (k=8 kNN over that region's positives) of the binary
           "unsupported" indicator (d > 1920 m).  Measures whether the
           unsupported positives are CLUSTERED, not how many there are.
  I10b_G   frac of G-metre cells holding positives that hold no negative
           (= I10 as written, at cell size G)
  I10p_G   frac of POSITIVES sitting in a G-metre cell that holds no negative
           (count-weighted I10: step 1/n_pos instead of 1/n_cells)
  KSx,KSy  two-sample KS between positive and negative coordinate marginals
  Cov_RF   frac of positives with no POOL CANDIDATE within 1920 m
           (a property of the candidate pool alone -- no seed, no draw)
  Spos     frac of positives whose nearest OTHER POSITIVE is > 1920 m
           (seed-independent matched reference: "negatives placed at the
           positives", since NEG_RATIO = 1 so n_neg == n_pos)

Two normalisations of any of the above:
  z_frozen  (x - mu_r)/sd_r against that REGION's own fair null, measured
            once over N seeds on the reference pool.   <- frozen null
  z_within  (x - mean_B)/sd_B against B redraws from THIS RUN's own pool,
            same targets, same real draw.              <- within-run null
"""
import numpy as np, pandas as pd
from scipy.spatial import cKDTree
from scipy.stats import ks_2samp
import inv_formalC_lib as L

RF = L.RF
R = L.R
GS = (30000., 10000.)
STATS = ['S', 'Exc', 'Med', 'P90', 'MorU', 'I10b30', 'I10p30',
         'I10b10', 'I10p10', 'KSx', 'KSy', 'S_train', 'S_val',
         'Sws_train', 'Sws_val', 'Excws_val', 'MorUws_val',
         'Rws_train', 'Rws_val', 'R_all', 'Spos_val']


def cellkeys(xy, G):
    return (np.floor(xy[:, 0] / G).astype(np.int64) * 1000000
            + np.floor(xy[:, 1] / G).astype(np.int64))


def moran_bin(ind, knn):
    z = np.asarray(ind, dtype=float)
    z = z - z.mean()
    if z.std() == 0:
        return 0.0
    return float((z[knn].mean(axis=1) * z).sum() / (z ** 2).sum())


class Fixed:
    """Seed-independent per-region positive geometry (positives never move)."""

    def __init__(self, P, k=8):
        self.reg = {}
        for r in R:
            m = (P.state.values == r)
            xy = P.loc[m, ['x_5070', 'y_5070']].values
            t = cKDTree(xy)
            dnn, idx = t.query(xy, k=k + 1)
            self.reg[r] = dict(
                xy=xy, pos_i=np.where(m)[0], knn=idx[:, 1:],
                dpos=dnn[:, 1], Spos=float((dnn[:, 1] > RF).mean()),
                cells={G: cellkeys(xy, G) for G in GS})

    def coverage(self, C):
        """Pool-only adequacy: frac positives with no candidate within RF,
        and frac of G-cells with positives but no candidate.  No draw."""
        out = {}
        for r in R:
            F = self.reg[r]
            c = C.loc[C.state.values == r, ['x_5070', 'y_5070']].values
            if len(c) == 0:
                out[r] = dict(Cov_RF=1.0, Cov30=1.0, Cov10=1.0)
                continue
            d, _ = cKDTree(c).query(F['xy'], k=1)
            o = {'Cov_RF': float((d > RF).mean())}
            for G in GS:
                pc = F['cells'][G]
                nc = set(cellkeys(c, G))
                bad = np.array([k not in nc for k in pc])
                o[f'Cov{int(G/1000)}'] = float(len(set(pc[bad])) / len(set(pc)))
            out[r] = o
        return out


def region_stats(F, xy_neg, split_pos=None, split_neg=None, full=True):
    """All candidate statistics for one region.

    'Sws_*' are the WITHIN-SPLIT readings: I19 as specified takes the nearest
    negative of ANY split, so a val positive counts as supported by a training
    negative 2 km away -- which is not support for anything the val set
    measures.  The within-split reading asks each split's positives about
    their own split's negatives."""
    d, _ = cKDTree(xy_neg).query(F['xy'], k=1)
    u = d > RF
    g = {'S': float(u.mean()),
         'Exc': float(np.maximum(0.0, d - RF).mean() / 1000.0),
         'Med': float(np.median(d) / 1000.0),
         'P90': float(np.quantile(d, 0.90) / 1000.0),
         'MorU': moran_bin(u, F['knn'])}
    for G in GS:
        pc = F['cells'][G]
        nc = set(cellkeys(xy_neg, G))
        bad = np.array([k not in nc for k in pc])
        tag = int(G / 1000)
        g[f'I10b{tag}'] = float(len(set(pc[bad])) / len(set(pc)))
        g[f'I10p{tag}'] = float(bad.mean())
    if full:
        g['KSx'] = float(ks_2samp(F['xy'][:, 0], xy_neg[:, 0]).statistic)
        g['KSy'] = float(ks_2samp(F['xy'][:, 1], xy_neg[:, 1]).statistic)
    else:
        g['KSx'] = g['KSy'] = np.nan
    g['Sws_train'] = g['Sws_val'] = g['Excws_val'] = g['MorUws_val'] = np.nan
    g['Rws_train'] = g['Rws_val'] = g['Spos_val'] = np.nan
    g['R_all'] = float(g['S'] / F['Spos']) if F['Spos'] > 0 else np.nan
    if split_pos is not None:
        for s in ('train', 'val'):
            m = (split_pos == s)
            g[f'S_{s}'] = float(u[m].mean()) if m.any() else np.nan
            if split_neg is not None:
                nm = (split_neg == s)
                if m.any() and nm.any():
                    dw, _ = cKDTree(xy_neg[nm]).query(F['xy'][m], k=1)
                    g[f'Sws_{s}'] = float((dw > RF).mean())
                    # matched positive-only reference: n_neg == n_pos per
                    # (region, split), so 'negatives placed at the positives'
                    # is the exact-density reference draw.  Ratio to it is
                    # region-invariant BY CONSTRUCTION and needs no frozen null.
                    dp, _ = cKDTree(F['xy'][m]).query(F['xy'][m], k=2)
                    sp_ref = float((dp[:, 1] > RF).mean())
                    g[f'Rws_{s}'] = (g[f'Sws_{s}'] / sp_ref) if sp_ref > 0 else np.nan
                    if s == 'val':
                        g['Spos_val'] = sp_ref
                    if s == 'val':
                        g['Excws_val'] = float(np.maximum(0.0, dw - RF).mean() / 1000.0)
                        sub = np.where(m)[0]
                        # kNN among the val positives themselves
                        if m.sum() > 9:
                            _, ix = cKDTree(F['xy'][m]).query(F['xy'][m], k=9)
                            g['MorUws_val'] = moran_bin(dw > RF, ix[:, 1:])
    else:
        g['S_train'] = g['S_val'] = np.nan
    return g


def all_stats(F, P, neg, full=True):
    sp = P['split'].values
    out = {}
    for r in R:
        Fr = F.reg[r]
        m = neg.state.values == r
        nxy = neg.loc[m, ['x_5070', 'y_5070']].values
        if len(nxy) == 0:
            out[r] = {k: np.nan for k in STATS}
            continue
        out[r] = region_stats(Fr, nxy, sp[Fr['pos_i']],
                              neg.split.values[m], full=full)
    return out


def within_null(F, P, pool, targets, B=10, base=900000, full=True):
    """B redraws from THIS pool, same targets -> within-run null per region."""
    acc = {r: {k: [] for k in STATS} for r in R}
    for b in range(B):
        neg = L.real_draw(pool, targets, base + b)
        s = all_stats(F, P, neg, full=full)
        for r in R:
            for k in STATS:
                acc[r][k].append(s[r][k])
    return {r: {k: (float(np.nanmean(v)), float(np.nanstd(v)))
                for k, v in acc[r].items()} for r in R}


def setup(P, C, seed):
    """One fair seed: val blocks from positives, hash split for the rest."""
    vb = L.val_blocks(P, seed)
    P['split'] = np.where(P.blk.isin(vb), 'val', 'train')
    pb = set(P.blk.unique())
    bt = {b: ('val' if b in vb else 'train') for b in pb}
    gvf = len(vb) / len(pb)
    C['split'] = [bt[b] if b in bt else L.hash_split(b, gvf, seed) for b in C.blk]
    L.TARGETS = {(r, s): int(((P.state == r) & (P.split == s)).sum())
                 for r in R for s in ('train', 'val')}
    return dict(L.TARGETS)


def q(a, name=''):
    a = np.asarray(a, dtype=float)
    a = a[~np.isnan(a)]
    return (f"{name:>8} n{len(a):<4} min {a.min():+.4f} p50 {np.median(a):+.4f} "
            f"p95 {np.percentile(a,95):+.4f} p99 {np.percentile(a,99):+.4f} "
            f"max {a.max():+.4f} sd {a.std():.4f}")
