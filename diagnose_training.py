"""
diagnose_training.py

Answers three questions about the stalled training run, in order of
likelihood:

  1. COMPOSITION: what does the training set ACTUALLY look like after
     rotation expansion - how many positives vs negatives per region?
     (A severe imbalance here fully explains frozen accuracy: the model
     collapses to always predicting the majority class.)
  2. PARAMETER MOVEMENT: are the weights literally changing? Runs 5
     optimizer steps and measures the parameter-vector delta directly.
  3. PREDICTION COLLAPSE: what fraction of a val batch does the model
     call positive, and what do the raw logits look like? All-one-class
     with confident logits = collapse, not a frozen optimizer.

Run from the same directory as train.py:
    python diagnose_training.py
    python diagnose_training.py --regions ME NH VT
"""
import argparse

import torch
from torch.utils.data import ConcatDataset, DataLoader

from grouse_data import GrouseData
from models import FEATURE_SPEC, split_features
from dataset import GrousePatchDataset
from model_handler import GrouseModelHandler
from losses import FocalLoss


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--regions", nargs="+", default=["ME", "NH", "VT"])
    parser.add_argument("--img-size", type=int, default=64)
    args = parser.parse_args()

    data = GrouseData()

    # ------------------------------------------------------------------
    print("=" * 60)
    print("1. DATA COMPOSITION (the most likely culprit)")
    print("=" * 60)
    total_tr_pos = total_tr_neg = total_va_pos = total_va_neg = 0
    for region in args.regions:
        rd = data[region]
        try:
            tp, tn = len(rd.positives("train")), len(rd.negatives("train"))
            vp, vn = len(rd.positives("val")), len(rd.negatives("val"))
        except Exception as e:
            print(f"  {region}: FAILED to load files - {e}")
            continue
        total_tr_pos += tp; total_tr_neg += tn
        total_va_pos += vp; total_va_neg += vn
        print(f"  {region}: train {tp:,} pos / {tn:,} neg | "
              f"val {vp:,} pos / {vn:,} neg")

    eff_tr_pos = total_tr_pos * 4   # rotation expansion
    eff_va_pos = total_va_pos * 4
    print(f"\n  AFTER 4x rotation expansion (what the model actually sees):")
    print(f"    train: {eff_tr_pos:,} pos vs {total_tr_neg:,} neg "
          f"-> ratio {eff_tr_pos / max(total_tr_neg, 1):.1f} : 1")
    print(f"    val:   {eff_va_pos:,} pos vs {total_va_neg:,} neg "
          f"-> ratio {eff_va_pos / max(total_va_neg, 1):.1f} : 1")
    print(f"    expected train samples in train.py: "
          f"{eff_tr_pos + total_tr_neg:,}")
    print(f"    expected val samples in train.py:   "
          f"{eff_va_pos + total_va_neg:,}")
    maj = eff_va_pos / max(eff_va_pos + total_va_neg, 1) * 100
    print(f"    val accuracy if model just predicts ALL POSITIVE: {maj:.2f}%")
    print(f"    (compare to the frozen accuracy from your run)")
    if eff_tr_pos / max(total_tr_neg, 1) > 3:
        print(f"\n  [!] Training imbalance is severe. This alone explains "
             f"collapsed, frozen predictions. See the fix list the "
             f"assistant provided.")

    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("2. PARAMETER MOVEMENT (is the optimizer doing anything?)")
    print("=" * 60)
    region = args.regions[0]
    rd = data[region]
    feats = [f for f in rd.available_features() if f in FEATURE_SPEC]
    cat_f, cont_f = split_features(feats)
    small = ConcatDataset([
        GrousePatchDataset(rd.positives("train").head(8), rd, cat_f, cont_f,
                           img_size=args.img_size, expand_rotations=False,
                           label=1.0),
        GrousePatchDataset(rd.negatives("train").head(8), rd, cat_f, cont_f,
                           img_size=args.img_size, expand_rotations=False,
                           label=0.0)])
    loader = DataLoader(small, batch_size=4, shuffle=True, num_workers=0)

    handler = GrouseModelHandler(feats, pretrained=False,
                                 save_path="/dev/null")
    model = handler.model
    opt = torch.optim.AdamW(model.parameters(), lr=0.0003, weight_decay=1e-2)
    crit = FocalLoss(alpha=0.25, gamma=2.0)

    with torch.no_grad():
        before = torch.cat([p.flatten() for p in model.parameters()]).clone()
    model.train()
    steps = 0
    for cat_x, cont_x, y, w in loader:
        out = model(cat_x.to(handler.device),
                    cont_x.to(handler.device)).mean(dim=(2, 3))
        loss = crit(out, y.to(handler.device).unsqueeze(1))
        opt.zero_grad(set_to_none=True)
        loss.backward()
        grad_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        steps += 1
        print(f"  step {steps}: loss={loss.item():.5f}, "
              f"grad norm (pre-clip)={grad_norm:.5f}")
        if steps >= 5:
            break
    with torch.no_grad():
        after = torch.cat([p.flatten() for p in model.parameters()])
        delta = (after - before).abs()
    print(f"  parameter delta over {steps} steps: "
          f"mean {delta.mean():.2e}, max {delta.max():.2e}")
    print(f"  -> {'WEIGHTS ARE MOVING' if delta.max() > 0 else 'WEIGHTS FROZEN (real optimizer bug)'}")

    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("3. PREDICTION DISTRIBUTION (collapse check)")
    print("=" * 60)
    print("  Loading your trained checkpoint if present "
          "(grouse_single_best.pth)...")
    try:
        handler2 = GrouseModelHandler(feats, pretrained=False,
                                      save_path="data/models/grouse_single_best.pth")
        handler2.load("data/models/grouse_single_best.pth")
        val_small = ConcatDataset([
            GrousePatchDataset(rd.positives("val").head(32), rd, cat_f,
                               cont_f, img_size=args.img_size,
                               expand_rotations=False, label=1.0),
            GrousePatchDataset(rd.negatives("val").head(32), rd, cat_f,
                               cont_f, img_size=args.img_size,
                               expand_rotations=False, label=0.0)])
        vloader = DataLoader(val_small, batch_size=16, num_workers=0)
        all_logits, all_labels = [], []
        handler2.model.eval()
        with torch.no_grad():
            for cat_x, cont_x, y, w in vloader:
                out = handler2.model(
                    cat_x.to(handler2.device),
                    cont_x.to(handler2.device)).mean(dim=(2, 3))
                all_logits.append(out.cpu().squeeze(1))
                all_labels.append(y)
        logits = torch.cat(all_logits)
        labels = torch.cat(all_labels)
        probs = torch.sigmoid(logits)
        pred_pos = (probs >= 0.5).float().mean() * 100
        print(f"  logits: mean {logits.mean():.3f}, std {logits.std():.3f}, "
              f"range [{logits.min():.3f}, {logits.max():.3f}]")
        print(f"  predicted positive: {pred_pos:.1f}% of a balanced "
              f"64-sample val slice (true composition: 50%)")
        if pred_pos > 95 or pred_pos < 5:
            print(f"  -> COLLAPSED: the model predicts one class for "
                 f"essentially everything.")
        elif logits.std() < 0.05:
            print(f"  -> NEAR-CONSTANT logits: outputs barely vary with "
                 f"input; effectively collapsed.")
        else:
            print(f"  -> Predictions vary with input; if metrics are still "
                 f"frozen, the issue is elsewhere.")
    except FileNotFoundError:
        print("  grouse_single_best.pth not found in this directory - "
             "run from where train.py saved it, or skip this section.")


if __name__ == "__main__":
    main()

