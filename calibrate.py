"""
calibrate.py

Measures and fixes CALIBRATION - the property none of the training
metrics track. AUC/AP/accuracy are ranking- or threshold-based: a model
can rank perfectly (AUC 1.0) while its probability VALUES are badly
inflated, which is exactly what "the whole KMZ is red" looks like. This
script answers "when the model says 0.9, is the observed positive rate
actually ~90%?" and, if not, fits the standard one-parameter fix.

WHAT IT DOES
  1. Rebuilds the validation set exactly as train.py does (same regions,
     same 4 stored rotations per point, same per-point TTA averaging,
     same optional mirror flip), scores it with your checkpoint, and
     produces per-POINT logits - the same quantity train.py's "TTA AUC"
     is computed on.
  2. Reliability analysis: bins predictions by predicted probability and
     compares each bin's mean prediction against its observed positive
     rate. Reports ECE (expected calibration error - the count-weighted
     mean gap), MCE (worst bin gap), Brier score, and NLL.
  3. PLATT SCALING: fits p = sigmoid(a * logit + b) by minimizing NLL
     on the validation set. The SCALE a is what temperature scaling
     fits (a = 1/T: a < 1 softens an overconfident model). The BIAS b
     is what temperature scaling cannot fit: the training objective
     bakes a constant log-odds offset into the logits (focal alpha,
     L_AN-full lambda, label smoothing, class-balanced batches), and a
     pure scale is symmetric about logit 0, so no temperature can move
     a score across 0.5. With a > 0 it's a monotone transform, so
     RANKING IS PERFECTLY PRESERVED - AUC/AP are identical before and
     after (verified in the output). The plain temperature fit is
     still printed for comparison.
  4. Reports the after-calibration metrics twice: in-sample, and
     CROSS-FITTED (5 folds; each point calibrated by a fit that never
     saw it), which is the honest number.
  5. Writes data/calibration/calibration.json (consumed automatically by
     predict.py, which applies a and b, and re-anchors --prior against
     the validation prevalence recorded here), a reliability CSV, and a
     reliability-diagram PNG.

HONEST LIMITS (printed in the output too):
  - Fitted on the same validation set that picked the checkpoint. Two
    parameters on thousands of points barely overfit (the cross-fitted
    numbers show how much), but the block-split val set is the only
    held-out data there is.
  - Calibrated to the VALIDATION prevalence (recorded in the JSON).
    Real-landscape prevalence of "grouse habitat" is unknown, and no
    post-hoc scaling can recover it from presence/pseudo-absence data:
    the calibrated probabilities mean "relative to the validation
    design" until predict.py --prior supplies a deployment
    prevalence.

USAGE
    python calibrate.py                          # default checkpoint
    python calibrate.py --model data/models/grouse_single_best.pth
    python calibrate.py --regions ME NH VT --bins 15
    python calibrate.py --max-points 500         # quick smoke run
"""
import os
import sys
import json
import argparse
import datetime as dt

import numpy as np
import torch
from torch.utils.data import DataLoader

_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _here)

from grouse_data import GrouseData, refuse_legacy_checkpoint_on_repaired
from models import (GrouseResNet, FEATURE_SPEC, split_features,
                    config_to_model_kwargs, spec_with_checkpoint_vocab,
                    checkpoint_vocab_notes)
from model_handler import GrouseModelHandler, roc_auc, average_precision
from losses import loss_logit_bias
from train import build_datasets, discover_features

OUT_DIR = "data/calibration"


# ==========================================
# Model loading (wrapped or bare checkpoints)
# ==========================================
def load_model(path, device, cli_pool, cli_center_skip, disk_features):
    obj = torch.load(path, map_location=device, weights_only=True)
    state, cfg = GrouseModelHandler.unwrap_checkpoint(obj)
    first = next(iter(state))
    if first.startswith("_orig_mod."):
        state = {k[len("_orig_mod."):]: v for k, v in state.items()}
    if cfg is not None:
        features = cfg.get("features", disk_features)
    else:
        features = disk_features
    # config_to_model_kwargs owns every geometry key and legacy chain
    # in one place; CLI flags are only the bare-checkpoint fallback.
    kw = config_to_model_kwargs(cfg, defaults=dict(
        pool=cli_pool, center_skip=cli_center_skip))
    if cfg is not None:
        print(f"Checkpoint config: pool={kw['pool']}, "
              f"center_skip={kw['center_skip']}, features={features}")
        if set(features) != set(disk_features):
            print(f"  [note] checkpoint features differ from disk "
                  f"({disk_features}) - using the CHECKPOINT's list, since "
                  f"that's the geometry the weights encode.")
    else:
        print(f"Bare (pre-config) checkpoint: assuming pool={kw['pool']}, "
              f"center_skip={kw['center_skip']} from CLI flags - if "
              f"loading fails or results look wrong, pass the flags the "
              f"model was trained with.")
    cat_f, cont_f = split_features(features)
    # Vocab sizes from the checkpoint's own embedding tables (see
    # predict.load_model / models.spec_with_checkpoint_vocab).
    spec = spec_with_checkpoint_vocab(state)
    for note in checkpoint_vocab_notes(spec, cat_f):
        print(f"  [note] checkpoint {note} - rebuilt with the "
              f"checkpoint's own table size.")
    model = GrouseResNet(cat_f, cont_f, spec=spec, pretrained=False,
                         **kw).to(device)
    try:
        model.load_state_dict(state)
    except RuntimeError as e:
        raise SystemExit(
            f"Checkpoint doesn't match the model geometry "
            f"(pool={kw['pool']}, center_skip={kw['center_skip']}, "
            f"features={features}).\nOriginal error:\n{e}")
    model.eval()
    return model, features, cfg


# ==========================================
# Per-point TTA logits over the validation set
# ==========================================
@torch.no_grad()
def collect_val_logits(model, val_ds, device, batch_size, workers,
                       flip_tta, tta_group=4):
    loader = DataLoader(val_ds, batch_size=batch_size, num_workers=workers,
                        pin_memory=(device.type == 'cuda'))
    outs, ys = [], []
    from tqdm import tqdm
    for cat_x, cont_x, y, _w in tqdm(loader, desc="Scoring validation",
                                     leave=False):
        cat_x = cat_x.to(device, non_blocking=True)
        cont_x = cont_x.to(device, non_blocking=True)
        o = model.logits(cat_x, cont_x).float()
        if flip_tta:
            o = 0.5 * (o + model.logits(cat_x.flip(-1),
                                        cont_x.flip(-1)).float())
        outs.append(o.squeeze(1).cpu())
        ys.append(y)
    logits = torch.cat(outs).numpy()
    labels = torch.cat(ys).numpy()
    if tta_group and len(logits) % tta_group == 0:
        g = logits.reshape(-1, tta_group).mean(axis=1)
        gy = labels.reshape(-1, tta_group)
        assert (gy == gy[:, :1]).all(), "TTA grouping crossed a label"
        return g, gy[:, 0]
    return logits, labels


# ==========================================
# Calibration math
# ==========================================
def nll(logits, y, scale=1.0):
    z = logits * scale
    return float(np.mean(np.logaddexp(0.0, z) - y * z))


def fit_temperature(logits, y):
    """Minimize NLL over the logit SCALE s (=1/T). BCE is convex in s, so
    golden-section search is exact enough and dependency-free."""
    lo, hi = 0.02, 20.0
    phi = (np.sqrt(5) - 1) / 2
    a, b = lo, hi
    c, d = b - phi * (b - a), a + phi * (b - a)
    fc, fd = nll(logits, y, c), nll(logits, y, d)
    for _ in range(200):
        if fc < fd:
            b, d, fd = d, c, fc
            c = b - phi * (b - a)
            fc = nll(logits, y, c)
        else:
            a, c, fc = c, d, fd
            d = a + phi * (b - a)
            fd = nll(logits, y, d)
        if abs(b - a) < 1e-6:
            break
    s = 0.5 * (a + b)
    return 1.0 / s          # temperature T


def nll_ab(logits, y, a, b):
    z = a * logits + b
    return float(np.mean(np.logaddexp(0.0, z) - y * z))


def fit_platt(logits, y, iters=100):
    """Minimize NLL over (a, b) in p = sigmoid(a*logit + b): a
    one-feature logistic regression, convex, solved by Newton's method
    with step halving. Dependency-free, exact to ~1e-10."""
    logits = np.asarray(logits, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    X = np.stack([logits, np.ones_like(logits)], axis=1)
    w = np.array([1.0, 0.0])
    f = nll_ab(logits, y, *w)
    for _ in range(iters):
        p = 1.0 / (1.0 + np.exp(-np.clip(X @ w, -500, 500)))
        g = X.T @ (p - y) / len(y)
        H = (X * (p * (1 - p))[:, None]).T @ X / len(y)
        step = np.linalg.solve(H + 1e-9 * np.eye(2), g)
        t, improved = 1.0, False
        while t > 1e-8:
            w_new = w - t * step
            f_new = nll_ab(logits, y, *w_new)
            if f_new <= f:
                improved = True
                break
            t *= 0.5
        if not improved:
            break
        converged = f - f_new < 1e-12
        w, f = w_new, f_new
        if converged:
            break
    return float(w[0]), float(w[1])


def cross_fitted_probs(logits, y, k=5, seed=0):
    """Out-of-fold Platt probabilities: every point is calibrated by a
    fit on the OTHER k-1 folds, so metrics on them are not flattered by
    fitting and scoring the same points."""
    idx = np.random.default_rng(seed).permutation(len(logits))
    out = np.empty(len(logits), dtype=np.float64)
    for fold in np.array_split(idx, k):
        train = np.setdiff1d(idx, fold)
        a, b = fit_platt(logits[train], y[train])
        out[fold] = 1.0 / (1.0 + np.exp(-(a * logits[fold] + b)))
    return out


def reliability(probs, y, n_bins):
    """Equal-width probability bins -> (rows, ece, mce).
    Each row: (lo, hi, count, mean_pred, observed_rate, gap)."""
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    rows, ece, mce = [], 0.0, 0.0
    n = len(probs)
    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        m = (probs >= lo) & (probs < hi if i < n_bins - 1 else probs <= hi)
        cnt = int(m.sum())
        if cnt == 0:
            rows.append((lo, hi, 0, float('nan'), float('nan'), float('nan')))
            continue
        mp, orate = float(probs[m].mean()), float(y[m].mean())
        gap = abs(mp - orate)
        rows.append((lo, hi, cnt, mp, orate, gap))
        ece += (cnt / n) * gap
        mce = max(mce, gap)
    return rows, float(ece), float(mce)


def brier(probs, y):
    return float(np.mean((probs - y) ** 2))


def print_table(title, rows):
    print(f"\n{title}")
    print(f"  {'bin':>12s} {'n':>6s} {'mean pred':>10s} "
          f"{'observed':>9s} {'gap':>7s}")
    for lo, hi, cnt, mp, orate, gap in rows:
        if cnt == 0:
            print(f"  {lo:5.2f}-{hi:4.2f} {cnt:6d}      -          -       -")
        else:
            flag = " <-- " + "!" * min(int(gap * 20), 5) if gap > 0.05 else ""
            print(f"  {lo:5.2f}-{hi:4.2f} {cnt:6d} {mp:10.3f} "
                  f"{orate:9.3f} {gap:7.3f}{flag}")


def save_plot(path, probs_before, probs_after, y, n_bins):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    for ax, probs, name in ((axes[0], probs_before, "before"),
                            (axes[1], probs_after, "after")):
        rows, ece, _ = reliability(probs, y, n_bins)
        xs = [0.5 * (r[0] + r[1]) for r in rows if r[2] > 0]
        preds = [r[3] for r in rows if r[2] > 0]
        obs = [r[4] for r in rows if r[2] > 0]
        ax.plot([0, 1], [0, 1], "k--", lw=1, label="perfect")
        ax.plot(preds, obs, "o-", label=f"model (ECE {ece:.3f})")
        ax.hist(probs, bins=n_bins, range=(0, 1), weights=np.full(
            len(probs), 1.0 / len(probs)), alpha=0.25, label="prediction density")
        ax.set_xlabel("predicted probability")
        ax.set_ylabel("observed positive rate")
        ax.set_title(f"Reliability - {name} Platt scaling")
        ax.legend(fontsize=8)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(
        description="Reliability analysis + Platt scaling for the "
                    "trained grouse model.")
    parser.add_argument("--model", default="grouse_single_best.pth")
    parser.add_argument("--regions", nargs="+", default=["ME", "NH", "VT"])
    parser.add_argument("--img-size", type=int, default=64)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--workers", type=int,
                        default=max(1, (os.cpu_count() or 4) - 2))
    parser.add_argument("--bins", type=int, default=15)
    parser.add_argument("--cache-dir", default="data/cache",
                        help="Same patch cache train.py uses; '' disables.")
    parser.add_argument("--flip-tta", action=argparse.BooleanOptionalAction,
                        default=True,
                        help="Mirror-averaged scoring, matching train.py's "
                             "evaluation default.")
    parser.add_argument("--pool", default="attn",
                        choices=["mean", "center", "gauss", "attn"],
                        help="Only used for OLD bare checkpoints with no "
                             "embedded config.")
    parser.add_argument("--center-skip",
                        action=argparse.BooleanOptionalAction, default=True,
                        help="Only used for old bare checkpoints.")
    parser.add_argument("--max-points", type=int, default=None,
                        help="Subsample per-point predictions for a quick "
                             "smoke run (default: all).")
    parser.add_argument("--out", default=OUT_DIR)
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")
    data = GrouseData()
    disk_features = discover_features(data, args.regions)
    model, features, ckpt_cfg = load_model(args.model, device, args.pool,
                                           args.center_skip, disk_features)
    refuse_legacy_checkpoint_on_repaired(model, [
        data[r].raster_path(f, y, nearest=False, validate=False)
        for r in args.regions for f in features
        for y in data[r].raster_years(f)])
    bias = loss_logit_bias(ckpt_cfg)
    if bias is not None:
        reason, off = bias
        print(f"\n[note] this checkpoint was trained with {reason}: the "
              f"objective's asymmetric weighting builds a constant logit "
              f"offset (~{off:+.2f}) into the model BY DESIGN. A "
              f"temperature alone could not remove it; the Platt BIAS "
              f"fitted below does (expect a fitted bias of roughly "
              f"{-off:+.2f}, plus whatever else the design shifted).")

    _, val_ds, _ = build_datasets(data, args.regions, features,
                                  args.img_size,
                                  cache_dir=args.cache_dir or None)
    print(f"Validation samples: {len(val_ds):,} "
          f"({len(val_ds) // 4:,} points x 4 rotations)")

    logits, y = collect_val_logits(model, val_ds, device, args.batch_size,
                                   args.workers, args.flip_tta)
    if args.max_points and len(logits) > args.max_points:
        idx = np.random.default_rng(0).choice(len(logits), args.max_points,
                                              replace=False)
        logits, y = logits[idx], y[idx]
        print(f"[smoke mode] subsampled to {len(logits)} points")

    probs = 1.0 / (1.0 + np.exp(-logits))
    rows_b, ece_b, mce_b = reliability(probs, y, args.bins)
    auc_b, ap_b = roc_auc(logits, y), average_precision(logits, y)
    print_table("RELIABILITY - BEFORE calibration", rows_b)
    print(f"\n  ECE {ece_b:.4f} | MCE {mce_b:.4f} | Brier "
          f"{brier(probs, y):.4f} | NLL {nll(logits, y):.4f} | "
          f"AUC {auc_b:.4f} | AP {ap_b:.4f}")

    prevalence = float(np.mean(y))
    T_only = fit_temperature(logits, y)
    ece_T = reliability(1.0 / (1.0 + np.exp(-logits / T_only)), y,
                        args.bins)[1]
    a, b = fit_platt(logits, y)
    if a <= 0:
        raise SystemExit(
            f"Platt fit gave a non-positive scale (a={a:.4f}): on this "
            f"validation set the logits carry no usable ranking signal "
            f"(AUC {auc_b:.3f}), and calibrating them would invert or "
            f"flatten the map. Not writing a calibration - fix the "
            f"model first.")
    T = 1.0 / a
    logits_c = a * logits + b
    probs_c = 1.0 / (1.0 + np.exp(-logits_c))
    rows_a, ece_a, mce_a = reliability(probs_c, y, args.bins)
    auc_a, ap_a = roc_auc(logits_c, y), average_precision(logits_c, y)
    print_table(f"RELIABILITY - AFTER Platt scaling (a = {a:.3f}, "
                f"b = {b:+.3f}), in-sample", rows_a)
    print(f"\n  ECE {ece_a:.4f} | MCE {mce_a:.4f} | Brier "
          f"{brier(probs_c, y):.4f} | NLL {nll(logits_c, y):.4f} | "
          f"AUC {auc_a:.4f} | AP {ap_a:.4f}")
    probs_cv = cross_fitted_probs(logits, y)
    _, ece_cv, mce_cv = reliability(probs_cv, y, args.bins)
    nll_cv = float(-np.mean(y * np.log(np.clip(probs_cv, 1e-12, 1))
                            + (1 - y) * np.log(np.clip(1 - probs_cv,
                                                       1e-12, 1))))
    print(f"  cross-fitted (5-fold, out-of-sample): ECE {ece_cv:.4f} | "
          f"MCE {mce_cv:.4f} | Brier {brier(probs_cv, y):.4f} | "
          f"NLL {nll_cv:.4f}")
    print(f"  (temperature-only fit for comparison: T = {T_only:.3f}, "
          f"ECE {ece_T:.4f})")
    print(f"\n  Ranking preserved: AUC before {auc_b:.6f} == after "
          f"{auc_a:.6f} -> {abs(auc_b - auc_a) < 1e-9}")

    if a < 1 / 1.05:
        scale_v = (f"OVERCONFIDENT by a factor of ~{T:.2f}: raw logits "
                   f"are stretched toward the extremes and get "
                   f"multiplied by {a:.3f}")
    elif a > 1.05:
        scale_v = (f"UNDERCONFIDENT (scale {a:.2f} > 1): probabilities "
                   f"are compressed toward 0.5 and get sharpened")
    else:
        scale_v = f"confidence scale already about right (a = {a:.2f})"
    shift_p = 1.0 / (1.0 + np.exp(-b))
    print(f"\nVERDICT: {scale_v}; bias {b:+.3f} moves a raw logit of 0 "
          f"to p = {shift_p:.3f} - a constant offset (training "
          f"objective, balanced batches, label smoothing) that "
          f"temperature scaling could never remove.")
    print(f"\nCAVEAT: probabilities are calibrated to the validation "
          f"prevalence ({prevalence:.3f} positive), not to true "
          f"landscape occupancy - inherent to the presence/pseudo-"
          f"absence design. predict.py --prior re-anchors them to a "
          f"deployment prevalence you supply.")

    os.makedirs(args.out, exist_ok=True)
    payload = {
        # p = sigmoid(scale * logit + bias). predict.py reads these;
        # "temperature" (= 1/scale) is kept for older readers and is
        # NOT a complete calibration on its own.
        "method": "platt",
        "scale": float(a),
        "bias": float(b),
        "temperature": float(T),
        "val_prevalence": prevalence,
        "temperature_only": float(T_only),
        "fitted_at": dt.datetime.now().isoformat(timespec="seconds"),
        "model_path": os.path.abspath(args.model),
        "regions": args.regions,
        "features": features,
        "flip_tta": bool(args.flip_tta),
        "n_points": int(len(logits)),
        # The objective the checkpoint was trained with (None for
        # pre-metadata checkpoints), kept as provenance: the Platt bias
        # above already absorbs the offset it implies.
        "loss": (ckpt_cfg or {}).get("loss"),
        "an_pos_weight": (ckpt_cfg or {}).get("an_pos_weight"),
        "focal_alpha": (ckpt_cfg or {}).get("focal_alpha"),
        "ece_before": ece_b, "ece_after": ece_a,
        "mce_before": mce_b, "mce_after": mce_a,
        "brier_before": brier(probs, y), "brier_after": brier(probs_c, y),
        "nll_before": nll(logits, y), "nll_after": nll(logits_c, y),
        "ece_cross_fitted": ece_cv, "nll_cross_fitted": nll_cv,
        "auc": auc_b, "ap": ap_b,
    }
    json_path = os.path.join(args.out, "calibration.json")
    with open(json_path, "w") as f:
        json.dump(payload, f, indent=2)
    csv_path = os.path.join(args.out, "reliability.csv")
    with open(csv_path, "w") as f:
        f.write("stage,bin_lo,bin_hi,count,mean_pred,observed,gap\n")
        for stage, rows in (("before", rows_b), ("after", rows_a)):
            for lo, hi, cnt, mp, orate, gap in rows:
                f.write(f"{stage},{lo:.4f},{hi:.4f},{cnt},"
                        f"{mp if cnt else ''},{orate if cnt else ''},"
                        f"{gap if cnt else ''}\n")
    png_path = os.path.join(args.out, "reliability.png")
    save_plot(png_path, probs, probs_c, y, args.bins)
    print(f"\nSaved: {json_path}\n       {csv_path}\n       {png_path}")
    print("predict.py picks up the scale and bias automatically from "
          "calibration.json.")
    print(f"NOTE: these probabilities are relative to the validation "
          f"design ({prevalence:.0%} positive). If a predicted map lights "
          f"up wall-to-wall, that is prior mismatch, not a bad fit - use "
          f"predict.py --prior <expected suitable fraction> or --style "
          f"quantile.")


if __name__ == "__main__":
    main()
