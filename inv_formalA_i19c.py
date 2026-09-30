"""I19 sensitivity: does the envelope-weighted / NonVeg-capped draw sit lower
than a uniform draw at the same count? Controls for count and positive set."""
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from inv_formalA_harness import R, SEED, blk, val_blocks_fair, hash_split

SCR = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
cand = pd.read_pickle(f"{SCR}/cand.pkl")
pos = pd.read_pickle(f"{SCR}/pos.pkl")
RF = 1920.0

tp = pd.concat([pd.read_csv(f"data/pipeline/thinned_positives_{r}.csv") for r in R],
               ignore_index=True)
neg = pd.concat([pd.read_csv(f"data/negatives/negatives_{r}.csv") for r in R],
                ignore_index=True)
TPXY = tp[['x_5070', 'y_5070']].values
PPXY = pos[['x_5070', 'y_5070']].values


def f(xy, ref):
    d, _ = cKDTree(xy).query(ref, k=1)
    return float((d > RF).mean())


print("--- control 1: same reference positives (today's thinned, n=%d) ---" % len(tp))
print(f"  ACTUAL weighted negatives n={len(neg)}: I19 = {f(neg[['x_5070','y_5070']].values, TPXY):.4f}")
rng = np.random.default_rng(0)
u = [f(cand.iloc[rng.choice(len(cand), 8365, replace=False)][['x_5070', 'y_5070']].values, TPXY)
     for _ in range(30)]
print(f"  UNIFORM draw of 8365 from the pooled eligible pool: p50 {np.median(u):.4f} "
      f"min {min(u):.4f} max {max(u):.4f}")
print(f"  -> weighting/NonVeg-cap effect at matched count and reference: "
      f"{f(neg[['x_5070','y_5070']].values, TPXY) - np.median(u):+.4f}")

print("\n--- control 2: what does a WEIGHTED-pattern draw of only 6,230 look like? ---")
print("    (subsample today's actual weighted negatives down to 6,230, so the")
print("     weighted spatial pattern is preserved and only the count changes)")
sub = []
for _ in range(60):
    s = neg.iloc[rng.choice(len(neg), 6230, replace=False)]
    sub.append(f(s[['x_5070', 'y_5070']].values, PPXY))
sub = np.array(sub)
print(f"  vs post-partition positives (n={len(pos)}): p50 {np.median(sub):.4f} "
      f"p99 {np.percentile(sub,99):.4f} max {sub.max():.4f}")
allneg = f(neg[['x_5070', 'y_5070']].values, PPXY)
print(f"  all 8,365 weighted negatives vs same positives: {allneg:.4f}")
print(f"  -> pure count effect 8365->6230 on a weighted pattern: {np.median(sub)-allneg:+.4f}")

print("\n--- control 3: uniform draw of 6,230 (ignoring split constraint) ---")
u2 = [f(cand.iloc[rng.choice(len(cand), 6230, replace=False)][['x_5070', 'y_5070']].values, PPXY)
      for _ in range(60)]
print(f"  p50 {np.median(u2):.4f} max {max(u2):.4f}")

print("\n--- summary: best estimate of the WEIGHTED post-CR 1:1 I19 envelope ---")
print("   uniform post-CR 1:1 (measured, 300 seeds): p50 0.5438  max 0.5657")
print(f"   weighting offset (control 1): {f(neg[['x_5070','y_5070']].values, TPXY) - np.median(u):+.4f}")
print(f"   => weighted post-CR 1:1 estimate: p50 ~"
      f"{0.5438 + (f(neg[['x_5070','y_5070']].values, TPXY) - np.median(u)):.4f}")
