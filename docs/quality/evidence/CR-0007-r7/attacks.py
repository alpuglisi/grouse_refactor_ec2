"""Fair null for I19' cells (my own), then attacks: A1 no-buffer, A2 replace=True,
A3 buffer-inverted (negatives only from near-grouse), checking I19' Z=5, I8, C1, C14."""
import sys, numpy as np, pandas as pd
sys.path.insert(0, "/tmp/claude-1000/-home-ec2-user-grouse2/f462782e-8989-4c4d-919a-db7e5946838a/scratchpad/cr0007_A")
from lib import *
pos = split_positives(pd.read_csv(f"{OUT}/pos_thinned.csv"))
print("pos", len(pos), pos.groupby(['state', 'split']).size().to_dict())
P = pd.read_csv(f"{OUT}/pool_prebuffer.csv", low_memory=False)
P = assign_neg_split(P, pos)
fair_pool = P[P.d_grouse > 300]
NS = int(sys.argv[1]) if len(sys.argv) > 1 else 200

def extra(neg, pool):
    o = {}
    # duplicates within class (5dp), C14 weight ratio, C1 excess
    k = neg.longitude.round(5).astype(str) + neg.latitude.round(5).astype(str)
    o['dups'] = int(k.duplicated().sum())
    hs = neg[~neg.is_nonveg]; hp = pool[~pool.is_nonveg]
    o['C14'] = float(hs.weight.mean() / hp.weight.mean())
    o['min_d_grouse'] = float(neg.d_grouse.min())
    o['n_within300'] = int((neg.d_grouse <= 300).sum())
    return o

rows = []
for s in range(NS):
    n = draw(fair_pool, pos, s)
    rows.append({**i19(pos, n), **extra(n, fair_pool), 'seed': s})
F = pd.DataFrame(rows)
cells = [c for c in F.columns if c.split('_')[0] in ('S', 'Exc', 'Sws', 'Excws')]
mu, sd = F[cells].mean(), F[cells].std()
F.to_csv(f"{OUT}/fair.csv", index=False)
zf = ((F[cells] - mu) / sd).max(axis=1)
print(f"fair: max-cell z p99 {zf.quantile(.99):.2f} max {zf.max():.2f}; ff at Z=5: {(zf > 5).mean():.3f}")
print("fair C14 min", F.C14.min(), "dups max", F.dups.max(), "n_within300 max", F.n_within300.max())
print(F[cells].mean().round(4).to_dict())

def run(name, pool, replace=False, nseeds=20):
    rr = []
    for s in range(1000, 1000 + nseeds):
        n = draw(pool, pos, s, replace=replace)
        rr.append({**i19(pos, n), **extra(n, pool)})
    A = pd.DataFrame(rr)
    z = ((A[cells] - mu) / sd)
    fires = (z.max(axis=1) > 5).mean()
    print(f"\n== {name}: I19' fires {fires:.2f}; max-cell z median {z.max(axis=1).median():.2f}; "
          f"min-cell z median {z.min(axis=1).median():.2f}")
    print("  dups med", A.dups.median(), " C14 med", round(A.C14.median(), 4),
          " n_within300 med", A.n_within300.median(), " min_d med", round(A.min_d_grouse.median(), 1))
    return A

run("A1 no 300m buffer", P)
run("A2 replace=True (dup negatives)", fair_pool, replace=True)
# A3: buffer inverted in weight: prefer candidates within 300-1000 m of grouse (a 'hard-negative' tweak)
P3 = fair_pool.copy(); P3['weight'] = P3.weight * np.where(P3.d_grouse < 1000, 20.0, 1.0)
run("A3 near-grouse upweight x20 (<1 km)", P3)
# A4: negatives drawn only from within 300 m of grouse (label contamination), pool = P[d<=300] + nonveg from fair
P4 = pd.concat([P[P.d_grouse <= 300], fair_pool[fair_pool.is_nonveg]], ignore_index=True)
run("A4 habitat negatives only from inside the 300m exclusion zone", P4)
