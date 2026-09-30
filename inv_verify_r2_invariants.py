"""Author-side verification of reviewer A's BLOCKING R2-1: does v2's
invariant acceptance set pass on a pipeline that violates the PA-0018
pooled-thinning requirement? Read-only.

Non-compliant shape: thin PER REGION, then pool, then one global grid
and one draw. If every invariant still passes, the acceptance set is
inadequate."""
import numpy as np, pandas as pd
from pyproj import Transformer
from scipy.spatial import cKDTree
from grouse_data import GrouseData
from prepare_training_data import thin_by_min_distance

BLOCK_M, VAL_FRAC, SEED, MIN_SP = 3000, 0.2, 42, 30
REGIONS = ["ME", "NH", "VT"]
data = GrouseData()
# NON-COMPLIANT: per-region thin (this is what the on-disk files already are)
parts = []
for r in REGIONS:
    d = data[r].thinned[["longitude", "latitude"]].copy()
    d["src"] = r
    parts.append(d)
pool = pd.concat(parts, ignore_index=True)
t = Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True)
pool["x"], pool["y"] = t.transform(pool.longitude.values, pool.latitude.values)
pool["key"] = pool.longitude.round(5).astype(str) + "," + pool.latitude.round(5).astype(str)
pool = pool.drop_duplicates("key").reset_index(drop=True)      # dedup only, no re-thin
pool["blk"] = (np.floor(pool.x / BLOCK_M).astype(int).astype(str) + "_" +
               np.floor(pool.y / BLOCK_M).astype(int).astype(str))
cnt = pool.blk.value_counts()
order = cnt.sample(frac=1, random_state=SEED).index.tolist()
tgt, val_blocks, run = int(round(VAL_FRAC * len(pool))), set(), 0
for b in order:
    if run >= tgt: break
    val_blocks.add(b); run += cnt[b]
pool["split"] = np.where(pool.blk.isin(val_blocks), "val", "train")
tr, va = pool[pool.split == "train"], pool[pool.split == "val"]
print(f"pooled positives {len(pool)}  blocks {len(cnt)}  val {len(va)} ({len(va)/len(pool):.1%})")
print("\n--- v2's invariant set, evaluated on the NON-COMPLIANT pipeline ---")
coll = len(set(tr.key) & set(va.key))
print(f"  collisions (5dp)                : {coll:6d}      [require 0]        "
      f"{'PASS' if coll==0 else 'FAIL'}")
d, _ = cKDTree(tr[["x","y"]].values).query(va[["x","y"]].values, k=1)
for lim, req in ((30, 0.0), (300, 0.014)):
    got = (d <= lim).mean()
    ok = got <= req + 1e-12
    print(f"  val w/ train within {lim:>4} m       : {got:6.2%}      "
          f"[require <={req:.1%}]  {'PASS' if ok else 'FAIL'}")
vf = len(va)/len(pool)
print(f"  val fraction                    : {vf:6.1%}      [require 20%+-1pp] "
      f"{'PASS' if abs(vf-.2)<=.01 else 'FAIL'}")
print(f"  unique coords == rows           : {pool.key.nunique()}=={len(pool)}   "
      f"{'PASS' if pool.key.nunique()==len(pool) else 'FAIL'}")
print("\n--- the invariant v2 DOES NOT have ---")
pairs = cKDTree(pool[["x","y"]].values).query_pairs(MIN_SP, output_type='ndarray')
print(f"  pairs closer than {MIN_SP} m        : {len(pairs):6d}      [require 0]        "
      f"{'PASS' if len(pairs)==0 else 'FAIL'}")
if len(pairs):
    for i, j in pairs[:3]:
        a, b = pool.iloc[i], pool.iloc[j]
        dm = np.hypot(a.x-b.x, a.y-b.y)
        print(f"     {dm:5.1f} m apart  src {a.src}/{b.src}  splits {a.split}/{b.split}")
    print(f"  records involved: {len(set(pairs.ravel()))}")
