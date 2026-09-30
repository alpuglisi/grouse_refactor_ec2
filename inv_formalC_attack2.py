"""FORMAL C -- BREAK 10: tuned inter-region escape from the NEW per-region I19.
The gate is ONE threshold (0.64) on the max over regions, but the fair value
differs by 0.15 between regions (VT .426 / ME .530 / NH .568).  So the gate is
calibrated to NH and leaves ME 0.11 and VT 0.21 of free slack.  Skew ME and VT
(83 % of the positives) up to just under 0.64 and every GATE row stays green.
Skew = keep only candidates in the southern fraction f of each G-metre cell,
f tuned to the habitat supply limit.  REAL weighted two-pool draw. READ-ONLY."""
import numpy as np, pandas as pd
from scipy.spatial import cKDTree
import inv_formalC_lib as L

P, C = L.load()
vb = L.val_blocks(P, L.SEED)
P['split'] = np.where(P.blk.isin(vb), 'val', 'train')
pb = set(P.blk.unique()); bt = {b: ('val' if b in vb else 'train') for b in pb}
gvf = len(vb)/len(pb)
C['split'] = [bt[b] if b in bt else L.hash_split(b, gvf, L.SEED) for b in C.blk]
L.TARGETS = {(r,s): int(((P.state==r)&(P.split==s)).sum()) for r in L.R for s in ('train','val')}
pool_blocks = C.drop_duplicates('blk')[['blk','split']]

def skew_pool(regions, f, G):
    sub, ok = [], True
    for (r,s),n in L.TARGETS.items():
        pool = C[(C.state==r)&(C.split==s)]
        if r in regions:
            cell = np.floor(pool.y_5070.values/G)
            lo = pd.Series(pool.y_5070.values).groupby(cell).transform(
                    lambda v: v.quantile(f)).values
            k = pool[pool.y_5070.values <= lo]
            nv = int(k.is_nonveg.sum()); hb = len(k)-nv
            n_nv = min(int(round(n*L.NONVEG_MAX_FRAC)), nv)
            if hb < n - n_nv or len(k) < n: ok = False
            pool = k
        sub.append(pool)
    return pd.concat(sub, ignore_index=True), ok

print("scan: largest southern-quantile skew of ME+VT with adequate habitat supply")
best = None
for G in (30000., 45000., 60000.):
    for f in (0.90,0.85,0.80,0.75,0.70,0.65,0.60,0.55,0.50):
        pool, ok = skew_pool(("ME","VT"), f, G)
        if not ok: continue
        neg = L.real_draw(pool, L.TARGETS, 0)
        v = L.i19(P, neg)
        print(f"  G={G/1000:.0f}km f={f:.2f}  supply OK  I19 ME {v['ME']:.4f} "
              f"NH {v['NH']:.4f} VT {v['VT']:.4f} worst {v['worst']:.4f}"
              f"  {'PASS' if v['worst']<=0.64 else 'FAIL'}")
        if v['worst'] <= 0.64 and (best is None or f < best[1]): best = (G, f)
        break_inner = False
print("\nbest (largest harm) =", best)

G, f = best
pool, _ = skew_pool(("ME","VT"), f, G)
neg_a = L.real_draw(pool, L.TARGETS, 0)
neg_f = L.real_draw(C, L.TARGETS, 0)

def full(tag, neg):
    g = L.gate_report(P, neg, pool_blocks=pool_blocks, label=tag)
    print(f"  ==> every GATE row green? I19 worst {g['I19_worst']:.4f} <= 0.64 : "
          f"{g['I19_worst']<=0.64}")
    for r in L.R:
        p = P[P.state==r]; n = neg[neg.state==r]
        d,_ = cKDTree(n[['x_5070','y_5070']].values).query(p[['x_5070','y_5070']].values,k=1)
        cy = np.floor(p.y_5070.values/G)
        thr = pd.Series(p.y_5070.values).groupby(cy).transform(lambda v: v.quantile(f)).values
        strand = p.y_5070.values > thr
        pbk = set(zip(np.floor(p.x_5070/30000).astype(int), np.floor(p.y_5070/30000).astype(int)))
        nbk = set(zip(np.floor(n.x_5070/30000).astype(int), np.floor(n.y_5070/30000).astype(int)))
        print(f"    {r}: median pos->nearest-neg {np.median(d):>6.0f} m | "
              f"stranded band ({100*(1-f):.0f}% of every {G/1000:.0f} km cell, "
              f"n={strand.sum():>4}) frac>1920m {(d[strand]>L.RF).mean():.4f}"
              f"  rest {(d[~strand]>L.RF).mean():.4f} | I10 {len(pbk-nbk)}/{len(pbk)}"
              f"={len(pbk-nbk)/len(pbk):.4f}")
    return g

gf = full("A: FAIR (intended pipeline)", neg_f)
ga = full(f"B: BREAK 10 - ME+VT southern-{f:.0%} skew at {G/1000:.0f} km", neg_a)
