"""res_determ_whyfail.py -- the shipped split does NOT reproduce today.  Find
out which knob explains it.  Read-only.
"""
import itertools
import numpy as np, pandas as pd
from pyproj import Transformer
from regions import BOXES

BLOCK = 3000.0


def draw(block_id, n, vf, seed, vc_kind="stable", block_order=None):
    counts = block_id.value_counts()
    if vc_kind != "stable":
        enc = block_id.drop_duplicates().tolist()
        counts = counts.reindex(enc).sort_values(ascending=False, kind=vc_kind)
    if block_order == "lexi":
        counts = counts.reindex(sorted(counts.index))
    order = counts.sample(frac=1, random_state=seed).index.tolist()
    target = int(round(vf * n))
    v, run = set(), 0
    for b in order:
        if run >= target:
            break
        v.add(b); run += counts[b]
    return v


for r in ("ME", "NH", "VT"):
    t = pd.read_csv(f"data/pipeline/thinned_positives_{r}.csv")
    bid = pd.Series(t["block_id"].values, index=t.index)
    shipped_val = set(t.loc[t["split"] == "val", "block_id"])
    vf_rec = (t["split"] == "val").mean()
    vf_blk = t.drop_duplicates("block_id")["split"].eq("val").mean()
    print(f"\n{r}: {len(t):,} records, {t['block_id'].nunique():,} blocks, "
          f"shipped val share {100*vf_rec:.3f}% of records / "
          f"{100*vf_blk:.3f}% of blocks, {len(shipped_val):,} val blocks")
    hits = []
    for vc in ("stable", "quicksort", "heapsort"):
        for bo in (None, "lexi"):
            for seed in (42, 7, 1, 0, 123):
                for vf in (0.2, 0.18, 0.22, 0.25, 0.15):
                    v = draw(bid, len(t), vf, seed, vc, bo)
                    if v == shipped_val:
                        hits.append((vc, bo, seed, vf, "EXACT"))
                    elif len(v ^ shipped_val) < 0.05 * len(v | shipped_val):
                        hits.append((vc, bo, seed, vf,
                                     f"near ({len(v ^ shipped_val)} diff)"))
    print("   reproductions found:", hits if hits else "NONE")
    # closest attempt, for scale
    best = None
    for vc in ("stable", "quicksort", "heapsort"):
        for bo in (None, "lexi"):
            v = draw(bid, len(t), 0.2, 42, vc, bo)
            j = len(v & shipped_val) / len(v | shipped_val)
            if best is None or j > best[0]:
                best = (j, vc, bo, len(v), len(v ^ shipped_val))
    print(f"   best Jaccard vs shipped val-block set: {best[0]:.4f} "
          f"(vc={best[1]}, order={best[2]}, {best[3]} blocks drawn, "
          f"sym diff {best[4]})")

    # is the CSV in the order assign_spatial_blocks saw?  Compare block_id
    # first-encounter sequence against the shipped val set structure:
    # reconstruct which block order would have produced the shipped set by
    # greedy fill -- check the shipped val set is even ACHIEVABLE by the
    # greedy rule (i.e. total val records ~= target, no overshoot slack)
    counts = bid.value_counts()
    tot = counts[list(shipped_val)].sum()
    print(f"   shipped val records {tot:,} vs greedy target "
          f"{int(round(0.2*len(t))):,}; last-added block would overshoot by "
          f"{tot - int(round(0.2*len(t))):+,}")
