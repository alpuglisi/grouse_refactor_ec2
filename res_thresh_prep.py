"""res_thresh_prep.py -- build the pooled 'correct pipeline' positive base and
verify that a fast O(n) grid thinner is EXACTLY equivalent to
prepare_training_data.thin_by_min_distance (so 50+ seeds are affordable).

READ-ONLY on the project.  Writes only into the scratchpad.
"""
import os, time, sys
import numpy as np, pandas as pd
from collections import defaultdict
sys.path.insert(0, "/home/ec2-user/grouse2")
import prepare_training_data as P

SCRATCH = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
REG = ["ME", "NH", "VT"]


def load_own_state(dedupe):
    """Each region's habitat positives whose `state` == filing region, pooled,
    deduped.  `dedupe` in {'lonlat', 'lonlatyear'}."""
    frames = []
    for r in REG:
        d = pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv")
        d["_filing_region"] = r
        frames.append(d)
    a = pd.concat(frames, ignore_index=True)
    hab = a[~a["nonveg_landcover"].astype(bool)]
    own = hab[hab["state"] == hab["_filing_region"]]
    sub = ["longitude", "latitude"] if dedupe == "lonlat" else ["longitude", "latitude", "year"]
    own = own.drop_duplicates(subset=sub).reset_index(drop=True)
    return own


def thin_fast(df, min_spacing_m, seed):
    """O(n) occupancy-grid restatement of P.thin_by_min_distance.
    Identical greedy rule: shuffle with default_rng(seed).permutation, keep a
    point iff its distance to every already-kept point is >= min_spacing_m."""
    if len(df) == 0:
        return df
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(df))
    xs = df["x_5070"].values
    ys = df["y_5070"].values
    m = float(min_spacing_m)
    cells = defaultdict(list)
    keep = np.zeros(len(df), bool)
    m2 = m * m
    for i in order:
        cx = int(np.floor(xs[i] / m)); cy = int(np.floor(ys[i] / m))
        ok = True
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for (px, py) in cells.get((cx + dx, cy + dy), ()):
                    if (xs[i] - px) ** 2 + (ys[i] - py) ** 2 < m2:
                        ok = False
                        break
                if not ok:
                    break
            if not ok:
                break
        if ok:
            cells[(cx, cy)].append((xs[i], ys[i]))
            keep[i] = True
    return df[keep].copy()


if __name__ == "__main__":
    os.chdir("/home/ec2-user/grouse2")
    for dedupe in ("lonlat", "lonlatyear"):
        own = load_own_state(dedupe)
        print(f"dedupe={dedupe:12s} pooled habitat own-state rows: {len(own)}")
        t0 = time.time()
        real = P.thin_by_min_distance(own, 30, 42)
        t1 = time.time()
        fast = thin_fast(own, 30, 42)
        t2 = time.time()
        same = (set(real.index) == set(fast.index))
        print(f"   real thinner: {len(real)} in {t1-t0:.1f}s | fast: {len(fast)} in {t2-t1:.1f}s"
              f" | identical index sets: {same}")
        # a couple more seeds for the equivalence claim
        for s in (0, 7, 13):
            a = P.thin_by_min_distance(own, 30, s)
            b = thin_fast(own, 30, s)
            print(f"      seed {s}: real {len(a)} fast {len(b)} identical {set(a.index)==set(b.index)}")
