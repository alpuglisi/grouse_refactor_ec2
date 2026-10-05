"""Is road distance habitat or class-sampling bias? (current split)

diagnose_gbm_baseline.py ranks road_dist third (after sclass and evt).
diagnose_road_bias.py (2026-09-18, CHANGELOG "The road-hugging
investigation") already measured, on the splits of that time and TIGER
primary/secondary roads, that training POSITIVES sit 2-5x FARTHER from
roads than the negatives: the negatives (other species' records, from
roadsides, yards and towns) are the road-biased class. Since then the
split and negatives were rebuilt (CR-0012, CR-0017, CR-0019, CR-0021) and
road_dist is distance to PAVED roads. This re-measures on today's
training/validation points and asks the open question: is the road
signal habitat (grouse avoid developed land) or how each class gets
recorded (sampling), and how much does the model need it?

Read-only diagnostic (train.build_datasets, cache_dir=None: same split,
standing checks and patch reader as the CNN; nothing written under
data/). Reports:

  1. Road distance (metres to the nearest paved road, centre pixel) by
     class, region and split: quantiles, share within 100/250/500/1000 m,
     and the AUC of road distance ALONE (> 0.5: positives FARTHER from
     roads; < 0.5: positives nearer).
  2. The same AUC WITHIN habitat strata: points grouped by their centre
     succession class (sclass) and, separately, vegetation type (evt);
     per-stratum AUCs averaged, weighted by stratum size. A road signal
     that survives inside one habitat class is not explained by habitat
     composition alone.
  3. Gradient-boosted trees (as in diagnose_gbm_baseline.py, centre +
     neighbourhood) with and without every road_dist feature: the val
     AUC the road features add.

Reading:
  * road-only AUC near 0.5 overall and within strata: road_dist is not a
    class-sampling artefact.
  * road-only AUC far from 0.5 that mostly VANISHES within strata: the
    road signal is habitat composition the other layers already carry.
  * far from 0.5 and PERSISTS within strata, and the trees lose little
    without road_dist: a recording/sampling difference carrying little
    extra habitat information; candidate for removal (its own CR).
  * the trees lose a lot without it: road distance carries information
    the other layers do not (remoteness, development); inspect the map
    before removing.

Usage (repository root, same environment as train.py):
    python diagnose_road_signal.py
"""
import argparse
import time

import numpy as np

import diagnose_gbm_baseline as gbm

THRESHOLDS_M = (100, 250, 500, 1000)
MIN_STRATUM = 30          # points per class needed for a within-stratum AUC


def patch_frames_with_region(concat, workers):
    """As gbm.patch_frames, plus each point's region (from the part's
    points frame, whose rows are in dataset order)."""
    cat, cont, y = gbm.patch_frames(concat, workers)
    regions = np.concatenate([part.df["region"].astype(str).to_numpy()
                              for part in concat.datasets])
    assert len(regions) == len(y), (len(regions), len(y))
    return cat, cont, y, regions


def auc(score, y):
    from sklearn.metrics import roc_auc_score
    if len(np.unique(y)) < 2:
        return np.nan
    return float(roc_auc_score(y, score))


def describe(metres, y, label):
    pos, neg = metres[y == 1], metres[y == 0]
    q = (10, 25, 50, 75, 90)
    lines = [f"  {label}: n pos {len(pos):,} / neg {len(neg):,}; "
             f"road-only AUC {auc(metres, y):.3f} (> 0.5: positives farther from roads)"]
    for name, v in (("pos", pos), ("neg", neg)):
        qs = np.nanpercentile(v, q)
        within = "  ".join(f"<={t} m {np.mean(v <= t) * 100:5.1f}%"
                           for t in THRESHOLDS_M)
        lines.append(f"    {name}: median {qs[2]:7.0f} m  "
                     f"(p10 {qs[0]:.0f}, p25 {qs[1]:.0f}, p75 {qs[3]:.0f}, "
                     f"p90 {qs[4]:.0f})  {within}")
    return "\n".join(lines)


def within_strata_auc(metres, y, strata):
    """Size-weighted mean of the road-only AUC within each stratum that
    has >= MIN_STRATUM points of each class; and the share of points it
    covers."""
    num, den, covered = 0.0, 0, 0
    for s in np.unique(strata):
        m = strata == s
        n_pos, n_neg = int((y[m] == 1).sum()), int((y[m] == 0).sum())
        if n_pos < MIN_STRATUM or n_neg < MIN_STRATUM:
            continue
        a = auc(metres[m], y[m])
        num += a * m.sum()
        den += int(m.sum())
        covered += int(m.sum())
    return (num / den if den else np.nan), covered / len(y)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--img-size", type=int, default=64)
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    args = ap.parse_args()

    import train
    from grouse_data import GrouseData, MISSING_CODE
    from models import split_features, FEATURE_SPEC, road_dist_decode
    from regions import REGIONS

    t0 = time.time()
    data = GrouseData()
    regions = list(REGIONS)
    features = train.discover_features(data, regions)
    cat_f, cont_f = split_features(features)
    if "road_dist" not in cont_f:
        raise SystemExit("road_dist is not among the model features on disk.")
    train_ds, val_ds, _ = train.build_datasets(
        data, regions, features, args.img_size, cache_dir=None,
        jitter=0, augment=False, background_per_pos=0.0)
    sets = {"train": patch_frames_with_region(train_ds, args.workers),
            "val": patch_frames_with_region(val_ds, args.workers)}
    print(f"Patches read in {time.time() - t0:.0f} s")

    j_road = cont_f.index("road_dist")
    scale = float(FEATURE_SPEC["road_dist"].get("scale", 1.0))
    j_sclass = cat_f.index("sclass") if "sclass" in cat_f else None
    j_evt = cat_f.index("evt") if "evt" in cat_f else None

    print("\n1. ROAD DISTANCE BY CLASS (centre pixel, metres to paved road)")
    per = {}
    for split, (cat, cont, y, reg) in sets.items():
        n = cont.shape[-1]
        stored = cont[:, j_road, n // 2, n // 2] * scale     # NaN = nodata
        metres = road_dist_decode(np.where(np.isnan(stored), 0, stored))
        metres[np.isnan(stored)] = np.nan
        ok = ~np.isnan(metres)
        per[split] = (metres, y, reg, cat, ok)
        print(f"\n [{split}] nodata (outside road coverage): "
              f"{int((~ok).sum())} of {len(y)} points, excluded")
        print(describe(metres[ok], y[ok], f"{split} pooled"))
        for r in regions:
            m = ok & (reg == r)
            print(describe(metres[m], y[m], f"{split} {r}"))

    print("\n2. ROAD-ONLY AUC WITHIN HABITAT STRATA (size-weighted mean; "
          f"strata with >= {MIN_STRATUM} points of each class)")
    for split, (metres, y, reg, cat, ok) in per.items():
        n = cat.shape[-1]
        row = [f"  [{split}] overall {auc(metres[ok], y[ok]):.3f}"]
        for name, j in (("sclass", j_sclass), ("evt", j_evt)):
            if j is None:
                continue
            codes = cat[:, j, n // 2, n // 2]
            m = ok & (codes != MISSING_CODE)
            a, cov = within_strata_auc(metres[m], y[m], codes[m])
            row.append(f"within {name} {a:.3f} (covers {cov * 100:.0f}% of points)")
        for r in regions:
            m = ok & (reg == r)
            if j_sclass is not None:
                codes = cat[:, j_sclass, n // 2, n // 2]
                mm = m & (codes != MISSING_CODE)
                a, _ = within_strata_auc(metres[mm], y[mm], codes[mm])
                row.append(f"{r} within sclass {a:.3f}")
        print("; ".join(row))

    print("\n3. TREES WITH AND WITHOUT road_dist (centre + neighbourhood, val)")
    cat_tr, cont_tr, ytr, _ = sets["train"]
    cat_va, cont_va, yva, _ = sets["val"]
    n = cat_tr.shape[-1]
    train_centre = cat_tr[:, :, n // 2, n // 2]
    Xtr, names, is_cat = gbm.design(cat_tr, cont_tr, cat_f, cont_f,
                                    train_centre, MISSING_CODE, True)
    Xva, _, _ = gbm.design(cat_va, cont_va, cat_f, cont_f,
                           train_centre, MISSING_CODE, True)
    keep = np.array([not nm.startswith("road_dist_") for nm in names])
    out = {}
    for label, cols in (("with road_dist", np.ones(len(names), bool)),
                        ("without road_dist", keep)):
        aucs, aps = [], []
        for s in args.seeds:
            _, a, p = gbm.fit_eval(Xtr[:, cols], ytr, Xva[:, cols], yva,
                                   is_cat[cols], s)
            aucs.append(a)
            aps.append(p)
        out[label] = (np.mean(aucs), np.std(aucs), np.mean(aps))
        print(f"  {label:18s} {int(cols.sum()):3d} features  AUC "
              f"{np.mean(aucs):.4f} +/- {np.std(aucs):.4f}  AP {np.mean(aps):.4f}")
    d = out["with road_dist"][0] - out["without road_dist"][0]
    print(f"  road_dist adds {d:+.4f} val AUC")
    print(f"\nDone in {time.time() - t0:.0f} s.")


if __name__ == "__main__":
    main()
