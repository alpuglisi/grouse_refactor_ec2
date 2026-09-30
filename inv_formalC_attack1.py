"""FORMAL C -- BREAK 10, attack 1: I19's per-region fix (v6) closed the POOLED
escape but left an inter-region one.  The fair value of
frac(pos->nearest-neg > 1920 m) differs by 0.14 BETWEEN regions
(VT ~0.426, ME ~0.530, NH ~0.568) and the gate is a SINGLE threshold on the
max.  So the gate is calibrated to NH and hands ME and VT ~0.10-0.21 of free
slack: skew ME and VT (83 % of the positives) and every GATE row stays green.
Uses the REAL two-pool NonVeg-capped weighted_take draw.  READ-ONLY."""
import numpy as np, pandas as pd
from scipy.spatial import cKDTree
import inv_formalC_lib as L

G = 30000.0
P, C = L.load()
vb = L.val_blocks(P, L.SEED)
P['split'] = np.where(P.blk.isin(vb), 'val', 'train')
pb = set(P.blk.unique()); bt = {b: ('val' if b in vb else 'train') for b in pb}
gvf = len(vb)/len(pb)
C['split'] = [bt[b] if b in bt else L.hash_split(b, gvf, L.SEED) for b in C.blk]
L.TARGETS = {(r,s): int(((P.state==r)&(P.split==s)).sum()) for r in L.R for s in ('train','val')}
pool_blocks = C.drop_duplicates('blk')[['blk','split']]
allb = sorted(set(P.blk)|set(C.blk))
print(f"positives {len(P)}  pool {len(C)}  all-record(pool) blocks {len(allb)}")

def skewed(regions, seed=0, frac=0.5):
    sub = []
    for (r,s),n in L.TARGETS.items():
        pool = C[(C.state==r)&(C.split==s)]
        if r in regions:
            cell = np.floor(pool.y_5070.values/G)
            med = pd.Series(pool.y_5070.values).groupby(cell).transform('median').values
            k = pool[pool.y_5070.values <= med]
            # supply check honouring the NonVeg cap
            n_nv = min(int(round(n*L.NONVEG_MAX_FRAC)), int(k.is_nonveg.sum()))
            if (len(k)-int(k.is_nonveg.sum())) >= n-n_nv and len(k) >= n:
                pool = k
            else:
                print(f"   [{r}/{s}] skew pool SHORT ({len(k)} for {n}) -> unskewed")
        sub.append(pool)
    return pd.concat(sub, ignore_index=True)

def harm(neg, tag):
    print(f"  --- harm ({tag}) ---")
    for r in L.R:
        p = P[P.state==r]; n = neg[neg.state==r]
        pbk = set(zip(np.floor(p.x_5070/G).astype(int), np.floor(p.y_5070/G).astype(int)))
        nbk = set(zip(np.floor(n.x_5070/G).astype(int), np.floor(n.y_5070/G).astype(int)))
        d,_ = cKDTree(n[['x_5070','y_5070']].values).query(p[['x_5070','y_5070']].values,k=1)
        # northern-half-of-cell positives: the sub-area the skew strands
        cy = np.floor(p.y_5070.values/G)
        med = pd.Series(p.y_5070.values).groupby(cy).transform('median').values
        north = p.y_5070.values > med
        print(f"    {r}: I10 pos-only 30km blocks {len(pbk-nbk)}/{len(pbk)}="
              f"{len(pbk-nbk)/len(pbk):.4f}   median pos->neg {np.median(d):.0f} m"
              f"   frac>1920m north-half-of-cell {(d[north]>L.RF).mean():.4f}"
              f" vs south {(d[~north]>L.RF).mean():.4f}")

for tag, regs in (("FAIR (no skew)", ()),
                  ("ATTACK 10a: ME+VT southern-half skew (83% of positives)", ("ME","VT")),
                  ("ATTACK 10b: VT-only", ("VT",)),
                  ("prior BREAK 1 attack: NH-only", ("NH",)),
                  ("all three regions (control - expect FAIL)", ("ME","NH","VT"))):
    pool = skewed(regs)
    neg = L.real_draw(pool, L.TARGETS, 0)
    g = L.gate_report(P, neg, pool_blocks=pool_blocks, label=tag)
    print(f"  VERDICT I19 worst {g['I19_worst']:.4f} vs gate 0.64 -> "
          f"{'PASSES GATE' if g['I19_worst']<=0.64 else 'fails gate'}")
    harm(neg, tag)
