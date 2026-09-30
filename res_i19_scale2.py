"""RES step 5: the rescaling / sub-region escape, run against the RECOMMENDED
gate (12 cells, each at its own fair mean + Z*sd).

Attack: delete every negative candidate in y-bands of thickness t km repeated
with period G km inside ME+VT (and a val-split-only variant).  t controls how
far a stranded positive is from the nearest surviving candidate (harm per
positive); t/G controls how many positives are stranded (breadth).  Sweeping
both separates 'the gate stopped seeing it' from 'there is nothing left to
see'.  For every rung: does the gate pass on ALL seeds (an escape), and what
harm did the escape buy?   READ-ONLY."""
import sys, numpy as np
from scipy.spatial import cKDTree
import inv_formalC_lib as L
import res_i19_lib as X

NS = int(sys.argv[1]) if len(sys.argv) > 1 else 10
ZZ = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0
P, C = L.load()
F = X.Fixed(P)
CANON = C.copy()
Z = np.load(f"{L.SCR}/res_i19_cal.npz")
STATS = ['Exc', 'S', 'Excws_val', 'Sws_val']
MU = {(s, r): float(np.nanmean(Z[f'obs_{r}_{s}'])) for s in STATS for r in X.R}
SD = {(s, r): float(np.nanstd(Z[f'obs_{r}_{s}'])) for s in STATS for r in X.R}
print(f"recommended gate: {len(STATS)*3} cells, threshold mu + {ZZ}*sd")
for s in STATS:
    print("   " + "  ".join(f"{s}[{r}] <= {MU[(s,r)]+ZZ*SD[(s,r)]:.4f}" for r in X.R))


def bands(Cin, t, G, valonly):
    if t <= 0:
        return Cin
    sel = np.isin(Cin.state.values, ('ME', 'VT'))
    if valonly:
        sel &= (Cin.split.values == 'val')
    return Cin[~(sel & ((Cin.y_5070.values % G) < t))].copy()


def rung(t, G, valonly, NS):
    zs, hs, ok = [], [], True
    for sd in range(NS):
        tg = X.setup(P, CANON, sd)
        neg = L.real_draw(bands(CANON.copy(), t, G, valonly), tg, sd)
        if not all(int(((neg.state == r) & (neg.split == s)).sum()) == n
                   for (r, s), n in tg.items()):
            return None          # fails I8 exact supply: already gated
        st = X.all_stats(F, P, neg, full=False)
        zs.append({(s, r): (st[r][s] - MU[(s, r)]) / SD[(s, r)]
                   for s in STATS for r in X.R})
        h = {}
        for r in X.R:
            Fr = F.reg[r]; m = neg.state.values == r
            nxy = neg.loc[m, ['x_5070', 'y_5070']].values
            d, _ = cKDTree(nxy).query(Fr['xy'], k=1)
            sv = P.split.values[Fr['pos_i']] == 'val'
            nsv = neg.split.values[m] == 'val'
            dv, _ = cKDTree(nxy[nsv]).query(Fr['xy'][sv], k=1)
            h[r] = (int((d > X.RF).sum()), int((d > 2 * X.RF).sum()),
                    float(np.maximum(0, d - X.RF).sum() / 1e3),
                    int((dv > X.RF).sum()),
                    float(np.maximum(0, dv - X.RF).sum() / 1e3))
        hs.append([sum(x[i] for x in h.values()) for i in range(5)])
    zmax = np.array([max(z.values()) for z in zs])
    return zmax, np.median(np.array(hs), axis=0), zs


for valonly in (False, True):
    base = rung(0, 40000., valonly, NS)
    b = base[1]
    print(f"\n\n############ bands in {'the VAL-SPLIT pool only' if valonly else 'the whole pool'}"
          f" of ME+VT, {NS} seeds/rung  ############")
    print(f"  fair baseline: unsupported {b[0]:.0f}, >2RF {b[1]:.0f}, "
          f"total excess {b[2]:.0f} km, val-within-split unsupported {b[3]:.0f}, "
          f"val excess {b[4]:.0f} km")
    print(f"\n{'t km':>5} {'G/t':>4} {'med z':>7} {'min z':>7} {'det%':>5} "
          f"{'d(unsup)':>9} {'d(>2RF)':>8} {'d(exc km)':>10} "
          f"{'d(valunsup)':>12} {'d(valexc km)':>13}  binding cell")
    for t_km in (0.5, 1., 2., 3., 4., 6., 8., 12., 16., 24., 32.):
        for ratio in (2, 4, 8, 16):
            t = t_km * 1000.
            out = rung(t, t * ratio, valonly, NS)
            if out is None:
                print(f"{t_km:>5.1f} {ratio:>4} {'--':>7} {'--':>7} {'I8':>5}"
                      f"   (supply shortfall -- caught by I8, not by this gate)")
                continue
            zmax, hm, zs = out
            det = float((zmax > ZZ).mean())
            bind = max(zs[int(np.argmin(zmax))].items(), key=lambda kv: kv[1])
            print(f"{t_km:>5.1f} {ratio:>4} {np.median(zmax):>7.1f} {zmax.min():>7.1f} "
                  f"{det*100:>4.0f}% "
                  f"{hm[0]-b[0]:>+9.0f} {hm[1]-b[1]:>+8.0f} {hm[2]-b[2]:>+10.0f} "
                  f"{hm[3]-b[3]:>+12.0f} {hm[4]-b[4]:>+13.0f}  "
                  f"{bind[0][0]}[{bind[0][1]}] z={bind[1]:.1f}")
