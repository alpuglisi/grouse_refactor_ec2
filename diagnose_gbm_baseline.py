"""Gradient-boosted-trees baseline on the CNN's own train/val split.

Question it answers: is the CNN's ~0.76 validation AUC the ceiling of
the DATA (features + labels), or is the CNN leaving signal unused?

  - GBM ~ CNN    -> the data is the ceiling; tune data/features, not the net.
  - GBM >> CNN   -> the CNN under-uses the inputs (smaller/simpler model).
  - GBM << CNN   -> the CNN's spatial context earns its keep.

Read-only diagnostic. It goes through train.build_datasets, so it uses
exactly the training split, the acceptance standing checks (CR-0013) and
the patch reader the CNN uses; it passes cache_dir=None, so nothing is
written under data/. Background assumed-negatives are not used.

Per point (one unrotated 64 x 64 patch, the CNN's input):
  * categorical features (evt, evh, evc, sclass, fdist, nlcd): the centre
    pixel's code, re-coded to the 254 most frequent TRAINING codes per
    feature (others -> one "other" level; nodata -> missing), plus the
    share of the 21 x 21 window (~630 m) holding the centre code;
  * continuous features: centre 2 x 2 mean, and mean / std over 5 x 5,
    21 x 21 and the whole 64 x 64 window (NaN-aware; nodata is NaN).
Two models are fitted: centre-only, and centre + neighbourhood.

Usage (repository root, the same environment as train.py):
    python diagnose_gbm_baseline.py                 # 3 seeds, both models
    python diagnose_gbm_baseline.py --seeds 0 1 2 3 4 --importance
"""
import argparse
import time
import warnings

import numpy as np

CAT_MAX_LEVELS = 254          # HistGradientBoosting: categories < 255
CONT_WINDOWS = (5, 21, 64)    # neighbourhood widths in pixels (30 m)
CAT_WINDOW = 21


def patch_frames(concat, workers):
    """(cat, cont, label) arrays, one unrotated patch per point, for every
    GrousePatchDataset part of a ConcatDataset built with
    expand_rotations=True (index 4*i is point i, rotation 0)."""
    import torch
    from torch.utils.data import DataLoader, Subset
    cats, conts, ys = [], [], []
    for part in concat.datasets:
        n_points = len(part) // 4 if part.expand_rotations else len(part)
        step = 4 if part.expand_rotations else 1
        idx = list(range(0, n_points * step, step))
        loader = DataLoader(Subset(part, idx), batch_size=256,
                            num_workers=workers, shuffle=False)
        for batch in loader:
            cat_x, cont_x, yl = batch[0], batch[1], batch[2]
            cats.append(cat_x.numpy())
            conts.append(cont_x.numpy())
            ys.append(yl.numpy().reshape(-1))
    return (np.concatenate(cats), np.concatenate(conts),
            np.concatenate(ys).astype(np.int64))


def centre_slice(n, w):
    lo = n // 2 - w // 2
    return slice(lo, lo + w)


def cont_features(cont, names):
    """Centre 2x2 mean, then mean/std per window, per continuous feature."""
    n = cont.shape[-1]
    cols, out_names = [], []
    c2 = centre_slice(n, 2)
    with np.errstate(invalid="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)  # all-NaN windows
        for j, f in enumerate(names):
            x = cont[:, j]
            cols.append(np.nanmean(x[:, c2, c2], axis=(1, 2)))
            out_names.append(f"{f}_c")
            for w in CONT_WINDOWS:
                s = centre_slice(n, w)
                win = x[:, s, s]
                cols.append(np.nanmean(win, axis=(1, 2)))
                out_names.append(f"{f}_m{w}")
                cols.append(np.nanstd(win, axis=(1, 2)))
                out_names.append(f"{f}_s{w}")
    return np.stack(cols, axis=1), out_names


def cat_centre_codes(cat, missing_code):
    n = cat.shape[-1]
    centre = cat[:, :, n // 2, n // 2]                    # (N, n_cat)
    s = centre_slice(n, CAT_WINDOW)
    win = cat[:, :, s, s]
    share = (win == centre[:, :, None, None]).mean(axis=(2, 3))
    share[centre == missing_code] = np.nan
    return centre, share


def recode(train_codes, codes, missing_code):
    """Map raw codes to 0..K-1 by training frequency (top CAT_MAX_LEVELS-1
    kept, the rest -> K-1 "other"); nodata -> NaN (missing)."""
    out = np.full(codes.shape, np.nan)
    for j in range(codes.shape[1]):
        tr = train_codes[:, j]
        vals, counts = np.unique(tr[tr != missing_code], return_counts=True)
        keep = vals[np.argsort(-counts, kind="stable")][:CAT_MAX_LEVELS - 1]
        lut = {int(v): k for k, v in enumerate(keep)}
        other = len(keep)
        col = codes[:, j]
        mapped = np.array([lut.get(int(v), other) for v in col], float)
        mapped[col == missing_code] = np.nan
        out[:, j] = mapped
    return out


def design(cat, cont, cat_names, cont_names, train_cat_centre, missing_code,
           with_neighbourhood):
    centre, share = cat_centre_codes(cat, missing_code)
    codes = recode(train_cat_centre, centre, missing_code)
    cols = [codes]
    names = [f"{f}_code" for f in cat_names]
    is_cat = [True] * len(cat_names)
    cf, cn = cont_features(cont, cont_names)
    if with_neighbourhood:
        cols += [share, cf]
        names += [f"{f}_share{CAT_WINDOW}" for f in cat_names] + cn
        is_cat += [False] * (len(cat_names) + len(cn))
    else:
        centre_cols = [i for i, nm in enumerate(cn) if nm.endswith("_c")]
        cols.append(cf[:, centre_cols])
        names += [cn[i] for i in centre_cols]
        is_cat += [False] * len(centre_cols)
    return np.concatenate(cols, axis=1), names, np.array(is_cat)


def fit_eval(Xtr, ytr, Xva, yva, is_cat, seed):
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import roc_auc_score, average_precision_score
    clf = HistGradientBoostingClassifier(
        learning_rate=0.05, max_iter=1000, max_leaf_nodes=31,
        min_samples_leaf=40, l2_regularization=1.0,
        categorical_features=is_cat, early_stopping=True,
        validation_fraction=0.15, n_iter_no_change=30, random_state=seed)
    clf.fit(Xtr, ytr)
    p = clf.predict_proba(Xva)[:, 1]
    return clf, roc_auc_score(yva, p), average_precision_score(yva, p)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--img-size", type=int, default=64)
    ap.add_argument("--importance", action="store_true",
                    help="Permutation importance (val AUC drop) of the "
                         "neighbourhood model, first seed; slower.")
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
    print(f"Features: categorical {cat_f}; continuous {cont_f}")
    train_ds, val_ds, _ = train.build_datasets(
        data, regions, features, args.img_size, cache_dir=None,
        jitter=0, augment=False, background_per_pos=0.0)
    cat_tr, cont_tr, ytr = patch_frames(train_ds, args.workers)
    cat_va, cont_va, yva = patch_frames(val_ds, args.workers)
    print(f"Points: train {len(ytr):,} ({ytr.mean():.3f} positive), "
          f"val {len(yva):,} ({yva.mean():.3f} positive); "
          f"patches read in {time.time() - t0:.0f} s")

    n = cat_tr.shape[-1]
    train_centre = cat_tr[:, :, n // 2, n // 2]
    results = {}
    for label, nb in (("centre only", False), ("centre + neighbourhood", True)):
        Xtr, names, is_cat = design(cat_tr, cont_tr, cat_f, cont_f,
                                    train_centre, MISSING_CODE, nb)
        Xva, _, _ = design(cat_va, cont_va, cat_f, cont_f,
                           train_centre, MISSING_CODE, nb)
        aucs, aps, first = [], [], None
        for s in args.seeds:
            clf, auc, apv = fit_eval(Xtr, ytr, Xva, yva, is_cat, s)
            aucs.append(auc)
            aps.append(apv)
            first = first or (clf, Xva, names)
            print(f"  [{label}] seed {s}: val AUC {auc:.4f}  AP {apv:.4f}  "
                  f"({clf.n_iter_} trees)")
        results[label] = (np.mean(aucs), np.std(aucs), np.mean(aps),
                          np.std(aps), len(names), first)

    print("\nSUMMARY (val, one point per location; the CNN's reference is "
          "TTA AUC 0.760 / AP 0.714, warm-restart run 0.763 / 0.723)")
    for label, (ma, sa, mp, sp, nf, _) in results.items():
        print(f"  {label:24s} {nf:4d} features  AUC {ma:.4f} +/- {sa:.4f}  "
              f"AP {mp:.4f} +/- {sp:.4f}")

    if args.importance:
        from sklearn.inspection import permutation_importance
        clf, Xva, names = results["centre + neighbourhood"][5]
        r = permutation_importance(clf, Xva, yva, scoring="roc_auc",
                                   n_repeats=5, random_state=0,
                                   n_jobs=args.workers)
        order = np.argsort(-r.importances_mean)[:25]
        print("\nPermutation importance (val AUC drop), top 25:")
        for i in order:
            print(f"  {names[i]:22s} {r.importances_mean[i]:+.4f} "
                  f"+/- {r.importances_std[i]:.4f}")
    print(f"\nDone in {time.time() - t0:.0f} s.")


if __name__ == "__main__":
    main()
