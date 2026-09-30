"""RES-COMP: the NEGATIVE-class COMPOSITION statistics that CR-0007's
acceptance table has no row for.  Built on top of the validated FORMAL-C
harness (inv_formalC_lib / inv_formalC_pool2) -- nothing here re-implements
the sampler; the draw is L.real_draw verbatim.  READ-ONLY.

Statistic families
  S*  cross-split CONTRAST  (train-neg vs val-neg)        record set: selected negatives
  D*  absolute vs DESIGN CONSTANT                         record set: selected negatives
  Q*  absolute vs the eligible CANDIDATE POOL             record set: selected + pool
  B*  structural / per-block on the negative class        record set: selected negatives
"""
import numpy as np, pandas as pd
from scipy.stats import ks_2samp
import inv_formalC_lib as L

CONT = ["ch", "cc", "tcc", "road_dist", "tsd", "balive", "tpa_live", "qmd",
        "carbon_dwn"]
NVMAX = L.NONVEG_MAX_FRAC          # 0.30
RS = [(r, s) for r in L.R for s in ('train', 'val')]


def load_feat():
    """faithful pool + positives, with the 9 continuous FEATURE_SPEC columns."""
    P, C = L.load()
    FP = pd.read_csv(f"{L.SCR}/fc_feat_pos.csv")
    FC = pd.read_csv(f"{L.SCR}/fc_feat_pool.csv")
    P = pd.concat([P, FP], axis=1)
    C = pd.concat([C, FC], axis=1)
    for d in (P, C):
        d['evt_phys'] = d['envelope_id'].str.split('|').str[0].str.replace(
            'EVT_PHYS:', '', regex=False) if 'envelope_id' in d else 'NA'
    # source-species composition: which GBIF 'other species' observation
    # generated each pseudo-absence.  Present in negatives_{region}.csv as
    # `common_name`; merged back here on the 5dp coordinate key the pipeline
    # itself dedups on.
    kf = lambda d: (d.longitude.round(5).astype(str) + '_'
                    + d.latitude.round(5).astype(str))
    raw = pd.concat([pd.read_csv(f"data/negatives/gbif_negatives_{r}.csv",
                                 low_memory=False,
                                 usecols=['longitude', 'latitude', 'common_name'])
                     for r in L.R], ignore_index=True)
    raw['k'] = kf(raw); raw = raw.drop_duplicates('k')
    C['k'] = kf(C)
    C = C.merge(raw[['k', 'common_name']], on='k', how='left')
    C['weight_true'] = C['weight'].values
    build_wmap(C)
    return P, C


WMAP = {}


def build_wmap(C):
    """Canonical design weight per (region, envelope_id, is_nonveg), recomputed
    from envelope_metrics_{region}.csv through generate_negatives.build_weight --
    the analogue of I11's 'recompute block_id from lon/lat, never read the
    recorded column'."""
    import generate_negatives as GN
    from grouse_data import GrouseData
    d = GrouseData()
    WMAP.clear()
    for r in L.R:
        mm = {row['Envelope']: row for _, row in d[r].envelope_metrics.iterrows()}
        for eid in C.loc[C.state == r, 'envelope_id'].unique():
            for nv in (False, True):
                WMAP[(r, eid, bool(nv))] = GN.build_weight(eid, mm, nv)[0]


def weight_mismatches(df):
    exp = np.array([WMAP.get((r, e, bool(n)), np.nan) for r, e, n
                    in zip(df.state, df.envelope_id, df.is_nonveg)])
    return int(np.sum(~np.isclose(df['weight'].values.astype(float), exp,
                                  rtol=1e-9, atol=1e-12)))


def positive_split(P, seed):
    """CR-0007's global block holdout over the pooled positives."""
    vb = L.val_blocks(P, seed)
    P = P.copy()
    P['split'] = np.where(P.blk.isin(vb), 'val', 'train')
    pblocks = set(P.blk.unique())
    bt = {b: ('val' if b in vb else 'train') for b in pblocks}
    gvf = len(vb) / len(pblocks)
    targets = {(r, s): int(((P.state == r) & (P.split == s)).sum()) for r, s in RS}
    return P, bt, gvf, targets


def _tv(a, b):
    """total-variation distance between two categorical histograms."""
    k = sorted(set(a.index) | set(b.index))
    pa = a.reindex(k).fillna(0.0).values
    pb = b.reindex(k).fillna(0.0).values
    pa = pa / pa.sum() if pa.sum() else pa
    pb = pb / pb.sum() if pb.sum() else pb
    return 0.5 * float(np.abs(pa - pb).sum())


def _ks(a, b):
    a = a[~np.isnan(a)]; b = b[~np.isnan(b)]
    if len(a) < 5 or len(b) < 5:
        return 0.0, 0.0
    d = float(ks_2samp(a, b).statistic)
    return d, d * np.sqrt(len(a) * len(b) / (len(a) + len(b)))


def _smd(a, b):
    a = a[~np.isnan(a)]; b = b[~np.isnan(b)]
    if len(a) < 5 or len(b) < 5:
        return 0.0
    sd = np.sqrt((a.var(ddof=1) * (len(a) - 1) + b.var(ddof=1) * (len(b) - 1))
                 / max(len(a) + len(b) - 2, 1))
    if sd == 0:
        return 0.0
    return float(abs(a.mean() - b.mean()) / (sd * np.sqrt(1 / len(a) + 1 / len(b))))


def supply(C, targets):
    """Pool headroom + whether the beyond-cap NonVeg top-up MUST fire.
    Derived from (pool, targets) exactly as generate_negatives.py:277-289
    derives it -- no re-implementation of the draw."""
    out = {}
    for (r, s), n in targets.items():
        pool = C[(C.state.values == r) & (C.split.values == s)]
        nv = int(pool.is_nonveg.sum()); hb = int((~pool.is_nonveg).sum())
        n_nv_t = min(int(round(n * NVMAX)), nv)
        n_hb_t = n - n_nv_t
        out[(r, s)] = dict(target=n, n_hab_pool=hb, n_nv_pool=nv,
                           n_hab_target=n_hb_t, n_nv_cap=int(round(n * NVMAX)),
                           supply=hb / max(n_hb_t, 1), topup=hb < n_hb_t,
                           shortfall=max(0, n_hb_t - hb))
    return out


def comp_stats(P, C, neg, targets):
    """Every candidate composition statistic, one scalar each."""
    g = {}
    neg = neg.copy()
    sup = supply(C, targets)

    # ---------- D: absolute, vs the design constant --------------------------
    #   record set: SELECTED NEGATIVES, per (region, split).  No pool needed.
    nvc, nvs, short = [], [], []
    for (r, s), n in targets.items():
        sel = neg[(neg.state.values == r) & (neg.split.values == s)]
        cap = int(round(n * NVMAX))
        nvc.append(int(sel.is_nonveg.sum()) - cap)          # <= 0 required
        nvs.append(float(sel.is_nonveg.mean()) if len(sel) else 0.0)
        short.append(n - len(sel))                           # I8
    g['D1_nvexcess_max'] = int(max(nvc))            # exact predicate: <= 0
    g['D2_nvshare_max'] = float(max(nvs))
    g['D3_shortfall_max'] = int(max(short))         # == I8
    g['D4_topup_fired'] = bool(any(v['topup'] for v in sup.values()))
    g['D5_hab_supply_min'] = float(min(v['supply'] for v in sup.values()))
    #   D6: every selected negative's recorded `weight` must equal the weight
    #   recomputed from (envelope_id, is_nonveg, envelope_metrics).  Exact.
    g['D6_weight_mismatch'] = weight_mismatches(neg)

    # ---------- S: cross-split contrast -------------------------------------
    #   record set: SELECTED NEGATIVES ONLY, never pooled with positives.
    def ksblock(df, tag):
        dmax = zmax = 0.0; who = ''
        for f in CONT:
            d, z = _ks(df.loc[df.split == 'val', f].values,
                       df.loc[df.split == 'train', f].values)
            if d > dmax: dmax, who = d, f
            zmax = max(zmax, z)
        return dmax, zmax, who
    d, z, who = ksblock(neg, 'pooled')
    g['S1_ksneg_pooled'], g['S1z_pooled'], g['S1_feat'] = d, z, who
    dm = zm = 0.0; whor = ''
    for r in L.R:
        d, z, who = ksblock(neg[neg.state == r], r)
        if d > dm: dm, whor = d, f"{r}:{who}"
        zm = max(zm, z)
    g['S2_ksneg_region'], g['S2z_region'], g['S2_feat'] = dm, zm, whor
    hab = neg[~neg.is_nonveg]
    d, z, who = ksblock(hab, 'hab')
    g['S3_ksneghab_pooled'], g['S3z_pooled'] = d, z
    dm = zm = 0.0; whor = ''
    for r in L.R:
        d, z, who = ksblock(hab[hab.state == r], r)
        if d > dm: dm, whor = d, f"{r}:{who}"
        zm = max(zm, z)
    g['S4_ksneghab_region'], g['S4z_region'], g['S4_feat'] = dm, zm, whor
    sm = 0.0; whos = ''
    for r in L.R:
        sub = neg[neg.state == r]
        for f in CONT:
            v = _smd(sub.loc[sub.split == 'val', f].values,
                     sub.loc[sub.split == 'train', f].values)
            if v > sm: sm, whos = v, f"{r}:{f}"
    g['S5_smdneg_region'], g['S5_feat'] = sm, whos
    g['S6_nvgap_region'] = max(
        abs(float(neg[(neg.state == r) & (neg.split == 'val')].is_nonveg.mean())
            - float(neg[(neg.state == r) & (neg.split == 'train')].is_nonveg.mean()))
        for r in L.R)
    g['S7_basis_tv_region'] = max(
        _tv(neg[(neg.state == r) & (neg.split == 'val')].weight_basis.value_counts(),
            neg[(neg.state == r) & (neg.split == 'train')].weight_basis.value_counts())
        for r in L.R)
    g['S9_species_tv_split'] = max(
        _tv(neg[(neg.state == r) & (neg.split == 'val')].common_name.value_counts(),
            neg[(neg.state == r) & (neg.split == 'train')].common_name.value_counts())
        for r in L.R)
    sm = 0.0
    for r in L.R:
        sub = neg[neg.state == r]
        d, _ = _ks(sub.loc[sub.split == 'val', 'weight'].values,
                   sub.loc[sub.split == 'train', 'weight'].values)
        sm = max(sm, d)
    g['S10_ksweight_region'] = sm
    g['S8_env_tv_region'] = max(
        _tv(neg[(neg.state == r) & (neg.split == 'val')].envelope_id.value_counts(),
            neg[(neg.state == r) & (neg.split == 'train')].envelope_id.value_counts())
        for r in L.R)

    # ---------- Q: absolute, vs the eligible CANDIDATE POOL -----------------
    #   record set: SELECTED NEGATIVES vs the per-(region,split) eligible pool.
    q_basis, q_smd, q_cov, q_top1, q_nvtv = [], [], [], [], []
    q_wr, q_sp = [], []
    for (r, s) in targets:
        pool = C[(C.state.values == r) & (C.split.values == s)]
        sel = neg[(neg.state.values == r) & (neg.split.values == s)]
        ph, sh = pool[~pool.is_nonveg], sel[~sel.is_nonveg]
        if len(sh) < 20 or len(ph) < 20:
            continue
        w = ph.weight.values
        exp_basis = ph.groupby('weight_basis').weight.sum()
        q_basis.append(_tv(sh.weight_basis.value_counts(), exp_basis))
        for f in CONT:
            x = ph[f].values; ok = ~np.isnan(x)
            if ok.sum() < 20: continue
            mw = np.average(x[ok], weights=w[ok])
            sd = np.sqrt(np.average((x[ok] - mw) ** 2, weights=w[ok]))
            if sd == 0: continue
            q_smd.append(abs(float(sh[f].mean()) - mw) / (sd / np.sqrt(len(sh))))
        q_wr.append(float(sh.weight.mean()) / float(ph.weight.mean()))
        q_sp.append(_tv(sh.common_name.value_counts(), ph.common_name.value_counts()))
        q_cov.append(sh.envelope_id.nunique() / max(ph.envelope_id.nunique(), 1))
        q_top1.append(float(sh.envelope_id.value_counts(normalize=True).iloc[0]))
        pn, sn = pool[pool.is_nonveg], sel[sel.is_nonveg]
        if len(sn) >= 20:
            q_nvtv.append(_tv(sn.evt_phys.value_counts(), pn.evt_phys.value_counts()))
    g['Q1_basis_tv_pool'] = max(q_basis) if q_basis else 0.0
    g['Q2_smd_pool_max'] = max(q_smd) if q_smd else 0.0
    g['Q3_env_cov_min'] = min(q_cov) if q_cov else 1.0
    g['Q4_env_top1_max'] = max(q_top1) if q_top1 else 0.0
    g['Q5_nv_evtphys_tv'] = max(q_nvtv) if q_nvtv else 0.0
    # Q6 two-sided: the realised weighting strength.  1.0 == the draw ignored
    # `weight` entirely; < 1.0 == the weights are inverted.
    g['Q6_wratio_min'] = min(q_wr) if q_wr else 1.0
    g['Q6_wratio_max'] = max(q_wr) if q_wr else 1.0
    g['Q7_species_tv_pool'] = max(q_sp) if q_sp else 0.0

    # ---------- B: structural on the negative class -------------------------
    nb = neg.drop_duplicates('blk')
    g['B1_recs_per_valblock'] = (int((neg.split == 'val').sum())
                                 / max(int((nb.split == 'val').sum()), 1))
    g['B2_blockrec_gap_pp'] = abs(100 * float((nb.split == 'val').mean())
                                  - 100 * float((neg.split == 'val').mean()))
    g['B3_max_recs_one_block'] = int(neg.blk.value_counts().iloc[0])
    return g
