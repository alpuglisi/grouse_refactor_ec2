"""RES: the rescaling (sub-region) escape, run against the RECOMMENDED gate.

Attack family, one knob per axis so the escape is parameterised cleanly:
  strand positives by deleting every negative CANDIDATE in bands of thickness
  t km repeated with period G km (in y, i.e. north-south) inside the named
  regions.  Fraction of positives stranded ~ t/G; distance from a stranded
  positive to the nearest surviving candidate ~ t/4 .. t/2.  So HARM scales
  with t and BREADTH scales with t/G, independently.

For each rung we report every candidate statistic and the true harm, so the
level at which detectability and harm stop decaying together is measured, not
asserted.  A second ladder does the same for the val-split-only variant.
READ-ONLY (scratch writes only)."""
import sys, numpy as np, pandas as pd
from scipy.spatial import cKDTree
import inv_formalC_lib as L
import res_i19_lib as X

NS = int(sys.argv[1]) if len(sys.argv) > 1 else 20
P, C = L.load()
F = X.Fixed(P)
CANON = C.copy()
Z = np.load(f"{L.SCR}/res_i19_cal.npz")


def thr(stat, r, qq=99.5):
    return float(np.percentile(Z[f"obs_{r}_{stat}"], qq))


def bands(C, t, G, regions=('ME', 'VT'), valonly=False):
    keep = np.ones(len(C), bool)
    sel = np.isin(C.state.values, regions)
    if valonly:
        sel &= (C.split.values == 'val')
    y = C.y_5070.values
    keep &= ~(sel & ((y % G) < t))
    return C[keep].copy()


def supply_ok(neg, tg):
    return all(int(((neg.state == r) & (neg.split == s)).sum()) == n
               for (r, s), n in tg.items())


def run(t, G, valonly, NS):
    acc, hh = [], []
    for sd in range(NS):
        tg = X.setup(P, CANON, sd)
        pool = bands(CANON.copy(), t, G, valonly=valonly)
        neg = L.real_draw(pool, tg, sd)
        if not supply_ok(neg, tg):
            return None
        acc.append(X.all_stats(F, P, neg, full=False))
        h = {}
        for r in X.R:
            Fr = F.reg[r]
            m = neg.state.values == r
            nxy = neg.loc[m, ['x_5070', 'y_5070']].values
            d, _ = cKDTree(nxy).query(Fr['xy'], k=1)
            sv = P.split.values[Fr['pos_i']] == 'val'
            nsv = neg.split.values[m] == 'val'
            dv, _ = cKDTree(nxy[nsv]).query(Fr['xy'][sv], k=1)
            h[r] = dict(n_gtRF=int((d > X.RF).sum()), n_gt2RF=int((d > 2 * X.RF).sum()),
                        n_gt10=int((d > 10000).sum()),
                        sum_exc=float(np.maximum(0, d - X.RF).sum() / 1e3),
                        nv_gtRF=int((dv > X.RF).sum()), nv_gt10=int((dv > 10000).sum()),
                        sumv_exc=float(np.maximum(0, dv - X.RF).sum() / 1e3))
        hh.append(h)
    med = {r: {k: float(np.median([a[r][k] for a in acc])) for k in X.STATS}
           for r in X.R}
    hmed = {r: {k: float(np.median([h[r][k] for h in hh])) for k in hh[0][r]}
            for r in X.R}
    return med, hmed


GATED = [('S', None), ('Exc', None), ('Sws_train', None), ('Sws_val', None),
         ('Excws_val', None), ('MorU', None), ('I10p10', None), ('I10b30', None)]

print("thresholds = p99.5 of the 600-seed fair null, per region")
print(f"{'stat':>10} " + "  ".join(f"{r:>18}" for r in X.R))
for st, _ in GATED:
    print(f"{st:>10} " + "  ".join(
        f"{np.median(Z[f'obs_{r}_{st}']):.4f} -> {thr(st,r):.4f}" for r in X.R))

for valonly in (False, True):
    print(f"\n\n########## band ladder, valonly={valonly}, "
          f"period G = 4t (25 % of positives in the band), {NS} seeds ##########")
    print(f"{'t km':>6} {'harm: n(d>RF)':>14} {'n(d>2RF)':>9} {'n(d>10km)':>10} "
          f"{'sum_exc km':>11} | fired gates")
    base = run(0.0, 40000., valonly, NS)
    for t_km in (0.0, 1., 2., 3., 4., 6., 8., 12., 16., 24., 32., 48., 64.):
        t = t_km * 1000.0
        out = run(t, max(4 * t, 4000.), valonly, NS)
        if out is None:
            print(f"{t_km:>6.0f}  -- fails I8 exact supply (already gated)")
            continue
        med, hm = out
        fired = []
        for st, _ in GATED:
            for r in X.R:
                if med[r][st] > thr(st, r):
                    fired.append(f"{st}[{r}]={med[r][st]:.3f}>{thr(st,r):.3f}")
        tot = {k: sum(hm[r][k] for r in X.R) for k in hm['ME']}
        bt = {k: sum(base[1][r][k] for r in X.R) for k in base[1]['ME']}
        print(f"{t_km:>6.0f} {tot['n_gtRF']-bt['n_gtRF']:>+14.0f} "
              f"{tot['n_gt2RF']-bt['n_gt2RF']:>+9.0f} {tot['n_gt10']-bt['n_gt10']:>+10.0f} "
              f"{tot['sum_exc']-bt['sum_exc']:>+11.0f} | "
              + ("; ".join(fired[:6]) if fired else "NONE -- escapes"))
        if valonly:
            print(f"        val-only harm: n(dv>RF) {tot['nv_gtRF']-bt['nv_gtRF']:+.0f} "
                  f"n(dv>10km) {tot['nv_gt10']-bt['nv_gt10']:+.0f} "
                  f"sum_exc {tot['sumv_exc']-bt['sumv_exc']:+.0f} km")
