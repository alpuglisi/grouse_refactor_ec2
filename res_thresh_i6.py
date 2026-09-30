"""res_thresh_i6.py -- I6 (pooled positive count): fair-draw sampling
distribution over 400 seeds, plus the values every known wrong pipeline
produces, so the band can be set from the distribution instead of a round
number.  Also verifies that thin_fast is EXACTLY thin_by_min_distance on the
pooled negative candidate pool (the substitution that makes 400 seeds
affordable).

READ-ONLY on the project.
"""
import os, sys, time, warnings
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, "/home/ec2-user/grouse2")
os.chdir("/home/ec2-user/grouse2")
import prepare_training_data as P
from res_thresh_prep import load_own_state, thin_fast

SCRATCH = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
REG = ["ME", "NH", "VT"]


def main():
    own = load_own_state("lonlat")
    n = np.array([len(thin_fast(own, 30, s)) for s in range(400)])
    print(f"I6 FAIR, 400 seeds: min {n.min()} p0.5 {np.percentile(n,0.5):.1f} "
          f"p1 {np.percentile(n,1):.1f} p5 {np.percentile(n,5):.1f} "
          f"med {np.median(n)} p95 {np.percentile(n,95):.1f} "
          f"p99 {np.percentile(n,99):.1f} p99.5 {np.percentile(n,99.5):.1f} max {n.max()}")
    print(f"   distribution: {pd.Series(n).value_counts().sort_index().to_dict()}")
    print(f"   relative half-width of observed range: "
          f"{100*(n.max()-n.min())/2/np.median(n):.4f}%")

    print("\nWRONG PIPELINES (seed 42 unless noted):")
    # A. habitat flag / rows taken without the own-state filter (foreign grid)
    frames = []
    for r in REG:
        d = pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv")
        d["_filing_region"] = r
        frames.append(d)
    a = pd.concat(frames, ignore_index=True)
    hab_all = a[~a["nonveg_landcover"].astype(bool)].drop_duplicates(
        subset=["longitude", "latitude"])
    print(f"  A no own-state filter (foreign-grid habitat flag): "
          f"{len(hab_all)} habitat rows -> thin {len(thin_fast(hab_all,30,42))}")
    # A2 the exact chain Impact stated (8422 -> 6702 -> ?)
    ded_all = a.drop_duplicates(subset=["longitude", "latitude"])
    print(f"      (all rows deduped first then habitat: {len(ded_all)} -> "
          f"{len(ded_all[~ded_all['nonveg_landcover'].astype(bool)])} habitat)")
    # B. spacing drift via the surviving --min-spacing-m flag
    for m in (30, 35, 40, 45, 50, 60, 79, 100, 250):
        v = len(thin_fast(own, float(m), 42))
        print(f"  B thin at {m:4d} m: {v}   "
              f"{'INSIDE' if abs(v-6230) <= 0.02*6230 else 'outside'} the +/-2% band "
              f"[{6230*0.98:.0f},{6230*1.02:.0f}]")
    # C. half the dataset silently dropped
    print(f"  C 50% of records dropped: {len(thin_fast(own.iloc[::2],30,42))}")
    print(f"  C 95% kept:               {len(thin_fast(own.sample(frac=0.95,random_state=1),30,42))}")
    print(f"  C 99% kept:               {len(thin_fast(own.sample(frac=0.99,random_state=1),30,42))}")
    # D. per-region thinning (pre-CR) on the same own-state records
    tot = 0
    for r in REG:
        sub = own[own["state"] == r]
        tot += len(thin_fast(sub, 30, 42))
    print(f"  D per-region thin instead of pooled: {tot}")

    print("\nthin_fast vs prepare_training_data.thin_by_min_distance on the "
          "POOLED NEGATIVE CANDIDATE POOL (35,673 rows), seed 42:")
    cand = pd.read_csv(f"{SCRATCH}/res_thresh_cand_pool.csv")
    t0 = time.time()
    f = thin_fast(cand, 30, 42)
    t1 = time.time()
    rr = P.thin_by_min_distance(cand, 30, 42)
    t2 = time.time()
    print(f"  fast {len(f)} in {t1-t0:.1f}s | real {len(rr)} in {t2-t1:.1f}s | "
          f"identical index sets: {set(f.index)==set(rr.index)}")


if __name__ == "__main__":
    main()
