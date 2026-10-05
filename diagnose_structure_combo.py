"""Combined test: fine-scale canopy structure + disturbance history.

diagnose_lidar_features.py found the Meta/WRI 1 m canopy height adds
~+0.012 val AUC to diagnose_gbm_baseline's trees (GEDI adds nothing);
diagnose_disturbance_features.py found LCMS/Hansen harvest history adds
~0 on its own. Harvest timing and canopy structure describe the same
young-forest condition from two sides, so this asks whether they help
TOGETHER, using the Earth Engine samples both scripts cached - no new
Earth Engine queries.

Fits the same trees over several seeds for: today's features; + Meta;
+ LCMS; + Meta + LCMS; + Meta + LCMS + Hansen; + everything (with GEDI).
Optionally (--importance) the permutation importance of the new columns
in the Meta + LCMS model.

Read-only (train.build_datasets, cache_dir=None; nothing written under
data/). Needs both caches from runs on the CURRENT split; refuses if
either does not match today's points.

Usage (repository root):
    python diagnose_structure_combo.py
    python diagnose_structure_combo.py --seeds 0 1 2 3 4 5 6 7 --importance
"""
import argparse
import ast
import os
import time

import numpy as np
import pandas as pd

import diagnose_gbm_baseline as gbm
import diagnose_disturbance_features as ddf
import diagnose_lidar_features as dlf


def load_cache(path, pts, what, script):
    """The cached raw samples, refused unless they were drawn for these
    exact points (row count and the longitude checksum in the cache key)."""
    if not os.path.exists(path):
        raise SystemExit(f"No {what} cache at {path}: run "
                         f"python {script} first.")
    raw = pd.read_csv(path)
    key = ast.literal_eval(raw["key"].iloc[0])
    lon_sum = float(pts["longitude"].sum())
    if len(raw) != len(pts) or key[2] != len(pts) or \
            abs(float(key[3]) - lon_sum) > 1e-6 * max(1.0, abs(lon_sum)):
        raise SystemExit(f"{path} was drawn for other points (cache key "
                         f"{key[2]} points); re-run python {script}.")
    if not (raw["idx"].to_numpy() == np.arange(len(pts))).all():
        raise SystemExit(f"{path}: rows are not in point order.")
    return raw.drop(columns=["key"])


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dist-cache", default="/tmp/grouse_disturbance_samples.csv")
    ap.add_argument("--lidar-cache", default="/tmp/grouse_lidar_samples.csv")
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2, 3, 4])
    ap.add_argument("--importance", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--img-size", type=int, default=64)
    args = ap.parse_args()

    import train
    from grouse_data import GrouseData, MISSING_CODE
    from models import split_features
    from regions import REGIONS

    t0 = time.time()
    data = GrouseData()
    regions = list(REGIONS)
    features = train.discover_features(data, regions)
    cat_f, cont_f = split_features(features)
    train_ds, val_ds, _ = train.build_datasets(
        data, regions, features, args.img_size, cache_dir=None,
        jitter=0, augment=False, background_per_pos=0.0)
    cat_tr, cont_tr, ytr = gbm.patch_frames(train_ds, args.workers)
    cat_va, cont_va, yva = gbm.patch_frames(val_ds, args.workers)
    pts = pd.concat([ddf.point_frame(train_ds), ddf.point_frame(val_ds)],
                    ignore_index=True)
    print(f"Points: train {len(ytr):,}, val {len(yva):,}; patches read in "
          f"{time.time() - t0:.0f} s")

    dist = ddf.derive(load_cache(args.dist_cache, pts, "disturbance",
                                 "diagnose_disturbance_features.py"))
    lid = dlf.derive(load_cache(args.lidar_cache, pts, "lidar",
                                "diagnose_lidar_features.py"))
    feats = pd.concat([dist.drop(columns=["idx"]), lid.drop(columns=["idx"])],
                      axis=1)
    meta = [c for c in lid.columns if c.startswith("meta_")]
    gedi = [c for c in lid.columns if c.startswith("gedi_")]
    lcms, gfc = list(ddf.FEATURES_LCMS), list(ddf.FEATURES_GFC)

    n = cat_tr.shape[-1]
    train_centre = cat_tr[:, :, n // 2, n // 2]
    Xtr, names, is_cat = gbm.design(cat_tr, cont_tr, cat_f, cont_f,
                                    train_centre, MISSING_CODE, True)
    Xva, _, _ = gbm.design(cat_va, cont_va, cat_f, cont_f,
                           train_centre, MISSING_CODE, True)
    allc = list(feats.columns)
    F = feats.to_numpy(float)
    idx = lambda cs: [allc.index(c) for c in cs]

    print(f"\nTREES (centre + neighbourhood, val; {len(args.seeds)} seeds)")
    base = None
    combos = (("today's features", []),
              ("+ Meta", meta),
              ("+ LCMS", lcms),
              ("+ Meta + LCMS", meta + lcms),
              ("+ Meta + LCMS + Hansen", meta + lcms + gfc),
              ("+ everything (with GEDI)", meta + lcms + gfc + gedi))
    for label, cs in combos:
        m, sd, p = dlf.trees(Xtr, Xva, is_cat, F, idx(cs), ytr, yva, args.seeds)
        base = m if base is None else base
        print(f"  {label:26s} {Xtr.shape[1] + len(cs):3d} features  AUC "
              f"{m:.4f} +/- {sd:.4f}  AP {p:.4f}  (vs today {m - base:+.4f})")

    if args.importance:
        from sklearn.inspection import permutation_importance
        cs = meta + lcms
        cols = idx(cs)
        n_tr = len(ytr)
        Xt = np.concatenate([Xtr, F[:n_tr][:, cols]], axis=1)
        Xv = np.concatenate([Xva, F[n_tr:][:, cols]], axis=1)
        ic = np.concatenate([is_cat, np.zeros(len(cols), bool)])
        clf, _, _ = gbm.fit_eval(Xt, ytr, Xv, yva, ic, args.seeds[0])
        r = permutation_importance(clf, Xv, yva, scoring="roc_auc",
                                   n_repeats=5, random_state=0,
                                   n_jobs=args.workers)
        allnames = names + cs
        order = np.argsort(-r.importances_mean)[:20]
        print("\nPermutation importance in the Meta + LCMS model (val AUC "
              "drop), top 20:")
        for i in order:
            tag = "  NEW" if i >= len(names) else ""
            print(f"  {allnames[i]:22s} {r.importances_mean[i]:+.4f} "
                  f"+/- {r.importances_std[i]:.4f}{tag}")
    print(f"\nDone in {time.time() - t0:.0f} s.")


if __name__ == "__main__":
    main()
