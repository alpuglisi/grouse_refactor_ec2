"""RES: distinct positive/negative-spatial-support attacks, scored on every
candidate statistic over NS seeds.  Mechanisms covered:
  M1 one-region contiguous candidate loss          (A1  committed break 1)
  M2 multi-region contiguous candidate loss        (A2  committed 10A'')
  M3 per-cell (fine-grained) candidate loss        (A3  the rescaling escape)
  M4 dispersed single-site stranding               (A4  built to evade Moran)
  M5 split-asymmetric candidate loss               (A5  val-split only)
  M6 pure draw/weight bias, pool intact            (A6)
READ-ONLY (scratch writes only)."""
import sys, time, pickle, numpy as np, pandas as pd
from scipy.spatial import cKDTree
import inv_formalC_lib as L
import res_i19_lib as X

NS = int(sys.argv[1]) if len(sys.argv) > 1 else 60
B = int(sys.argv[2]) if len(sys.argv) > 2 else 8
P, C = L.load()
F = X.Fixed(P)
CANON = C.copy()


def a_nh_south(C, tg, f=0.5):
    thr = np.quantile(C.loc[C.state == 'NH', 'y_5070'].values, f)
    return C[~((C.state.values == 'NH') & (C.y_5070.values > thr))].copy(), None


def a_mevt_strip(C, tg, q=0.85, regions=('ME', 'VT')):
    keep = np.ones(len(C), bool)
    for r in regions:
        m = C.state.values == r
        thr = np.quantile(C.loc[m, 'y_5070'].values, q)
        keep &= ~(m & (C.y_5070.values > thr))
    return C[keep].copy(), None


def a_mevt_cell(C, tg, f=0.80, G=30000., regions=('ME', 'VT')):
    keep = np.ones(len(C), bool)
    for r in regions:
        m = C.state.values == r
        y = C.loc[m, 'y_5070'].values
        lo = pd.Series(y).groupby(np.floor(y / G)).transform(
            lambda v: v.quantile(f)).values
        drop = np.zeros(len(C), bool)
        drop[np.where(m)[0]] = y > lo
        keep &= ~drop
    return C[keep].copy(), None


def a_disperse(C, tg, rho=10000., sep=3.0):
    """Delete every candidate within rho of scattered single positives, chosen
    >= sep*rho apart, so the stranded positives never neighbour each other."""
    sites = []
    for r in X.R:
        xy = F.reg[r]['xy']
        order = np.argsort(-cKDTree(xy).query(xy, k=9)[0][:, 8])
        ch = []
        for i in order:
            if not ch or np.min(np.hypot(*(xy[i] - np.array(ch)).T)) > sep * rho:
                ch.append(xy[i])
        sites.append(np.array(ch))
    S = np.vstack(sites)
    d, _ = cKDTree(S).query(C[['x_5070', 'y_5070']].values, k=1)
    return C[d > rho].copy(), None


def a_valsplit(C, tg, f=0.5):
    """Split-asymmetric: only the VAL-split candidate pool is confined to the
    southern f of each region.  I19 as specified (a) pools train and val
    positives and (b) takes the nearest negative of ANY split, so a val-only
    defect can barely move it."""
    keep = np.ones(len(C), bool)
    for r in X.R:
        m = (C.state.values == r) & (C.split.values == 'val')
        if m.sum() == 0:
            continue
        thr = np.quantile(C.loc[m, 'y_5070'].values, f)
        keep &= ~(m & (C.y_5070.values > thr))
    return C[keep].copy(), None


def a_selbias(C, tg, Lm=60000.):
    """No pool damage: full pool, canonical weights recomputable; only the
    draw is tampered (southern weight preference)."""
    D = C.copy()
    w = D.weight.values.astype(float).copy()
    for r in X.R:
        m = D.state.values == r
        y = D.y_5070.values[m]
        w[m] = w[m] * np.exp(-(y - y.min()) / Lm)
    D['weight'] = w
    return D, C.copy()


CASES = [
    ('A1 NH-only southern-half [committed break 1]', a_nh_south, dict(f=0.50)),
    ('A2a ME+VT northern-15% candidate loss [committed 10A\'\']', a_mevt_strip, dict(q=0.85)),
    ('A2b ME+VT northern-25% loss [tuned to pass I19<=0.64]', a_mevt_strip, dict(q=0.75)),
    ('A3a ME+VT southern-80% of every 30 km cell [named variant]', a_mevt_cell, dict(f=0.80)),
    ('A3b ME+VT southern-60% of every 30 km cell [tuned]', a_mevt_cell, dict(f=0.60)),
    ('A3c ME+VT southern-60% of every 10 km cell [finer]', a_mevt_cell, dict(f=0.60, G=10000.)),
    ('A4 dispersed stranding rho=2.5 km [anti-Moran]', a_disperse, dict(rho=2500.)),
    ('A4b dispersed stranding rho=8 km sep=2 [anti-Moran]', a_disperse, dict(rho=8000., sep=2.0)),
    ('A5 val-split pool confined to southern 50% [split-asymmetric]', a_valsplit, dict(f=0.50)),
    ('A5b val-split pool confined to southern 25%', a_valsplit, dict(f=0.25)),
    ('A6 pure selection bias Lm=200 km, pool intact', a_selbias, dict(Lm=200000.)),
    ('A6b pure selection bias Lm=100 km, pool intact', a_selbias, dict(Lm=100000.)),
]


def supply_ok(neg, tg):
    return all(int(((neg.state == r) & (neg.split == s)).sum()) == n
               for (r, s), n in tg.items())


def harm(neg, splitv):
    h = {}
    for r in X.R:
        Fr = F.reg[r]
        m = neg.state.values == r
        nxy = neg.loc[m, ['x_5070', 'y_5070']].values
        d, _ = cKDTree(nxy).query(Fr['xy'], k=1)
        u = d > X.RF
        sv = splitv[Fr['pos_i']] == 'val'
        nsv = neg.split.values[m] == 'val'
        dv, _ = cKDTree(nxy[nsv]).query(Fr['xy'][sv], k=1)
        uv = dv > X.RF
        h[r] = dict(n=int(u.sum()), med=float(np.median(d[u]) / 1e3) if u.any() else 0.,
                    nval_ws=int(uv.sum()), medval_ws=float(np.median(dv[uv]) / 1e3) if uv.any() else 0.,
                    nval=int(sv.sum()))
    return h


print("===== FAIR reference (seed 0) =====")
tg0 = X.setup(P, CANON, 0)
neg0 = L.real_draw(CANON, tg0, 0)
s0 = X.all_stats(F, P, neg0)
h0 = harm(neg0, P.split.values)
for r in X.R:
    print(f"  {r}: S {s0[r]['S']:.4f} MorU {s0[r]['MorU']:+.4f} I10b30 {s0[r]['I10b30']:.4f}"
          f" I10p10 {s0[r]['I10p10']:.4f} Sws_val {s0[r]['Sws_val']:.4f}"
          f" | unsupported {h0[r]['n']} med {h0[r]['med']:.1f} km"
          f" | val within-split unsupported {h0[r]['nval_ws']}/{h0[r]['nval']}"
          f" med {h0[r]['medval_ws']:.1f} km")

print(f"\n===== {NS} seeds per case =====")
res = {}
t0 = time.time()
for name, fn, kw in CASES:
    acc = {r: {k: [] for k in X.STATS} for r in X.R}
    zwa = {r: {k: [] for k in X.STATS} for r in X.R}
    hacc, nshort = [], 0
    for sd in range(NS):
        tg = X.setup(P, CANON, sd)
        pool, npool = fn(CANON.copy(), tg, **kw)
        neg = L.real_draw(pool, tg, sd)
        if not supply_ok(neg, tg):
            nshort += 1
            continue
        s = X.all_stats(F, P, neg)
        nul = X.within_null(F, P, npool if npool is not None else pool, tg,
                            B=B, base=700000 + 1000 * sd)
        for r in X.R:
            for k in X.STATS:
                acc[r][k].append(s[r][k])
                m, sdv = nul[r][k]
                zwa[r][k].append((s[r][k] - m) / sdv if sdv > 0 else 0.0)
        hacc.append(harm(neg, P.split.values))
    res[name] = (kw, acc, zwa, hacc, nshort)
    print(f"\n----- {name}   {len(hacc)}/{NS} seeds pass I8 "
          f"(short in {nshort})   {time.time()-t0:.0f}s")
    if not hacc:
        print("   (every seed fails I8 exact supply -> already gated)")
        continue
    for k in X.STATS:
        print(f"   {k:>10} " + "  ".join(
            f"{r} [{np.nanmin(acc[r][k]):+.4f},{np.nanmax(acc[r][k]):+.4f}]"
            for r in X.R))
    for r in X.R:
        n = [h[r]['n'] for h in hacc]
        print(f"   HARM {r}: unsupported {int(np.median(n))}/{len(F.reg[r]['xy'])}"
              f"  med d {np.median([h[r]['med'] for h in hacc]):.1f} km"
              f" | val-within-split {int(np.median([h[r]['nval_ws'] for h in hacc]))}"
              f"/{hacc[0][r]['nval']} med {np.median([h[r]['medval_ws'] for h in hacc]):.1f} km")

with open(f"{L.SCR}/res_i19_attacks.pkl", "wb") as fh:
    pickle.dump(res, fh)
print("\nsaved res_i19_attacks.pkl")
