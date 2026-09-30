"""res_determ_i14.py -- what does I14 actually test?  Run it, as literally
written, against the SHIPPED (pre-CR, known-leaky) artifacts.  Read-only.
"""
import numpy as np, pandas as pd
from scipy.spatial import cKDTree
from prepare_training_data import assign_spatial_blocks
from regions import BOXES

print("=" * 78)
print("I14a, applied literally, to the artifacts that ship TODAY")
print("  'Re-running assign_spatial_blocks from the recorded manifest")
print("   (spacing, block size, origin, seed, val fraction) must reproduce")
print("   the shipped split bit-for-bit'")
print("=" * 78)
for r in ("ME", "NH", "VT"):
    t = pd.read_csv(f"data/pipeline/thinned_positives_{r}.csv")
    bid, sp = assign_spatial_blocks(t, BOXES[r], 3000.0, 0.2, 42)
    mb = int((bid.values != t["block_id"].values).sum())
    ms = int((sp.values != t["split"].values).sum())
    print(f"  {r}: {len(t):,} records -> block_id mismatches {mb}, "
          f"split mismatches {ms}   "
          f"{'BIT-FOR-BIT PASS' if mb == 0 and ms == 0 else 'FAIL'}")

    # I14b: does seed S' give a different val block set?
    _, sp7 = assign_spatial_blocks(t, BOXES[r], 3000.0, 0.2, 7)
    v42 = set(bid[sp == "val"]); v7 = set(bid[sp7 == "val"])
    print(f"     I14b seed 42 vs 7: {'DIFFER -> PASS' if v42 != v7 else 'FAIL'}"
          f"  (Jaccard {len(v42 & v7)/len(v42 | v7):.3f})")

    # and the same file with its rows re-sorted -- same records, same
    # manifest, same seed
    t2 = t.sort_values(["longitude", "latitude"], kind="mergesort").reset_index(drop=True)
    b2, s2 = assign_spatial_blocks(t2, BOXES[r], 3000.0, 0.2, 42)
    key = dict(zip(zip(t["longitude"], t["latitude"]), t["split"]))
    diff = sum(1 for lo, la, s in zip(t2["longitude"], t2["latitude"], s2)
               if key[(lo, la)] != s)
    print(f"     same records, CSV rows re-sorted by (lon,lat): "
          f"{diff:,} of {len(t2):,} records change split "
          f"({100*diff/len(t2):.1f}%) -> I14a FAILS on a pure re-ordering")

print("\n" + "=" * 78)
print("what the shipped, I14a-passing split actually looks like (the defect")
print("CR-0007 exists to fix), measured POOLED across the three regions")
print("=" * 78)
fr = []
for r in ("ME", "NH", "VT"):
    d = pd.read_csv(f"data/pipeline/thinned_positives_{r}.csv")
    d["filed"] = r
    fr.append(d)
p = pd.concat(fr, ignore_index=True)
iv = (p["split"] == "val").values
xy = p[["x_5070", "y_5070"]].values
d, _ = cKDTree(xy[~iv]).query(xy[iv], k=1)
k = lambda a: set(map(tuple, np.round(a, 5)))
ov = len(k(p.loc[~iv, ["longitude", "latitude"]].values)
         & k(p.loc[iv, ["longitude", "latitude"]].values))
print(f"  {len(p):,} pooled records, {iv.sum():,} val")
print(f"  val records with a TRAIN record at the identical coordinate: {ov:,}")
print(f"  median val->nearest-train distance: {np.median(d):.0f} m; "
      f"within 30 m: {(d < 30).mean()*100:.2f}%; within 1920 m: "
      f"{(d < 1920).mean()*100:.2f}%")
print("  -> I14a PASSES on this artifact. I14a is not a correctness test.")
