"""res_thresh_shift.py -- the gate CR-0007 has NO row for: train/val covariate
shift.  The eastern-half val-block attack (inv_reviewF_attack_i14.py) passes
every I1-I15 row including a hard per-region I7; nothing in the acceptance set
measures what it breaks.  Calibrates candidate statistics against 400 fair
seeds and the two committed block-draw attacks.

Statistics:
  KS_x, KS_y   : two-sample KS statistic between val and train positives on
                 x_5070 / y_5070 (per region, worst region reported)
  dmed_x       : |median(val x) - median(train x)| in metres, worst region
  KS_dens      : KS on spatial_density (the statistic BREAK 1 moves)
READ-ONLY on the project.
"""
import os, sys, time, warnings
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, "/home/ec2-user/grouse2")
os.chdir("/home/ec2-user/grouse2")
from scipy.stats import ks_2samp
from res_thresh_prep import load_own_state, thin_fast
from res_thresh_pos import blocks_of, draw_correct, draw_east, draw_stratified, REG
from res_thresh_pos2 import draw_break1b

SCRATCH = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"


def shift_stats(pos, split):
    out = {}
    for tag, col in (("KS_x", "x_5070"), ("KS_y", "y_5070"),
                     ("KS_dens", "spatial_density")):
        if col not in pos.columns:
            continue
        worst = 0.0
        for r in REG:
            m = (pos["state"] == r).values
            v = pos.loc[m & (split == "val").values, col].dropna()
            t = pos.loc[m & (split == "train").values, col].dropna()
            if len(v) > 10 and len(t) > 10:
                worst = max(worst, ks_2samp(v, t).statistic)
        out[tag + "_worstreg"] = worst
        v = pos.loc[(split == "val").values, col].dropna()
        t = pos.loc[(split == "train").values, col].dropna()
        out[tag + "_pooled"] = ks_2samp(v, t).statistic
    worst = 0.0
    for r in REG:
        m = (pos["state"] == r).values
        v = pos.loc[m & (split == "val").values, "x_5070"]
        t = pos.loc[m & (split == "train").values, "x_5070"]
        worst = max(worst, abs(np.median(v) - np.median(t)))
    out["dmed_x_worstreg_m"] = worst
    return out


def main():
    own = load_own_state("lonlat")
    rows = []
    t0 = time.time()
    for seed in range(400):
        pos = thin_fast(own, 30, seed).reset_index(drop=True)
        bid = blocks_of(pos)
        variants = {"fair": draw_correct(bid, len(pos), seed)[0]}
        if seed < 24:
            variants["east_half"] = draw_east(pos, bid, seed)
            variants["break1_noshuffle"] = draw_correct(bid, len(pos), seed, shuffle=False)[0]
            variants["break1b_sorted"] = draw_break1b(bid, len(pos), seed)
            variants["stratified"] = draw_stratified(pos, bid, seed)
        for tag, vb in variants.items():
            split = bid.map(lambda b: "val" if b in vb else "train")
            s = shift_stats(pos, split)
            s.update(variant=tag, seed=seed)
            rows.append(s)
        if seed % 100 == 0:
            print(f"  seed {seed} ({time.time()-t0:.0f}s)")
    df = pd.DataFrame(rows)
    df.to_csv(f"{SCRATCH}/res_thresh_shift.csv", index=False)
    cols = [c for c in df.columns if c not in ("variant", "seed")]
    for v, g in df.groupby("variant"):
        print(f"\n===== {v} ({len(g)} seeds) =====")
        for c in cols:
            a = g[c].values.astype(float)
            print(f"  {c:22s} min {a.min():10.4f} p50 {np.median(a):10.4f} "
                  f"p95 {np.percentile(a,95):10.4f} p99 {np.percentile(a,99):10.4f} "
                  f"max {a.max():10.4f}")
    fair = df[df.variant == "fair"]
    print("\nseparation check (fair p99 / fair max vs each attack's min):")
    for c in cols:
        fp99 = np.percentile(fair[c].astype(float), 99)
        fmax = fair[c].astype(float).max()
        line = f"  {c:22s} fair p99 {fp99:9.4f} max {fmax:9.4f} |"
        for v in ("east_half", "break1_noshuffle", "break1b_sorted", "stratified"):
            g = df[df.variant == v]
            if len(g):
                line += f" {v[:12]} min {g[c].astype(float).min():9.4f}"
        print(line)


if __name__ == "__main__":
    main()
