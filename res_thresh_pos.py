"""res_thresh_pos.py -- fair-draw sampling distributions for every
POSITIVE-SIDE gated statistic in CR-0007's acceptance table, over 50+ seeds
of the correct pipeline, plus the values the two committed block-draw attacks
produce.

Correct pipeline (reproduced from prepare_training_data.py, not approximated):
  1. each region's habitat positives (nonveg_landcover == False) whose `state`
     equals the filing region of the file they are in
  2. pool (concat, ignore_index), dedupe on (longitude, latitude)
  3. ONE pooled thin at 30 m with prepare_training_data.thin_by_min_distance
     (seed = the run's seed, exactly as main() passes args.seed to both steps)
  4. 3 km blocks on a GLOBAL EPSG:5070 origin (0,0):
     bx = floor(x/3000), by = floor(y/3000)
  5. val blocks: block_counts = block_id.value_counts();
     block_counts.sample(frac=1, random_state=seed); accumulate whole blocks
     until running >= int(round(0.2*n)) -- i.e. the real loop, break BEFORE add

READ-ONLY on the project.  Output goes to stdout + the scratchpad.
"""
import os, sys, json, time
import numpy as np, pandas as pd
sys.path.insert(0, "/home/ec2-user/grouse2")
os.chdir("/home/ec2-user/grouse2")
import prepare_training_data as P
from res_thresh_prep import load_own_state, thin_fast

SCRATCH = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
REG = ["ME", "NH", "VT"]
BS = 3000.0
VF = 0.2
NSEED = 60          # >= 50 required by PA-0021(c); 60 draws
USE_REAL_THINNER = True


def blocks_of(df, size=BS, origin=(0.0, 0.0)):
    bx = np.floor((df["x_5070"].values - origin[0]) / size).astype(int)
    by = np.floor((df["y_5070"].values - origin[1]) / size).astype(int)
    return pd.Series([f"{a}_{b}" for a, b in zip(bx, by)], index=df.index)


def draw_correct(bid, n, seed, vf=VF, shuffle=True):
    """Exactly prepare_training_data.assign_spatial_blocks' selection loop."""
    bc = bid.value_counts()
    if shuffle:
        order = bc.sample(frac=1, random_state=seed).index.tolist()
    else:
        order = bc.index.tolist()          # BREAK 1: shuffle deleted
    target = int(round(vf * n))
    vb, running = set(), 0
    for b in order:
        if running >= target:
            break
        vb.add(b)
        running += bc[b]
    return vb, bc


def draw_east(df, bid, seed, vf=VF):
    """ATTACK (inv_reviewF_attack_i14): per region, val blocks drawn only from
    the eastern half of that region's occupied blocks, uniformly at random,
    to 20% of that region's records."""
    vb = set()
    rng = np.random.default_rng(seed)
    for r in REG:
        m = (df["state"] == r).values
        sub = bid[m]
        bc = sub.value_counts()
        bx = pd.Series({b: int(b.split("_")[0]) for b in bc.index})
        cut = bx.median()
        elig = [b for b in bc.index if bx[b] >= cut]
        rng.shuffle(elig)
        target = int(round(vf * m.sum()))
        running = 0
        for b in elig:
            if running >= target:
                break
            vb.add(b)
            running += bc[b]
    return vb


def draw_stratified(df, bid, seed, vf=VF):
    """DESIGN CHANGE candidate: the same correct random draw, but run once per
    region so the per-region val fraction is ~exact by construction."""
    vb = set()
    for r in REG:
        m = (df["state"] == r).values
        sub = bid[m]
        bc = sub.value_counts()
        order = bc.sample(frac=1, random_state=seed).index.tolist()
        target = int(round(vf * m.sum()))
        running = 0
        for b in order:
            if running >= target:
                break
            vb.add(b)
            running += bc[b]
    return vb


def stats(df, bid, vb, bc=None):
    if bc is None:
        bc = bid.value_counts()
    split = bid.map(lambda b: "val" if b in vb else "train")
    n = len(df)
    recf = 100.0 * (split == "val").mean()
    nblk = bc.size
    blkf = 100.0 * len(vb) / nblk
    per = {}
    for r in REG:
        m = (df["state"] == r).values
        per[r] = 100.0 * (split[m] == "val").mean()
    out = {
        "n": n,
        "recf": recf,
        "blkf": blkf,
        "i15": abs(blkf - recf),
        "nblk": int(nblk),
        "nvalblk": len(vb),
        "rec_per_valblk": float((split == "val").sum() / max(len(vb), 1)),
        "per_ME": per["ME"], "per_NH": per["NH"], "per_VT": per["VT"],
        "worst_dev20": max(abs(per[r] - 20.0) for r in REG),
        "worst_dev_pooled": max(abs(per[r] - recf) for r in REG),
    }
    return out, split


def main():
    own = load_own_state("lonlat")
    print(f"pooled habitat own-state rows before thin: {len(own)}")
    rows = []
    t0 = time.time()
    for seed in range(NSEED):
        pos = (P.thin_by_min_distance(own, 30, seed) if USE_REAL_THINNER
               else thin_fast(own, 30, seed))
        pos = pos.reset_index(drop=True)
        bid = blocks_of(pos)
        vb, bc = draw_correct(bid, len(pos), seed)
        s, split = stats(pos, bid, vb, bc)
        s["seed"] = seed
        rows.append(s)
        if seed % 10 == 0:
            print(f"  seed {seed:3d}  n={s['n']}  recf={s['recf']:.2f}  "
                  f"i15={s['i15']:.2f}  worst_dev20={s['worst_dev20']:.2f}  "
                  f"({time.time()-t0:.0f}s)")
    fair = pd.DataFrame(rows)
    fair.to_csv(f"{SCRATCH}/res_thresh_fair_pos.csv", index=False)

    def q(col):
        v = fair[col].values
        return dict(min=v.min(), p1=np.percentile(v, 1), p5=np.percentile(v, 5),
                    median=np.median(v), p95=np.percentile(v, 95),
                    p99=np.percentile(v, 99), max=v.max(), mean=v.mean())

    print(f"\n===== FAIR-DRAW ENVELOPE, {NSEED} seeds, positives =====")
    for col in ["n", "recf", "worst_dev20", "worst_dev_pooled", "i15",
                "blkf", "rec_per_valblk", "nblk", "nvalblk",
                "per_ME", "per_NH", "per_VT"]:
        d = q(col)
        print(f"  {col:18s} min {d['min']:9.4f} p1 {d['p1']:9.4f} p5 {d['p5']:9.4f} "
              f"med {d['median']:9.4f} p95 {d['p95']:9.4f} p99 {d['p99']:9.4f} "
              f"max {d['max']:9.4f}")

    print("\n  false-fail rates of the thresholds CR-0007 currently proposes:")
    print(f"    I6  6230 +/- 2%  -> [{6230*0.98:.0f},{6230*1.02:.0f}] : "
          f"{(~fair['n'].between(6230*0.98, 6230*1.02)).sum()}/{NSEED}")
    print(f"    I7  pooled 20% +/- 1 pp                    : "
          f"{(abs(fair['recf']-20)>1).sum()}/{NSEED}")
    for t in (1, 2, 3, 4, 5):
        print(f"    I7  per-region hard +/-{t} pp (dev from 20) : "
              f"{(fair['worst_dev20']>t).sum()}/{NSEED} = "
              f"{100*(fair['worst_dev20']>t).mean():.0f}%")
    for t in (1, 2, 3, 4, 5):
        print(f"    I7' per-region hard +/-{t} pp (dev from POOLED rate): "
              f"{(fair['worst_dev_pooled']>t).sum()}/{NSEED} = "
              f"{100*(fair['worst_dev_pooled']>t).mean():.0f}%")
    for t in (1, 2, 3, 4, 5, 6):
        print(f"    I15 |blockfrac-recfrac| <= {t} pp          : "
              f"{(fair['i15']>t).sum()}/{NSEED} = {100*(fair['i15']>t).mean():.0f}%")

    # ---------------- attacks -----------------
    print("\n===== ATTACK VALUES (same statistics) =====")
    att_rows = []
    for seed in range(12):
        pos = (P.thin_by_min_distance(own, 30, seed) if USE_REAL_THINNER
               else thin_fast(own, 30, seed)).reset_index(drop=True)
        bid = blocks_of(pos)
        # BREAK 1: shuffle deleted -> densest blocks first
        vb1, bc = draw_correct(bid, len(pos), seed, shuffle=False)
        s1, _ = stats(pos, bid, vb1, bc)
        s1.update(attack="break1_no_shuffle", seed=seed)
        att_rows.append(s1)
        # ATTACK: eastern-half val blocks per region
        vb2 = draw_east(pos, bid, seed)
        s2, _ = stats(pos, bid, vb2)
        s2.update(attack="east_half", seed=seed)
        att_rows.append(s2)
        # DESIGN CHANGE: region-stratified correct draw
        vb3 = draw_stratified(pos, bid, seed)
        s3, _ = stats(pos, bid, vb3)
        s3.update(attack="stratified_by_region(design change)", seed=seed)
        att_rows.append(s3)
    att = pd.DataFrame(att_rows)
    att.to_csv(f"{SCRATCH}/res_thresh_attack_pos.csv", index=False)
    for a, g in att.groupby("attack"):
        print(f"\n  {a}  (12 seeds)")
        for col in ["recf", "worst_dev20", "worst_dev_pooled", "i15",
                    "rec_per_valblk", "nvalblk", "per_ME", "per_NH", "per_VT"]:
            print(f"     {col:18s} min {g[col].min():9.4f} med {np.median(g[col]):9.4f} "
                  f"max {g[col].max():9.4f}")
        # seed invariance (I14 ii)
    print("\n  I14(ii) seed-invariance check (exact predicate, not a threshold):")
    pos = (P.thin_by_min_distance(own, 30, 42)).reset_index(drop=True)
    bid = blocks_of(pos)
    a = draw_correct(bid, len(pos), 42, shuffle=False)[0]
    b = draw_correct(bid, len(pos), 7, shuffle=False)[0]
    print(f"    break1 val-block set seed42 == seed7 : {a==b}")
    a = draw_correct(bid, len(pos), 42)[0]
    b = draw_correct(bid, len(pos), 7)[0]
    print(f"    correct val-block set seed42 == seed7 : {a==b}")
    a = draw_east(pos, bid, 42); b = draw_east(pos, bid, 7)
    print(f"    east   val-block set seed42 == seed7 : {a==b}")


if __name__ == "__main__":
    main()
