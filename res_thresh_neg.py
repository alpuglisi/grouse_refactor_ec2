"""res_thresh_neg.py -- Phase B: fair-draw sampling distributions for the
NEGATIVE-DEPENDENT gated statistics of CR-0007 (I8, I7-negatives, I10/(d), and
I10's proposed replacement = positive->nearest-negative distance), plus the
values the two committed spatial-support attacks produce.

Per seed, the whole post-CR pipeline is re-run:
  positives : own-state habitat, pooled, deduped, ONE 30 m pooled thin at that
              seed, 3 km blocks on origin (0,0), block draw to ~20%
  negatives : cached weighted candidate pool (res_thresh_negprep.py), pooled
              30 m thin at that seed, 300 m pooled buffer against every pooled
              own-state evaluated sighting, global 3 km block ids, split taken
              from the positive block table else the md5 hash split at the
              GLOBAL block-level val rate, then the real two-pool weighted
              draw (NonVeg capped at 30%) to a 1:1 per-region per-split target.

Attacks (negative-side spatial support):
  south_half  : reviewer D (inv_reviewD_cr7b.py) -- candidates restricted to the
                southern half of each state
  south_sixth : the rescaled attack CR-0007 records as passing I10 at 0.15 --
                candidates restricted to the southern sixth of each 30 km block

READ-ONLY on the project.
"""
import os, sys, time, hashlib, warnings
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, "/home/ec2-user/grouse2")
os.chdir("/home/ec2-user/grouse2")
from scipy.spatial import cKDTree
from pyproj import Transformer
import generate_negatives as GN
from res_thresh_prep import load_own_state, thin_fast
from res_thresh_pos import blocks_of, draw_correct

SCRATCH = "/tmp/claude-1000/-home-ec2-user-grouse2/c7549c28-707b-493c-9502-4fa7b4eaff65/scratchpad"
REG = ["ME", "NH", "VT"]
BS, KB, VF = 3000.0, 30000.0, 0.2
NSEED = int(os.environ.get("NSEED", "60"))
RF_M = 1920.0      # receptive field, CR-0007 I10 replacement


def load_pooled_evaluated():
    """Every pooled own-state evaluated row (habitat AND non-veg) -- the 300 m
    buffer in generate_negatives buffers 'vegetated and non-veg alike'."""
    fr = []
    for r in REG:
        d = pd.read_csv(f"data/pipeline/evaluated_sightings_{r}.csv")
        d = d[d["state"] == r]
        fr.append(d[["longitude", "latitude", "x_5070", "y_5070"]])
    return pd.concat(fr, ignore_index=True)


def kblocks(x, y, size=KB):
    return set(zip(np.floor(x / size).astype(int), np.floor(y / size).astype(int)))


def draw_negatives(cand, pos, psplit, seed, restrict=None):
    """The real two-pool weighted draw. `restrict` is a boolean mask over cand
    applied to the eligible pool only (the attack)."""
    rng = np.random.default_rng(seed)
    picked = []
    for r in REG:
        pm = (pos["state"] == r).values
        for sp in ("train", "val"):
            need = int(round(float((pm & (psplit == sp).values).sum()) * GN.NEG_RATIO))
            pool = cand[(cand["state"] == r) & (cand["split"] == sp)]
            if restrict is not None:
                pool = pool[restrict.reindex(pool.index).fillna(False).values]
            if len(pool) == 0:
                continue
            nvp = pool[pool["is_nonveg"]]
            hbp = pool[~pool["is_nonveg"]]
            n_nv = min(int(round(need * GN.NONVEG_MAX_FRAC)), len(nvp))
            n_hb = need - n_nv

            def take(sub, n):
                if n <= 0 or len(sub) == 0:
                    return sub.iloc[0:0]
                if len(sub) <= n:
                    return sub
                p = sub["weight"].values / sub["weight"].sum()
                idx = rng.choice(sub.index.values, size=n, replace=False, p=p)
                return sub.loc[idx]

            th = take(hbp, n_hb)
            short = n_hb - len(th)
            if short > 0:
                n_nv = min(n_nv + short, len(nvp))
            tn = take(nvp, n_nv)
            got = pd.concat([th, tn])
            picked.append(got.assign(split=sp))
    return pd.concat(picked, ignore_index=True)


def measure(pos, psplit, neg):
    out = {}
    # --- I7 / I8
    nsp = neg["split"].values
    out["neg_valfrac"] = 100.0 * (nsp == "val").mean()
    npos_val = int((psplit == "val").sum())
    nneg_val = int((nsp == "val").sum())
    out["I8_pooled"] = nneg_val / max(npos_val, 1)
    worst8 = 0.0
    worst7 = 0.0
    for r in REG:
        pm = (pos["state"] == r).values
        nm = (neg["state"] == r).values
        pv = int((pm & (psplit == "val").values).sum())
        nv = int((nm & (nsp == "val")).sum())
        out[f"I8_{r}"] = nv / max(pv, 1)
        out[f"negval_{r}"] = 100.0 * (nsp[nm] == "val").mean()
        worst8 = max(worst8, abs(out[f"I8_{r}"] - 1.0))
        worst7 = max(worst7, abs(out[f"negval_{r}"] - 20.0))
    out["I8_worst_dev"] = worst8
    out["I7neg_worst_dev20"] = worst7
    # --- (d) / I10 support
    worst_d = 0.0
    for r in REG:
        p = pos[pos["state"] == r]
        n = neg[neg["state"] == r]
        Pb = kblocks(p["x_5070"].values, p["y_5070"].values)
        Nb = kblocks(n["x_5070"].values, n["y_5070"].values)
        v = len(Pb - Nb) / max(len(Pb), 1)
        out[f"d_{r}"] = v
        out[f"dU_{r}"] = len(Pb - Nb) / max(len(Pb | Nb), 1)
        out[f"nposblk_{r}"] = len(Pb)
        worst_d = max(worst_d, v)
    out["d_worst"] = worst_d
    # --- I10 replacement: positive -> nearest selected negative distance
    tree = cKDTree(neg[["x_5070", "y_5070"]].values)
    dist, _ = tree.query(pos[["x_5070", "y_5070"]].values, k=1)
    out["nn_median"] = float(np.median(dist))
    out["nn_p90"] = float(np.percentile(dist, 90))
    out["nn_p95"] = float(np.percentile(dist, 95))
    out["nn_frac_gt_rf"] = float((dist > RF_M).mean())
    wm, wp = 0.0, 0.0
    for r in REG:
        pm = (pos["state"] == r).values
        d = dist[pm]
        out[f"nnmed_{r}"] = float(np.median(d))
        out[f"nnp90_{r}"] = float(np.percentile(d, 90))
        wm = max(wm, out[f"nnmed_{r}"]); wp = max(wp, out[f"nnp90_{r}"])
    out["nn_median_worst_region"] = wm
    out["nn_p90_worst_region"] = wp
    # --- I15 computed over BOTH classes pooled (the other reading of I15)
    allb = pd.concat([
        pd.Series(blocks_of(pos).values), pd.Series(blocks_of(neg).values)])
    allsp = np.concatenate([psplit.values, nsp])
    recf = 100.0 * (allsp == "val").mean()
    dfb = pd.DataFrame({"b": allb.values, "s": allsp})
    per = dfb.drop_duplicates("b")
    blkf = 100.0 * (per["s"] == "val").mean()
    out["I15_bothclass"] = abs(blkf - recf)
    out["recf_bothclass"] = recf
    return out


def main():
    own = load_own_state("lonlat")
    cand0 = pd.read_csv(f"{SCRATCH}/res_thresh_cand_pool.csv")
    ev = load_pooled_evaluated()
    evtree = cKDTree(ev[["x_5070", "y_5070"]].values)
    print(f"candidate pool {len(cand0):,} | pooled evaluated {len(ev):,}")

    # attack masks, defined on the FULL candidate pool (index-stable)
    south_half = pd.Series(False, index=cand0.index)
    for r in REG:
        m = (cand0["state"] == r).values
        cut = np.median(cand0.loc[m, "y_5070"])
        south_half[m & (cand0["y_5070"] <= cut).values] = True
    resid = cand0["y_5070"].values - KB * np.floor(cand0["y_5070"].values / KB)
    south_sixth = pd.Series(resid < KB / 6.0, index=cand0.index)
    print(f"attack pools: south_half {south_half.sum():,}  "
          f"south_sixth {south_sixth.sum():,}  of {len(cand0):,}")

    rows = []
    t0 = time.time()
    for seed in range(NSEED):
        pos = thin_fast(own, 30, seed).reset_index(drop=True)
        pbid = blocks_of(pos)
        vb, bc = draw_correct(pbid, len(pos), seed)
        psplit = pbid.map(lambda b: "val" if b in vb else "train")
        blockvf = len(vb) / bc.size            # GLOBAL block-level val rate

        cnd = thin_fast(cand0, 30, seed)
        d, _ = evtree.query(cnd[["x_5070", "y_5070"]].values, k=1)
        cnd = cnd[d > GN.BUFFER_M].copy()
        cbid = blocks_of(cnd)
        cnd["block_id"] = cbid
        bs = dict(zip(pbid.values, psplit.values))
        cnd["split"] = [bs.get(b) or GN.split_for_unassigned(b, blockvf, seed)
                        for b in cnd["block_id"]]

        for tag, restrict in (("fair", None), ("south_half", south_half),
                             ("south_sixth", south_sixth)):
            neg = draw_negatives(cnd, pos, psplit, seed, restrict)
            m = measure(pos, psplit, neg)
            m.update(variant=tag, seed=seed, n_pos=len(pos), n_neg=len(neg),
                     n_cand_after_thin_buffer=len(cnd), blockvf=blockvf)
            rows.append(m)
        if seed % 5 == 0:
            f = [r for r in rows if r["variant"] == "fair"][-1]
            print(f"  seed {seed:3d} ({time.time()-t0:.0f}s) n_pos {f['n_pos']} "
                  f"n_neg {f['n_neg']} d_worst {f['d_worst']:.4f} "
                  f"nn_med {f['nn_median']:.0f} nn_p90 {f['nn_p90']:.0f}")
    df = pd.DataFrame(rows)
    df.to_csv(f"{SCRATCH}/res_thresh_neg.csv", index=False)

    cols = ["d_ME", "d_NH", "d_VT", "d_worst",
            "nn_median", "nn_p90", "nn_p95", "nn_frac_gt_rf",
            "nn_median_worst_region", "nn_p90_worst_region",
            "nnmed_ME", "nnmed_NH", "nnmed_VT",
            "nnp90_ME", "nnp90_NH", "nnp90_VT",
            "I8_pooled", "I8_worst_dev", "neg_valfrac", "I7neg_worst_dev20",
            "negval_ME", "negval_NH", "negval_VT",
            "I15_bothclass", "n_neg"]
    for v, g in df.groupby("variant"):
        print(f"\n===== {v}  ({len(g)} seeds) =====")
        for c in cols:
            a = g[c].values.astype(float)
            print(f"  {c:24s} min {a.min():10.4f} p1 {np.percentile(a,1):10.4f} "
                  f"p5 {np.percentile(a,5):10.4f} med {np.median(a):10.4f} "
                  f"p95 {np.percentile(a,95):10.4f} p99 {np.percentile(a,99):10.4f} "
                  f"max {a.max():10.4f}")
    fair = df[df.variant == "fair"]
    print("\n--- false-fail rate of CR-0007's proposed / withdrawn thresholds ---")
    for t in (0.035, 0.05, 0.10, 0.15, 0.20):
        print(f"  I10 (d) <= {t:.3f} per region : "
              f"{(fair['d_worst']>t).sum()}/{len(fair)} = "
              f"{100*(fair['d_worst']>t).mean():.0f}% false-fail")
    for t in (0.98, 1.0, 1.02):
        pass
    print(f"  I8  1.000 +/- 0.02       : "
          f"{(fair['I8_worst_dev']>0.02).sum()}/{len(fair)}")
    print(f"  I7 neg pooled 20 +/-1 pp : "
          f"{(abs(fair['neg_valfrac']-20)>1).sum()}/{len(fair)}")
    print(f"  I7 neg per-region +/-2pp : "
          f"{(fair['I7neg_worst_dev20']>2).sum()}/{len(fair)}")
    print(f"  nposblk per region (fair, seed0): "
          f"{ {r: int(fair.iloc[0]['nposblk_'+r]) for r in REG} }")
    print(f"  (d) step size per region = 1/nposblk: "
          f"{ {r: round(1.0/fair.iloc[0]['nposblk_'+r],4) for r in REG} }")


if __name__ == "__main__":
    main()
