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
  3. TEMPERATURE SCALING (Guo et al. 2017): fits a single scalar T that
     rescales logits (p = sigmoid(logit / T)) to minimize NLL on the
     validation set. T > 1 means the model was overconfident and gets
     softened; T < 1 means underconfident. Because it's a monotone
     transform of the logit, RANKING IS PERFECTLY PRESERVED - AUC/AP are
     bit-identical before and after (verified in the output).
  4. Writes data/calibration/calibration.json (consumed automatically by
     predict.py), a reliability CSV, and a reliability-diagram PNG.

HONEST LIMITS (printed in the output too):
  - Fitted and evaluated on the same validation set. Standard practice
    for temperature scaling (it's ONE parameter, overfit risk is tiny),
    but the block-split val set is the only held-out data there is.
  - Calibrated to the VALIDATION prevalence (~50/50 by construction).
    Real-landscape prevalence of "grouse habitat" is not 50%, so the
    calibrated probabilities mean "relative to a balanced
    presence/pseudo-absence design", not "true occupancy probability".
    That's inherent to how the training data was built, not fixable by
    any post-hoc scaling.

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

from grouse_data import GrouseData
from models import GrouseResNet, FEATURE_SPEC, split_features
from model_handler import GrouseModelHandler, roc_auc, average_precision
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
        pool = cfg.get("pool", cli_pool)
        center_skip = cfg.get("center_skip", cli_center_skip)
        features = cfg.get("features", disk_features)
        keep_early_res = cfg.get("keep_early_resolution", False)
        early_attn = cfg.get("early_attn", False)
        early_attn_kv_stride = cfg.get("early_attn_kv_stride", 1)
        early_attn_heads = cfg.get("early_attn_heads", 4)
        # Position-mode legacy chain: new configs store
        # early_attn_pos_mode; interim ones store early_attn_pos_enc
        # (bool -> 'abs'); pre-fix ones store neither and trained
        # position-blind ('none'). The model must be rebuilt with
        # whatever mode it trained under.
        early_attn_pos_mode = cfg.get("early_attn_pos_mode")
        if early_attn_pos_mode is None:
            early_attn_pos_mode = ('abs' if cfg.get("early_attn_pos_enc")
                                   else 'none')
        print(f"Checkpoint config: pool={pool}, center_skip={center_skip}, "
              f"features={features}")
        if set(features) != set(disk_features):
            print(f"  [note] checkpoint features differ from disk "
                  f"({disk_features}) - using the CHECKPOINT's list, since "
                  f"that's the geometry the weights encode.")
    else:
        pool, center_skip, features = cli_pool, cli_center_skip, disk_features
        keep_early_res, early_attn = False, False
        early_attn_kv_stride, early_attn_heads = 1, 4
        early_attn_pos_mode = 'none'
        print(f"Bare (pre-config) checkpoint: assuming pool={pool}, "
              f"center_skip={center_skip} from CLI flags - if loading "
              f"fails or results look wrong, pass the flags the model "
              f"was trained with.")
    cat_f, cont_f = split_features(features)
    model = GrouseResNet(
        cat_f, cont_f, pretrained=False, pool=pool, center_skip=center_skip,
        keep_early_resolution=keep_early_res, early_attn=early_attn,
        early_attn_heads=early_attn_heads,
        early_attn_kv_stride=early_attn_kv_stride,
        early_attn_pos_mode=early_attn_pos_mode).to(device)
    try:
        model.load_state_dict(state)
    except RuntimeError as e:
        raise SystemExit(
            f"Checkpoint doesn't match the model geometry "
            f"(pool={pool}, center_skip={center_skip}, "
            f"features={features}).\nOriginal error:\n{e}")
    model.eval()
    return model, features


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
        ax.set_title(f"Reliability - {name} temperature scaling")
        ax.legend(fontsize=8)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(
        description="Reliability analysis + temperature scaling for the "
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
    model, features = load_model(args.model, device, args.pool,
                                 args.center_skip, disk_features)

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
    print_table("RELIABILITY - BEFORE temperature scaling", rows_b)
    print(f"\n  ECE {ece_b:.4f} | MCE {mce_b:.4f} | Brier "
          f"{brier(probs, y):.4f} | NLL {nll(logits, y):.4f} | "
          f"AUC {auc_b:.4f} | AP {ap_b:.4f}")

    T = fit_temperature(logits, y)
    logits_c = logits / T
    probs_c = 1.0 / (1.0 + np.exp(-logits_c))
    rows_a, ece_a, mce_a = reliability(probs_c, y, args.bins)
    auc_a, ap_a = roc_auc(logits_c, y), average_precision(logits_c, y)
    print_table(f"RELIABILITY - AFTER temperature scaling (T = {T:.3f})",
                rows_a)
    print(f"\n  ECE {ece_a:.4f} | MCE {mce_a:.4f} | Brier "
          f"{brier(probs_c, y):.4f} | NLL {nll(logits_c, y):.4f} | "
          f"AUC {auc_a:.4f} | AP {ap_a:.4f}")
    print(f"\n  Ranking preserved: AUC before {auc_b:.6f} == after "
          f"{auc_a:.6f} -> {abs(auc_b - auc_a) < 1e-9}")

    if T > 1.05:
        verdict = (f"OVERCONFIDENT by a factor of ~{T:.2f}: raw "
                   f"probabilities are pushed toward the extremes; "
                   f"dividing logits by {T:.3f} corrects them. This is "
                   f"the direct explanation for saturated 'everything is "
                   f"red' maps at high alpha thresholds.")
    elif T < 0.95:
        verdict = (f"UNDERCONFIDENT (T={T:.2f} < 1): probabilities are "
                   f"compressed toward 0.5; scaling sharpens them.")
    else:
        verdict = (f"Already well calibrated (T={T:.2f} ~ 1): the map's "
                   f"appearance reflects what the model genuinely "
                   f"believes, so 'all red' would mean it genuinely "
                   f"rates the area uniformly high.")
    print(f"\nVERDICT: {verdict}")
    print("\nCAVEAT: probabilities are calibrated to the ~balanced "
          "validation prevalence, not to true landscape occupancy - "
          "inherent to the presence/pseudo-absence design.")

    os.makedirs(args.out, exist_ok=True)
    payload = {
        "temperature": float(T),
        "fitted_at": dt.datetime.now().isoformat(timespec="seconds"),
        "model_path": os.path.abspath(args.model),
        "regions": args.regions,
        "features": features,
        "flip_tta": bool(args.flip_tta),
        "n_points": int(len(logits)),
        "ece_before": ece_b, "ece_after": ece_a,
        "mce_before": mce_b, "mce_after": mce_a,
        "brier_before": brier(probs, y), "brier_after": brier(probs_c, y),
        "nll_before": nll(logits, y), "nll_after": nll(logits_c, y),
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
    print("predict.py picks up the temperature automatically from "
          "calibration.json.")
    print("NOTE: temperature calibrates probabilities to the ~50/50 "
          "presence/pseudo-absence validation design; it is symmetric "
          "about p=0.5 and can never move a score across it. If a "
          "predicted map lights up wall-to-wall, that is prior "
          "mismatch, not a bad temperature - use predict.py --prior "
          "<expected suitable fraction> or --style quantile.")


if __name__ == "__main__":
    main()
