"""
smoke_test_training.py

Quick functionality test of the refactored ML stack against your real
pipeline data - NOT a real training run. Uses tiny subsets (default 40
points/class train, 10/class val, 2 epochs) so it finishes in a few
minutes on CPU and seconds on GPU, while still exercising every stage:

  grouse_data discovery -> feature detection -> patch extraction ->
  dynamic model construction -> both weighting modes -> checkpoint
  save/load -> both prediction paths

Run it from the directory containing the ml files + grouse_data.py +
your pipeline outputs (evaluated/thinned/negatives CSVs, landfire_data/):

    python smoke_test_training.py
    python smoke_test_training.py --region NH --n-train 20 --epochs 1
    python smoke_test_training.py --no-pretrained   # offline machines

Anything failing here would fail identically (but much later and more
expensively) in a full train.py run.
"""
import argparse
import os
import sys
import traceback

STEPS_PASSED = []


def step(name):
    print(f"\n=== {name} ===")
    STEPS_PASSED.append(name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", default="ME")
    parser.add_argument("--n-train", type=int, default=40,
                        help="points per class for training (x4 rotations "
                             "for positives)")
    parser.add_argument("--n-val", type=int, default=10)
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--img-size", type=int, default=64)
    parser.add_argument("--no-pretrained", action="store_true",
                        help="skip the ImageNet weight download (offline)")
    args = parser.parse_args()

    try:
        # ------------------------------------------------------------------
        step("1/7 Imports (torch, torchvision, the new ml files, grouse_data)")
        import torch
        from torch.utils.data import ConcatDataset
        from grouse_data import GrouseData
        from models import FEATURE_SPEC, split_features
        from dataset import GrousePatchDataset
        from model_handler import GrouseModelHandler
        print(f"    torch {torch.__version__} | "
              f"cuda available: {torch.cuda.is_available()}")

        # ------------------------------------------------------------------
        step(f"2/7 Data discovery for {args.region}")
        data = GrouseData()
        rd = data[args.region]
        feats = [f for f in rd.available_features() if f in FEATURE_SPEC]
        if not feats:
            raise SystemExit(f"No usable features on disk for {args.region} "
                             f"- check landfire_data/.")
        cat_f, cont_f = split_features(feats)
        print(f"    features: {feats}")
        print(f"    categorical: {cat_f} | continuous: {cont_f}")

        tr_pos = rd.positives("train")
        tr_neg = rd.negatives("train")
        va_pos = rd.positives("val")
        va_neg = rd.negatives("val")
        print(f"    on disk: {len(tr_pos):,} train pos, {len(tr_neg):,} "
              f"train neg, {len(va_pos):,} val pos, {len(va_neg):,} val neg")

        # ------------------------------------------------------------------
        step("3/7 Patch dataset construction + one sample inspection")
        train_ds = ConcatDataset([
            GrousePatchDataset(tr_pos.head(args.n_train), rd, cat_f, cont_f,
                               img_size=args.img_size,
                               expand_rotations=True, label=1.0),
            GrousePatchDataset(tr_neg.head(args.n_train), rd, cat_f, cont_f,
                               img_size=args.img_size,
                               expand_rotations=False, label=0.0)])
        val_ds = ConcatDataset([
            GrousePatchDataset(va_pos.head(args.n_val), rd, cat_f, cont_f,
                               img_size=args.img_size,
                               expand_rotations=True, label=1.0),
            GrousePatchDataset(va_neg.head(args.n_val), rd, cat_f, cont_f,
                               img_size=args.img_size,
                               expand_rotations=False, label=0.0)])
        cat_x, cont_x, y, w = train_ds[0]
        print(f"    train={len(train_ds)} samples, val={len(val_ds)} samples")
        print(f"    sample shapes: cat_x={tuple(cat_x.shape)} "
              f"({cat_x.dtype}), cont_x={tuple(cont_x.shape)} "
              f"({cont_x.dtype}), y={y.item()}, weight={w.item():.2f}")
        assert cat_x.shape == (len(cat_f), args.img_size, args.img_size)
        assert cont_x.shape == (len(cont_f), args.img_size, args.img_size)
        # negatives carry their envelope weights - check one
        _, _, yn, wn = train_ds[len(train_ds) - 1]
        print(f"    a negative sample: label={yn.item()}, "
              f"weight={wn.item():.2f} (envelope-derived if != 1.0)")

        # ------------------------------------------------------------------
        step("4/7 Model construction (dynamic geometry)")
        handler = GrouseModelHandler(
            feats, pretrained=not args.no_pretrained,
            save_path="data/models/smoke_test_model.pth")

        # ------------------------------------------------------------------
        step(f"5/7 Training loop ({args.epochs} epochs, unweighted - "
             f"original behavior)")
        handler.fit(train_ds, val_ds, epochs=args.epochs,
                    batch_size=args.batch_size, workers=0)

        # ------------------------------------------------------------------
        step("6/7 Weighted-loss mode (1 epoch)")
        handler_w = GrouseModelHandler(
            feats, pretrained=not args.no_pretrained,
            use_sample_weights=True,
            save_path="data/models/smoke_test_model_weighted.pth")
        handler_w.fit(train_ds, val_ds, epochs=1,
                      batch_size=args.batch_size, workers=0)

        # ------------------------------------------------------------------
        step("7/7 Checkpoint round-trip + both prediction paths")
        fresh = GrouseModelHandler(
            feats, pretrained=False,
            save_path="data/models/smoke_test_model.pth").load("data/models/smoke_test_model.pth")
        p = fresh.predict_proba(cat_x.unsqueeze(0), cont_x.unsqueeze(0))
        m = fresh.predict_map(cat_x.unsqueeze(0), cont_x.unsqueeze(0))
        print(f"    predict_proba: {p.item():.3f} | "
              f"predict_map: {tuple(m.shape)}")

        print("\n" + "=" * 50)
        print("ALL 7 STAGES PASSED - the stack is functional on your data.")
        print("Cleanup: rm smoke_test_model.pth smoke_test_model_weighted.pth")
        print("Full run: python train.py")
        print("=" * 50)

    except Exception:
        print("\n" + "!" * 50)
        print(f"FAILED during: {STEPS_PASSED[-1] if STEPS_PASSED else 'startup'}")
        print("!" * 50)
        traceback.print_exc()
        print("\nStages completed before failure:")
        for s in STEPS_PASSED[:-1]:
            print(f"  [ok] {s}")
        sys.exit(1)


if __name__ == "__main__":
    main()

