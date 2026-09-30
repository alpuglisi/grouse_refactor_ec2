"""I14 cost: reproduce the recorded split from a manifest.
Components: input digests, own-state+habitat filter, pooled thin,
global block ids, block draw.  READ-ONLY."""
import hashlib, time, sys
import numpy as np, pandas as pd
sys.path.insert(0, "/home/ec2-user/grouse2")
from prepare_training_data import thin_by_min_distance

R = ["ME", "NH", "VT"]
t = time.perf_counter()
digs = {}
for r in R:
    for p in (f"data/pipeline/evaluated_sightings_{r}.csv",
              f"data/negatives/gbif_negatives_{r}.csv"):
        h = hashlib.blake2b(digest_size=16)
        with open(p, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        digs[p] = h.hexdigest()
print(f"input file digests (6 files, blake2b): "
      f"{1000*(time.perf_counter()-t):.0f} ms")

t = time.perf_counter()
ev = pd.concat([pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv")
                .assign(_reg=r) for r in R], ignore_index=True)
hab = ev[(ev.state == ev._reg) & (~ev.nonveg_landcover.astype(bool))]
hab = hab.loc[~hab[["longitude", "latitude", "year"]].duplicated()].copy()
print(f"load + own-state + habitat + dedup: "
      f"{1000*(time.perf_counter()-t):.0f} ms  n={len(hab)}")

t = time.perf_counter()
kept = thin_by_min_distance(hab, 30.0, 42)
t_thin = time.perf_counter() - t
print(f"pooled 30 m thin: {t_thin:.1f}s  kept={len(kept)}")

t = time.perf_counter()
BS = 3000.0
bx = np.floor(kept.x_5070.values / BS).astype(int)
by = np.floor(kept.y_5070.values / BS).astype(int)
bid = pd.Series([f"{a}_{b}" for a, b in zip(bx, by)])
bc = bid.value_counts()
order = bc.sample(frac=1, random_state=42).index.tolist()
target = int(round(0.2 * len(kept)))
vb, run = set(), 0
for b in order:
    if run >= target:
        break
    vb.add(b)
    run += bc[b]
print(f"global block ids + val draw: {1000*(time.perf_counter()-t):.0f} ms  "
      f"{len(bc)} blocks, {len(vb)} val blocks, "
      f"val record frac {run/len(kept):.4f}")
print(f"I14 full reproduction total ~= {t_thin+0.4:.1f}s")
