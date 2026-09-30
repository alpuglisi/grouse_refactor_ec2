"""res_thresh_pos2.py -- follow-ups on the positive-side gates:
  1. 400-seed fair tail for I15 and the per-region val fraction (firms the p99)
  2. the region-stratified block draw over 400 seeds (the design change that
     would make I7's per-region gate nearly exact) -- and how many 3 km blocks
     straddle a state border, which is what would make stratification unclean
  3. BREAK 1b: shuffle KEPT but the shuffled order stable-sorted by block count
     descending.  Seed-varying (so I14(ii) passes) and densest-first (so the
     harm of BREAK 1 is intact) -- the test of whether I15 is redundant given
     I14(ii).
READ-ONLY on the project.
"""
import os, sys, time, warnings
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, "/home/ec2-user/grouse2")
os.chdir("/home/ec2-user/grouse2")
from res_thresh_prep import load_own_state, thin_fast
from res_thresh_pos import blocks_of, draw_correct, draw_stratified, stats, REG


def draw_break1b(bid, n, seed, vf=0.2):
    """shuffle, then stable-sort by count descending -> densest blocks first,
    but the tie order (and hence the val set) still varies with the seed."""
    bc = bid.value_counts()
    sh = bc.sample(frac=1, random_state=seed)
    order = sh.sort_values(ascending=False, kind="stable").index.tolist()
    target = int(round(vf * n))
    vb, run = set(), 0
    for b in order:
        if run >= target:
            break
        vb.add(b)
        run += bc[b]
    return vb


def main():
    own = load_own_state("lonlat")

    # --- straddling blocks -------------------------------------------------
    pos42 = thin_fast(own, 30, 42).reset_index(drop=True)
    b42 = blocks_of(pos42)
    g = pd.DataFrame({"b": b42.values, "s": pos42["state"].values})
    ns = g.groupby("b")["s"].nunique()
    strad = g[g.b.isin(ns[ns > 1].index)]
    print(f"3 km blocks occupied by pooled positives: {ns.size}")
    print(f"  blocks holding >1 state: {(ns>1).sum()} "
          f"({100*(ns>1).mean():.3f}%), holding {len(strad)} records "
          f"({100*len(strad)/len(g):.3f}% of all positives)")
    print(f"  30 km blocks holding >1 state: ", end="")
    b30 = pd.Series([f"{int(np.floor(x/30000))}_{int(np.floor(y/30000))}"
                     for x, y in zip(pos42.x_5070, pos42.y_5070)])
    g30 = pd.DataFrame({"b": b30.values, "s": pos42["state"].values})
    n30 = g30.groupby("b")["s"].nunique()
    print(f"{(n30>1).sum()} of {n30.size}")

    # --- 400-seed fair tail, plus stratified, plus break1b ----------------
    rows = []
    t0 = time.time()
    for seed in range(400):
        pos = thin_fast(own, 30, seed).reset_index(drop=True)
        bid = blocks_of(pos)
        for tag in ("fair", "stratified", "break1b", "break1_noshuffle"):
            if tag == "fair":
                vb, bc = draw_correct(bid, len(pos), seed)
            elif tag == "stratified":
                if seed >= 400:
                    continue
                vb = draw_stratified(pos, bid, seed)
            elif tag == "break1b":
                if seed >= 60:
                    continue
                vb = draw_break1b(bid, len(pos), seed)
            else:
                if seed >= 60:
                    continue
                vb = draw_correct(bid, len(pos), seed, shuffle=False)[0]
            s, _ = stats(pos, bid, vb)
            s.update(variant=tag, seed=seed)
            rows.append(s)
        if seed % 100 == 0:
            print(f"  seed {seed} ({time.time()-t0:.0f}s)")
    df = pd.DataFrame(rows)
    df.to_csv("/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad/res_thresh_pos2.csv", index=False)

    cols = ["i15", "rec_per_valblk", "worst_dev20", "recf", "nvalblk"]
    for v, gg in df.groupby("variant"):
        print(f"\n===== {v} ({len(gg)} seeds) =====")
        for c in cols:
            a = gg[c].values.astype(float)
            print(f"  {c:16s} min {a.min():9.4f} p50 {np.median(a):9.4f} "
                  f"p95 {np.percentile(a,95):9.4f} p99 {np.percentile(a,99):9.4f} "
                  f"p99.5 {np.percentile(a,99.5):9.4f} max {a.max():9.4f}")
    fair = df[df.variant == "fair"]
    print("\nI15 gate false-fail on 400 fair seeds:")
    for t in (1.0, 1.25, 1.5, 2.0, 2.5, 3.0):
        print(f"  <= {t:4.2f} pp : {(fair['i15']>t).sum()}/400 = "
              f"{100*(fair['i15']>t).mean():.2f}%")
    print("rec/valblk gate false-fail on 400 fair seeds:")
    for t in (1.8, 1.9, 2.0, 2.5):
        print(f"  <= {t:4.2f} : {(fair['rec_per_valblk']>t).sum()}/400")
    print("I7 per-region gate false-fail on 400 fair seeds (dev from 20):")
    for t in (1, 2, 3, 4, 4.5, 5, 6):
        print(f"  <= {t} pp : {(fair['worst_dev20']>t).sum()}/400 = "
              f"{100*(fair['worst_dev20']>t).mean():.2f}%")
    st = df[df.variant == "stratified"]
    print("I7 per-region gate false-fail, STRATIFIED draw:")
    for t in (0.5, 0.75, 1, 2):
        print(f"  <= {t} pp : {(st['worst_dev20']>t).sum()}/{len(st)}")

    print("\nI14(ii) seed-variance of each variant (val block set seed42 vs 7):")
    pos = thin_fast(own, 30, 42).reset_index(drop=True)
    bid = blocks_of(pos)
    print(f"  fair              : {draw_correct(bid,len(pos),42)[0]==draw_correct(bid,len(pos),7)[0]}")
    print(f"  break1_noshuffle  : {draw_correct(bid,len(pos),42,shuffle=False)[0]==draw_correct(bid,len(pos),7,shuffle=False)[0]}")
    print(f"  break1b           : {draw_break1b(bid,len(pos),42)==draw_break1b(bid,len(pos),7)}")


if __name__ == "__main__":
    main()
