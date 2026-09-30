"""Independent re-measurement of CR-0007 v5's load-bearing 'today' figures."""
import glob
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from inv_formalA_thin import fast_thin
from inv_formalA_harness import R, T, blk

print("=== 'Why now' figures ===")
tp = {r: pd.read_csv(f"data/pipeline/train_positives_{r}.csv") for r in R}
vp = {r: pd.read_csv(f"data/pipeline/val_positives_{r}.csv") for r in R}
TR = pd.concat(tp.values(), ignore_index=True)
VA = pd.concat(vp.values(), ignore_index=True)
print(f"  pooled train positives {len(TR)}, pooled val positives {len(VA)}")
k5 = lambda d: set(map(tuple, d[['longitude', 'latitude']].round(5).values))
inter = k5(TR) & k5(VA)
vkeys = list(map(tuple, VA[['longitude', 'latitude']].round(5).values))
n_in = sum(1 for k in vkeys if k in k5(TR))
print(f"  val positives whose 5dp coord is also a train positive: {n_in} "
      f"({100*n_in/len(VA):.1f}%)   CR says 522 of 1,674 (31.2%)")
allp = pd.concat([TR, VA], ignore_index=True)
dup = allp[['longitude', 'latitude']].round(5).duplicated(keep=False).sum()
print(f"  duplicated 5dp coords anywhere in the pooled positive set: {dup}")
for r in R:
    e = pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv")
    print(f"  {r}: evaluated {len(e)}, out-of-state by `state` column "
          f"{int((e.state != r).sum())}")
tpool = pd.concat([pd.read_csv(f"data/pipeline/thinned_positives_{r}.csv").assign(_reg=r)
                   for r in R], ignore_index=True)
print(f"  thinned positives pooled {len(tpool)}; out-of-region {(tpool.state != tpool._reg).sum()}")

print("\n=== I1-I4 'today' ===")
xy = tpool[['x_5070', 'y_5070']].values
print(f"  I1 pooled positive pairs < 30 m: "
      f"{len(cKDTree(xy).query_pairs(30.0, output_type='ndarray'))}   CR: 1690")
neg = pd.concat([pd.read_csv(f"data/negatives/negatives_{r}.csv").assign(_reg=r)
                 for r in R], ignore_index=True)
rec = pd.concat([tpool.assign(cls='pos')[['x_5070', 'y_5070', 'split', 'cls']],
                 neg.assign(cls='neg')[['x_5070', 'y_5070', 'split', 'cls']]],
                ignore_index=True)
rec['gblk'] = blk(rec.x_5070.values, rec.y_5070.values)
g = rec.groupby('gblk')['split'].nunique()
print(f"  I2 blocks holding both splits on ONE global grid: {int((g>1).sum())}   CR: 882")
trb = set(rec.loc[rec.split == 'train', 'gblk'])
vn = rec[(rec.split == 'val') & (rec.cls == 'neg')]
print(f"  I3 val negatives whose global block holds a train record: "
      f"{100*vn.gblk.isin(trb).mean():.1f}%   CR: 37.2%")
for c, lbl in ((('pos'), 'pos'), (('neg'), 'neg')):
    s = rec[rec.cls == c]
    kt = set(map(tuple, np.round(s.loc[s.split == 'train', ['x_5070', 'y_5070']].values, 2)))
    kv = list(map(tuple, np.round(s.loc[s.split == 'val', ['x_5070', 'y_5070']].values, 2)))
    print(f"  I4 [{lbl}] train/val coord collisions: {sum(1 for k in kv if k in kt)}   "
          f"CR: 522 pos / 0 neg")

print("\n=== negative pooled-vs-per-region thinning: is 'measured effect today: none' right? ===")
c = pd.concat([pd.read_csv(f"data/negatives/gbif_negatives_{r}.csv") for r in R],
              ignore_index=True)
key = c[['longitude', 'latitude']].round(5)
c = c.loc[~key.duplicated()].copy()
c['x_5070'], c['y_5070'] = T.transform(c.longitude.values, c.latitude.values)
c = c.reset_index(drop=True)
xy = c[['x_5070', 'y_5070']].values
pairs = cKDTree(xy).query_pairs(30.0, output_type='ndarray')
same = (c.state.values[pairs[:, 0]] == c.state.values[pairs[:, 1]])
print(f"  candidate pairs < 30 m: {len(pairs)} total, cross-STATE: {int((~same).sum())}")
pooled = fast_thin(c, 30, 42)
perreg = pd.concat([fast_thin(c[c.state == r].reset_index(drop=True), 30, 42) for r in R],
                   ignore_index=True)
kp = set(map(tuple, pooled[['longitude', 'latitude']].round(5).values))
kr = set(map(tuple, perreg[['longitude', 'latitude']].round(5).values))
print(f"  pooled thin keeps {len(pooled)}; per-region thin keeps {len(perreg)}; "
      f"symmetric difference of the RETAINED SETS: {len(kp ^ kr)}")
negxy = neg[['x_5070', 'y_5070']].values
print(f"  today's SELECTED negatives, pairs < 30 m: "
      f"{len(cKDTree(negxy).query_pairs(30.0, output_type='ndarray'))}")

print("\n=== jitter / constants ===")
import subprocess
for pat, f in (("jitter", "train.py"), ("TIGER", "generate_road_distance.py"),
               ("TIGER", "diagnose_road_bias.py")):
    out = subprocess.run(["grep", "-n", pat, f], capture_output=True, text=True).stdout
    for line in out.splitlines()[:6]:
        print(f"  {f}: {line}")
