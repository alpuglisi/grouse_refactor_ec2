"""CR-0006 review, part 3 (read-only): independently re-measure the
motivating defect (BUG-0027) on the CURRENT on-disk splits, and confirm
that per-region block ids collide across regions."""
import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.spatial import cKDTree
from prepare_training_data import assign_spatial_blocks, BOXES

R = ["ME", "NH", "VT"]
t = Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True)
tr, va = [], []
for r in R:
    for lst, name in ((tr, "train"), (va, "val")):
        d = pd.read_csv(f"data/pipeline/{name}_positives_{r}.csv")
        d["region"] = r
        lst.append(d)
tr, va = pd.concat(tr, ignore_index=True), pd.concat(va, ignore_index=True)
for d in (tr, va):
    d["key"] = (d.longitude.round(5).astype(str) + "," +
                d.latitude.round(5).astype(str))
print(f"pooled train {len(tr)} rows / {tr.key.nunique()} coords; "
      f"pooled val {len(va)} rows / {va.key.nunique()} coords")
both = set(tr.key) & set(va.key)
print(f"coords in BOTH pooled train and pooled val: {len(both)}  "
      f"(= {len(va[va.key.isin(both)])} of {len(va)} val rows, "
      f"{len(va[va.key.isin(both)])/len(va):.1%})   CR/BUG-0027 claim: 522 "
      f"of 1674 (31.2%)")
trx, try_ = t.transform(tr.longitude.values, tr.latitude.values)
vax, vay = t.transform(va.longitude.values, va.latitude.values)
d, _ = cKDTree(np.column_stack([trx, try_])).query(
    np.column_stack([vax, vay]), k=1)
for m in (0.5, 30, 300, 3000):
    print(f"  pooled: val with a train positive within {m:>6} m: "
          f"{(d <= m).mean():6.1%}")
for r in R:
    s = va.region == r
    sub_tr = tr[tr.region == r]
    x, y = t.transform(sub_tr.longitude.values, sub_tr.latitude.values)
    dd, _ = cKDTree(np.column_stack([x, y])).query(
        np.column_stack([vax[s.values], vay[s.values]]), k=1)
    print(f"  {r} within-region: val {int(s.sum())}, "
          f"<=30 m {(dd<=30).mean():.1%}, <=300 m {(dd<=300).mean():.1%}")

print("\n=== per-region block ids: does the SAME string mean different "
      "ground in different regions? ===")
ba = {r: pd.read_csv(f"data/pipeline/block_assignments_{r}.csv") for r in R}
for a in R:
    for b in R:
        if a >= b:
            continue
        sa, sb = set(ba[a].block_id), set(ba[b].block_id)
        sh = sa & sb
        conflict = 0
        ma = dict(zip(ba[a].block_id, ba[a].split))
        mb = dict(zip(ba[b].block_id, ba[b].split))
        for k in sh:
            if ma[k] != mb[k]:
                conflict += 1
        print(f"  {a} vs {b}: {len(sa)} vs {len(sb)} block ids, "
              f"{len(sh)} identical strings, {conflict} of them with "
              f"OPPOSITE splits")
# where does block "0_0" sit in each region?
for r in R:
    lo, la, hi, ha = BOXES[r]
    cx, cy = t.transform([lo, hi], [la, ha])
    print(f"  {r}: local grid origin EPSG:5070 ({min(cx):,.0f}, "
          f"{min(cy):,.0f}) -> block '0_0' is a different 3 km cell in "
          f"each region")
print("\ndone")
