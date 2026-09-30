"""RESEARCH (read-only): run every committed attack on the FAITHFUL sampler and
score the same statistic vector as res_env_fair.py, over many seeds, so
separation can be judged on BOTH tails (the failure mode that broke I7b/I10:
comparing an attack's single value to a fair maximum)."""
import sys, time
import numpy as np, pandas as pd
from scipy.spatial import cKDTree
import inv_formalC_lib as L
import res_env_core as K

N = int(sys.argv[1]) if len(sys.argv) > 1 else 40
P0, C0 = K.load_all()


# ---------------- pool-shaping attacks (split rule stays fair) -------------
def skew_cells(C, tg, regions, f, G):
    """attack2 / BREAK 10: keep only the southern quantile f of every G-metre
    y-cell, within each (region, split) subpool."""
    sub, ok = [], True
    for (r, s), n in tg.items():
        pool = C[(C.state == r) & (C.split == s)]
        if r in regions and len(pool):
            cell = np.floor(pool.y_5070.values / G)
            lo = pd.Series(pool.y_5070.values).groupby(cell).transform(
                lambda v: v.quantile(f)).values
            k = pool[pool.y_5070.values <= lo]
            nv = int(k.is_nonveg.sum()); hb = len(k) - nv
            n_nv = min(int(round(n * L.NONVEG_MAX_FRAC)), nv)
            if hb < n - n_nv or len(k) < n:
                ok = False
            pool = k
        sub.append(pool)
    return pd.concat(sub, ignore_index=True), ok


def north_strip(C, tg, regions, q):
    """attack5 / BREAK 10A'': the northern (1-q) of ME+VT loses candidates."""
    out = []
    for r in L.R:
        s = C[C.state == r]
        if r in regions and len(s):
            s = s[s.y_5070.values <= np.quantile(s.y_5070.values, q)]
        out.append(s)
    return pd.concat(out, ignore_index=True), True


def starve(C, tg, keep, seed):
    """attack6: habitat candidate pool starved -> quota filled from NonVeg
    beyond the 30 % cap, so I8 stays exact."""
    rng = np.random.default_rng(1000 + seed)
    hab = C[~C.is_nonveg]; nv = C[C.is_nonveg]
    k = hab.iloc[rng.choice(len(hab), int(keep * len(hab)), replace=False)] \
        if keep < 1 else hab
    return pd.concat([k, nv], ignore_index=True), True


def nh_south(C, tg, G=30000.0):
    """inv_fix_breaks Break-1 attack, faithful: NH only, southern half of every
    30 km y-cell."""
    out = []
    for r in L.R:
        s = C[C.state == r]
        if r == 'NH' and len(s):
            cell = np.floor(s.y_5070.values / G)
            med = pd.Series(s.y_5070.values).groupby(cell).transform('median').values
            s = s[s.y_5070.values <= med]
        out.append(s)
    return pd.concat(out, ignore_index=True), True


# ---------------- split-rule attacks (pool stays fair) ---------------------
def rule_east(C, free, gvf, seed):
    """BREAK 2: positive-free blocks sent to val east-first (global ids are
    bx_by, so sorting the id IS sorting on x)."""
    bx = np.floor_divide(free, 1000000)
    sel = set(free[np.argsort(-bx)[:int(round(gvf * len(free)))]])
    return {b: ('val' if b in sel else 'train') for b in free}


def rule_featextremum(feat, k=9):
    """BREAK 10B / attack3: inside every kNN cluster of positive-free blocks,
    send the block ranking highest on `feat` to val.  Salt-and-pepper in
    space -> Moran ~ 0, but the val negatives come from a different feature
    distribution."""
    def f(C, free, gvf, seed):
        fb = C[C.blk.isin(set(free))].groupby('blk')[[feat]].mean()
        fb = fb.reindex(free)
        xy = L.bcentre(fb.index.values)
        v = fb[feat].values
        v = np.where(np.isnan(v), np.nanmin(v) - 1, v)
        _, idx = cKDTree(xy).query(xy, k=k)
        rank = (v[:, None] >= v[idx]).mean(axis=1)
        sel = set(fb.index.values[np.argsort(-rank)[:int(round(gvf * len(free)))]])
        return {b: ('val' if b in sel else 'train') for b in free}
    return f


ATTACKS = {}


def register(name, pool_fn=None, free_rule=None):
    ATTACKS[name] = (pool_fn, free_rule)


for _f in (0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.90):
    register(f'A2_skew_MEVT_f{_f:.2f}_G30km',
             (lambda ff: lambda C, tg, sd: skew_cells(C, tg, ("ME", "VT"), ff, 30000.))(_f))
register('A2_skew_ALL_f0.70_G30km', lambda C, tg, sd: skew_cells(C, tg, ("ME", "NH", "VT"), 0.70, 30000.))
register('A2_skew_ALL_f0.80_G30km', lambda C, tg, sd: skew_cells(C, tg, ("ME", "NH", "VT"), 0.80, 30000.))
register('A2_skew_MEVT_f0.70_G60km', lambda C, tg, sd: skew_cells(C, tg, ("ME", "VT"), 0.70, 60000.))
register('A5_north15pct_loss_MEVT', lambda C, tg, sd: north_strip(C, tg, ("ME", "VT"), 0.85))
register('A5_north15pct_loss_ALL', lambda C, tg, sd: north_strip(C, tg, ("ME", "NH", "VT"), 0.85))
register('A6_starve_hab_keep50', lambda C, tg, sd: starve(C, tg, 0.50, sd))
register('A6_starve_hab_keep10', lambda C, tg, sd: starve(C, tg, 0.10, sd))
register('A6_starve_hab_keep00', lambda C, tg, sd: starve(C, tg, 0.00, sd))
register('B1_NH_south_half_30km', lambda C, tg, sd: nh_south(C, tg))
register('B2_east_first_negsplit', None, rule_east)
register('A3_localmax_road_dist', None, rule_featextremum('road_dist'))
register('A3_localmax_tcc', None, rule_featextremum('tcc'))
register('A3_localmax_balive', None, rule_featextremum('balive'))
register('A3_localmax_tsd', None, rule_featextremum('tsd'))

if __name__ == "__main__":
    only = sys.argv[2:] if len(sys.argv) > 2 else list(ATTACKS)
    rows, t0 = [], time.time()
    for name in only:
        pool_fn, free_rule = ATTACKS[name]
        for sd in range(N):
            Pa, Ca, tg, gvf = K.assign(P0, C0, sd, free_rule=free_rule)
            if pool_fn is not None:
                Cp, ok = pool_fn(Ca, tg, sd)
            else:
                Cp, ok = Ca, True
            neg = L.real_draw(Cp, tg, sd)
            g = K.score(Pa, Cp, neg, tg)
            g['seed'] = sd; g['gvf'] = gvf; g['attack'] = name; g['supply_ok'] = int(ok)
            g['pool_n'] = len(Cp)
            rows.append(g)
        print(f"{name} done  {time.time()-t0:.0f}s", flush=True)
    pd.DataFrame(rows).to_csv(f"{K.SCR}/res_attacks_{N}.csv", index=False)
    print("saved")
