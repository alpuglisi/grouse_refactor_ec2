"""res_thresh_neg2.py -- (1) a 400-seed fair-draw tail for the support statistics
(so the p99 is a real quantile and not a 60-draw artefact), and (2) an ATTACK
LADDER: the same "negatives only from the southern slice" attack rescaled from
whole-state down to 3 km, which is exactly the rescaling that defeated I10 at
0.15.  Answers: does ANY threshold on each statistic separate every rung of the
ladder from the fair draw, and which gate catches which rung?

READ-ONLY on the project.
"""
import os, sys, time, warnings
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, "/home/ec2-user/grouse2")
os.chdir("/home/ec2-user/grouse2")
from scipy.spatial import cKDTree
import generate_negatives as GN
from res_thresh_prep import load_own_state, thin_fast
from res_thresh_pos import blocks_of, draw_correct
from res_thresh_neg import (load_pooled_evaluated, draw_negatives, measure,
                            REG, KB)

SCRATCH = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
NFAIR = int(os.environ.get("NFAIR", "400"))
NATT = int(os.environ.get("NATT", "12"))


def main():
    own = load_own_state("lonlat")
    cand0 = pd.read_csv(f"{SCRATCH}/res_thresh_cand_pool.csv")
    ev = load_pooled_evaluated()
    evtree = cKDTree(ev[["x_5070", "y_5070"]].values)

    def south_slice(size, frac):
        resid = cand0["y_5070"].values - size * np.floor(cand0["y_5070"].values / size)
        return pd.Series(resid < size * frac, index=cand0.index)

    sh = pd.Series(False, index=cand0.index)
    for r in REG:
        m = (cand0["state"] == r).values
        cut = np.median(cand0.loc[m, "y_5070"])
        sh[m & (cand0["y_5070"] <= cut).values] = True

    ladder = [
        ("fair", None),
        ("south_half_state", sh),
        ("south_1/6_of_30km", south_slice(30000.0, 1 / 6)),
        ("south_1/2_of_30km", south_slice(30000.0, 1 / 2)),
        ("south_1/6_of_6km", south_slice(6000.0, 1 / 6)),
        ("south_1/2_of_6km", south_slice(6000.0, 1 / 2)),
        ("south_1/6_of_3km", south_slice(3000.0, 1 / 6)),
        ("south_1/2_of_3km", south_slice(3000.0, 1 / 2)),
        ("south_1/6_of_1km", south_slice(1000.0, 1 / 6)),
        ("south_1/2_of_1km", south_slice(1000.0, 1 / 2)),
    ]
    for tag, m in ladder:
        print(f"  pool size {tag:20s}: {len(cand0) if m is None else int(m.sum()):,}")

    rows = []
    t0 = time.time()
    for seed in range(NFAIR):
        pos = thin_fast(own, 30, seed).reset_index(drop=True)
        pbid = blocks_of(pos)
        vb, bc = draw_correct(pbid, len(pos), seed)
        psplit = pbid.map(lambda b: "val" if b in vb else "train")
        blockvf = len(vb) / bc.size
        cnd = thin_fast(cand0, 30, seed)
        d, _ = evtree.query(cnd[["x_5070", "y_5070"]].values, k=1)
        cnd = cnd[d > GN.BUFFER_M].copy()
        cnd["block_id"] = blocks_of(cnd)
        bs = dict(zip(pbid.values, psplit.values))
        cnd["split"] = [bs.get(b) or GN.split_for_unassigned(b, blockvf, seed)
                        for b in cnd["block_id"]]
        for tag, restrict in ladder:
            if tag != "fair" and seed >= NATT:
                continue
            neg = draw_negatives(cnd, pos, psplit, seed, restrict)
            m = measure(pos, psplit, neg)
            m.update(variant=tag, seed=seed, n_pos=len(pos), n_neg=len(neg),
                     shortfall=len(pos) - len(neg))
            rows.append(m)
        if seed % 25 == 0:
            print(f"   seed {seed} ({time.time()-t0:.0f}s)")
    df = pd.DataFrame(rows)
    df.to_csv(f"{SCRATCH}/res_thresh_neg2.csv", index=False)

    cols = ["d_ME", "d_NH", "d_VT", "d_worst", "nn_median", "nn_p90",
            "nn_median_worst_region", "nn_p90_worst_region", "nn_frac_gt_rf",
            "I8_pooled", "shortfall", "I15_bothclass"]
    fair = df[df.variant == "fair"]
    print(f"\n===== FAIR, {len(fair)} seeds =====")
    for c in cols:
        a = fair[c].values.astype(float)
        print(f"  {c:24s} min {a.min():11.4f} p50 {np.median(a):11.4f} "
              f"p95 {np.percentile(a,95):11.4f} p99 {np.percentile(a,99):11.4f} "
              f"p99.5 {np.percentile(a,99.5):11.4f} max {a.max():11.4f}")
    print("\n  d_NH empirical distribution (steps of 1/39):")
    print("   ", fair["d_NH"].value_counts().sort_index().to_dict())
    print("  d_worst empirical distribution:")
    print("   ", fair["d_worst"].round(4).value_counts().sort_index().to_dict())

    print("\n===== ATTACK LADDER =====")
    for tag, _ in ladder:
        if tag == "fair":
            continue
        g = df[df.variant == tag]
        if len(g) == 0:
            continue
        print(f"\n  {tag}  ({len(g)} seeds)")
        for c in cols:
            a = g[c].values.astype(float)
            print(f"     {c:24s} min {a.min():11.4f} med {np.median(a):11.4f} "
                  f"max {a.max():11.4f}")

    print("\n===== which gate catches which rung =====")
    fp = {c: np.percentile(fair[c].values.astype(float), 99) for c in cols}
    gates = {
        "(d) worst-region <= 0.15": ("d_worst", lambda v: v <= 0.15),
        "(d) worst-region <= 0.115": ("d_worst", lambda v: v <= 0.115),
        "nn median pooled <= 2500 m": ("nn_median", lambda v: v <= 2500),
        "nn median worst-region <= 3000 m": ("nn_median_worst_region", lambda v: v <= 3000),
        "nn p90 pooled <= 6000 m": ("nn_p90", lambda v: v <= 6000),
        "nn p90 worst-region <= 7000 m": ("nn_p90_worst_region", lambda v: v <= 7000),
        "frac(nn > 1.92 km) <= 0.60": ("nn_frac_gt_rf", lambda v: v <= 0.60),
        "I8 shortfall == 0 (exact)": ("shortfall", lambda v: v == 0),
    }
    hdr = f"  {'gate':36s} {'fair false-fail':>16s} " + " ".join(
        f"{t[:14]:>15s}" for t, _ in ladder if t != "fair")
    print(hdr)
    for gname, (col, fn) in gates.items():
        ff = 100 * (~fair[col].astype(float).map(fn)).mean()
        cells = []
        for tag, _ in ladder:
            if tag == "fair":
                continue
            g = df[df.variant == tag]
            if len(g) == 0:
                cells.append(f"{'--':>15s}")
                continue
            caught = (~g[col].astype(float).map(fn)).mean()
            cells.append(f"{'CAUGHT' if caught == 1 else ('passes' if caught == 0 else f'{100*caught:.0f}%'):>15s}")
        print(f"  {gname:36s} {ff:15.1f}% " + " ".join(cells))


if __name__ == "__main__":
    main()
