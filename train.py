"""
train.py

Thin orchestrator, refactored from the original:
  - GeoJSON inputs -> grouse_data pipeline outputs (train/val positives
    from prepare_training_data.py, train/val negatives from
    generate_negatives.py, already spatially block-split - the old 4x4
    grid re-split is retired, since re-splitting would produce a second
    conflicting partition and reintroduce the leakage the block system
    prevents)
  - hardcoded CONUS mosaic paths -> per-region, per-year, content-
    validated rasters via grouse_data
  - model geometry -> discovered from whichever features actually have
    rasters on disk (intersected across regions), via FEATURE_SPEC

Positives keep 4x rotation augmentation (train AND val, matching the
original's index convention); negatives don't, also as original.

Defaults now encode the recipe that measured best on the validation set
(see the comparison below). The original recipe is still reachable:
    --pool mean --no-center-skip --no-augment --no-flip-tta \
    --ema 0 --dropout 0 --label-smoothing 0 --sched warm_restarts \
    --select-by loss

Measured on ME+NH+VT, per-POINT scores (the 4 stored rotations averaged):

    configuration                     AUC      AP    accuracy   val loss
    original recipe                 0.8653  0.8249    79.21%     0.335 (rising)
    + center skip, attn pool, reg   0.8858  0.8744    80.86%     0.061 (stable)
    + 4-member ensemble             0.8975  0.8900    81.80%       -

Usage:
    python train.py                          # all regions, 30 epochs
    python train.py --ensemble 4 --epochs 16 # the strongest configuration
    python train.py --regions ME --epochs 5
    python train.py --use-weights            # envelope-derived negative weights
    python train.py --features evt evh sclass ch   # explicit geometry
"""
import argparse
import sys
import os

# grouse_data.py may sit next to this script (flat layout) or one
# directory up (the original ml/ subfolder layout). Search for it rather
# than assuming a fixed depth - assuming depth is what broke on a flat
# deployment: dirname(dirname(...)) computed the PARENT of the project
# folder, inserted it ahead of the real one in sys.path, and a same-named
# stray file up there got imported instead.
_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _here)
if not os.path.exists(os.path.join(_here, "grouse_data.py")):
    _parent = os.path.dirname(_here)
    if os.path.exists(os.path.join(_parent, "grouse_data.py")):
        sys.path.insert(0, _parent)
    else:
        raise SystemExit(
            f"Could not find grouse_data.py next to {__file__} or in "
            f"its parent directory ({_parent}). Run train.py from the "
            f"project directory that contains grouse_data.py.")

from torch.utils.data import ConcatDataset

from grouse_data import GrouseData
from models import FEATURE_SPEC, split_features
from dataset import GrousePatchDataset
from model_handler import GrouseModelHandler

IMG_SIZE = 64
# Batch size is the single biggest THROUGHPUT knob for the DEFAULT
# architecture, and also the single biggest MEMORY knob for every
# architecture - which is why it stays at 32 and you raise it
# deliberately.
#
# On the default geometry, 64x64 inputs give feature maps of 16x16
# (layer1) down to 8x8 (layer4). Those launch CUDA grids too small to
# fill a modern GPU's SMs, so throughput scales steeply with batch size
# (measured, A10G, default architecture):
#
#     batch    32    64   128   256   512
#     samp/s 1673  2795  3100  3282  3400
#
# That is also why a g4dn (T4, 40 SMs) and a g5 (A10G, 80 SMs) ran this
# at nearly the same speed: at batch 32 the extra SMs had nothing to
# schedule. On that geometry --batch-size 128 is ~2.5x end to end.
#
# It does NOT transfer to every flag combination. --keep-early-
# resolution holds layer1 at 32x32 and everything after it at 16x16
# (4x the activations), and --early-attn costs memory QUADRATIC in
# token count - 32x32 = 1024 tokens means the attention matrix alone is
# ~0.27 GB at batch 32 and ~1.07 GB at batch 128. Those configurations
# both fill the SMs at a smaller batch and run out of memory sooner, so
# they gain little and risk OOM. Raise this after checking it fits.
BATCH_SIZE = 32
# The batch size the tuned recipe's --lr was measured at; --lr-scaling
# is applied relative to this, so the default reproduces the tuned
# recipe exactly and only an explicit --batch-size changes the LR.
REFERENCE_BATCH_SIZE = 32
# Patch assembly is raster-read bound, so loader workers are what keep
# the GPU fed. Scale to the machine (leaving 2 cores for the training
# loop and the pin_memory thread) rather than assuming a laptop's 4.
WORKERS = max(1, (os.cpu_count() or 4) - 2)


def discover_features(data, regions):
    """Features usable for the model = those with rasters on disk in
    EVERY requested region, intersected with FEATURE_SPEC. This is the
    dynamic-geometry entry point: drop a new feature's rasters into
    landfire_data/ and it joins the model; delete them and it leaves."""
    sets = []
    for region in regions:
        avail = set(data[region].available_features())
        sets.append(avail & set(FEATURE_SPEC))
    usable = sorted(set.intersection(*sets),
                    key=lambda f: list(FEATURE_SPEC).index(f))
    return usable


def sample_background_points(rd, features, n, seed=0):
    """n uniformly random locations inside the region's reference
    raster, filtered to valid data at the center pixel - the random
    "assumed negative" background locations of Cole et al.'s L_AN-full.
    Deliberately NOT buffered away from known presences: assuming
    negatives everywhere (and accepting the resulting label noise) is
    the loss's design; its positive up-weighting is what absorbs the
    false negatives this creates."""
    import numpy as np
    import pandas as pd
    import rasterio
    from pyproj import Transformer
    from dataset import NODATA_SENTINELS

    feat = features[0]                     # spec order: categorical first
    path = rd.latest_raster_path(feat)
    year = max(rd.raster_years(feat))
    rng = np.random.default_rng(seed)
    lons, lats = [], []
    with rasterio.open(path) as src:
        to_lonlat = Transformer.from_crs(src.crs, "EPSG:4326",
                                         always_xy=True)
        nodata = src.nodata if src.nodata is not None else -9999
        bad = set(NODATA_SENTINELS) | {nodata, 0}
        attempts = 0
        while len(lons) < n and attempts < 40:
            attempts += 1
            m = max(64, 2 * (n - len(lons)))
            rows = rng.integers(0, src.height, m)
            cols = rng.integers(0, src.width, m)
            xs, ys = rasterio.transform.xy(src.transform, rows, cols)
            vals = np.array([v[0] for v in
                             src.sample(zip(xs, ys))], dtype=np.float64)
            ok = ~np.isin(vals, list(bad)) & np.isfinite(vals)
            if ok.any():
                glon, glat = to_lonlat.transform(
                    np.asarray(xs)[ok], np.asarray(ys)[ok])
                lons.extend(np.atleast_1d(glon)[:n - len(lons)])
                lats.extend(np.atleast_1d(glat)[:n - len(lats)])
        if len(lons) < n:
            raise SystemExit(
                f"Background sampling found only {len(lons)}/{n} valid "
                f"locations in {path} after {attempts} rounds - the "
                f"raster may be mostly nodata.")
    return pd.DataFrame({"longitude": lons, "latitude": lats,
                         "year": int(year), "label": 0.0, "weight": 1.0})


def filter_by_year_gap(df, rd, features, tolerance, what, region):
    """Drop TRAINING records whose sighting year has no raster within
    +/-tolerance years for one or more features - environmental data
    that far from the sighting date describes a different landscape, so
    the record is not evidence about its own label. Records with no
    year are kept (the dataset assigns them the latest vintage, i.e.
    they claim current conditions). tolerance < 0 disables."""
    if (tolerance < 0 or 'year' not in df.columns
            or df['year'].isna().all()):
        return df
    yrs = {f: rd.raster_years(f) for f in features}
    yrs = {f: ys for f, ys in yrs.items() if ys}

    def ok(year):
        year = int(year)
        return all(min(abs(y - year) for y in ys) <= tolerance
                   for ys in yrs.values())

    verdict = {int(y): ok(y) for y in df['year'].dropna().unique()}
    keep = df['year'].map(lambda y: verdict.get(int(y), True)
                          if not (y != y) else True)   # NaN-safe
    dropped = int((~keep).sum())
    if dropped:
        bad = sorted(y for y, v in verdict.items() if not v)
        print(f"   {region}: EXCLUDED {dropped:,} {what} records - "
              f"sighting years {bad} have no raster within "
              f"+/-{tolerance} years for at least one feature "
              f"({len(df) - dropped:,} kept).")
    return df[keep].reset_index(drop=True)


def build_datasets(data, regions, features, img_size, cache_dir=None,
                   jitter=0, augment=False, background_per_pos=0.0,
                   seed=0, train_year_gap=2):
    import numpy as np
    cat_f, cont_f = split_features(features)
    train_parts, val_parts, train_labels = [], [], []
    aug = dict(cache_dir=cache_dir, jitter=jitter, augment=augment)
    for region in regions:
        rd = data[region]
        # Year-gap exclusion applies to TRAINING only. Validation keeps
        # every point so metrics stay comparable across runs and across
        # this policy's introduction (old-year val points still carry
        # the once-per-feature staleness warning from grouse_data).
        pos_df = filter_by_year_gap(rd.positives("train"), rd, features,
                                    train_year_gap, "positive", region)
        neg_df = filter_by_year_gap(rd.negatives("train"), rd, features,
                                    train_year_gap, "negative", region)
        # Rotation expansion applied to BOTH classes (symmetric 4x ->
        # 1:1 effective balance; see earlier collapse diagnosis).
        p_tr = GrousePatchDataset(pos_df, rd, cat_f, cont_f,
                                  img_size=img_size, expand_rotations=True,
                                  label=1.0, **aug)
        n_tr = GrousePatchDataset(neg_df, rd, cat_f, cont_f,
                                  img_size=img_size, expand_rotations=True,
                                  label=0.0, **aug)
        train_parts += [p_tr, n_tr]
        train_labels += [p_tr.labels, n_tr.labels]
        if background_per_pos > 0:
            n_bg = int(round(background_per_pos * len(pos_df)))
            if n_bg > 0:
                bg_df = sample_background_points(rd, features, n_bg,
                                                 seed=seed)
                bg_tr = GrousePatchDataset(bg_df, rd, cat_f, cont_f,
                                           img_size=img_size,
                                           expand_rotations=True,
                                           label=0.0, **aug)
                train_parts.append(bg_tr)
                train_labels.append(bg_tr.labels)
                print(f"   {region}: +{n_bg:,} random background "
                      f"assumed-negatives (x{background_per_pos:g} per "
                      f"positive; train only - validation unchanged).")
        # Validation is never augmented: the 4 fixed rotations are kept so
        # val scores stay comparable across runs (and so the evaluator can
        # average them per point as test-time augmentation).
        val_parts.append(GrousePatchDataset(
            rd.positives("val"), rd, cat_f, cont_f, img_size=img_size,
            expand_rotations=True, label=1.0, cache_dir=cache_dir))
        val_parts.append(GrousePatchDataset(
            rd.negatives("val"), rd, cat_f, cont_f, img_size=img_size,
            expand_rotations=True, label=0.0, cache_dir=cache_dir))
    return (ConcatDataset(train_parts), ConcatDataset(val_parts),
            np.concatenate(train_labels))


# Ensemble member recipes. Deliberately NOT just different seeds: on this
# data four same-shaped models agree with each other and averaging them
# barely helps, while models that pool differently and regularize
# differently make different mistakes. Measured on the val set, averaging
# four of these lifted per-point AUC from 0.878 (best single) to 0.899.
ENSEMBLE_MEMBERS = [
    {"pool": "attn",  "dropout": 0.2, "label_smoothing": 0.05,
     "weight_decay": 1e-4},
    {"pool": "gauss", "dropout": 0.2, "label_smoothing": 0.05,
     "weight_decay": 1e-4},
    {"pool": "attn",  "dropout": 0.4, "label_smoothing": 0.10,
     "weight_decay": 1e-3},
    {"pool": "gauss", "dropout": 0.0, "label_smoothing": 0.00,
     "weight_decay": 1e-4},
]


def score_ensemble(members, features, val_ds, args):
    """Average the members' per-point scores and report the result.
    Members are z-scored first: they are trained with different losses and
    smoothing, so their logits live on different scales and a raw average
    would let the widest-scaled member dominate the vote."""
    import numpy as np
    import torch
    from torch.utils.data import DataLoader
    from models import GrouseResNet
    from model_handler import roc_auc, average_precision

    cat_f, cont_f = split_features(features)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    loader = DataLoader(val_ds, batch_size=256, num_workers=args.workers)
    per_member, ys = [], None
    for path, pool in members:
        state, cfg = GrouseModelHandler.unwrap_checkpoint(
            torch.load(path, map_location=device, weights_only=True))
        # Rebuild each member from its own stored config - members can
        # carry geometry beyond pooling (early_attn, keep_early_
        # resolution), and a guessed constructor either fails to load or
        # silently runs the wrong architecture. CLI args are only the
        # fallback for bare-state_dict checkpoints. Position-mode legacy
        # chain: new checkpoints store early_attn_pos_mode; ones from
        # the interim sin-cos fix store early_attn_pos_enc (bool); older
        # ones store neither and trained position-blind.
        cfg = cfg or {}
        pos_mode = cfg.get("early_attn_pos_mode")
        if pos_mode is None:
            pos_mode = 'abs' if cfg.get("early_attn_pos_enc") else 'none'
        model = GrouseResNet(
            cat_f, cont_f, pretrained=False,
            pool=cfg.get("pool", pool),
            center_skip=cfg.get("center_skip", args.center_skip),
            keep_early_resolution=cfg.get("keep_early_resolution",
                                          args.keep_early_resolution),
            early_attn=cfg.get("early_attn", args.early_attn),
            early_attn_heads=cfg.get("early_attn_heads",
                                     args.early_attn_heads),
            early_attn_kv_stride=cfg.get("early_attn_kv_stride",
                                         args.early_attn_kv_stride),
            early_attn_pos_mode=pos_mode,
            dual_branch=cfg.get("dual_branch", args.dual_branch),
            dual_branch_channels=cfg.get("dual_branch_channels",
                                         args.dual_branch_channels),
        ).to(device).eval()
        model.load_state_dict(state)
        outs, labels = [], []
        with torch.no_grad():
            for cat_x, cont_x, y, _w in loader:
                cat_x, cont_x = cat_x.to(device), cont_x.to(device)
                o = model.logits(cat_x, cont_x).float()
                if args.flip_tta:
                    o = 0.5 * (o + model.logits(cat_x.flip(-1),
                                                cont_x.flip(-1)).float())
                outs.append(o.squeeze(1).cpu())
                labels.append(y)
        lo = torch.cat(outs).numpy().reshape(-1, 4).mean(axis=1)
        ys = torch.cat(labels).numpy().reshape(-1, 4)[:, 0]
        per_member.append((lo - lo.mean()) / (lo.std() + 1e-9))
        print(f"   member {path.split('.')[-1]:>8s} ({pool:5s}): "
              f"AUC {roc_auc(lo, ys):.4f} | AP {average_precision(lo, ys):.4f}")
    ens = np.mean(per_member, axis=0)
    print(f"\nENSEMBLE of {len(per_member)} | per-point AUC "
          f"{roc_auc(ens, ys):.4f} | AP {average_precision(ens, ys):.4f} | "
          f"accuracy {100 * ((ens >= 0) == (ys == 1)).mean():.2f}%")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--regions", nargs="+", default=["ME", "NH", "VT"])
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--img-size", type=int, default=IMG_SIZE)
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    parser.add_argument("--eval-batch-size", type=int, default=None,
                        help="Batch size for validation only. Validation "
                             "runs no optimizer, so this changes nothing "
                             "about the reported metrics - only speed and "
                             "peak memory. Default: --batch-size, widened "
                             "automatically when the model has no "
                             "quadratic-memory attention block.")
    parser.add_argument("--workers", type=int, default=WORKERS)
    parser.add_argument("--features", nargs="+", default=None,
                        help="Explicit feature list; default: discover "
                             "from rasters on disk.")
    parser.add_argument("--use-weights", action="store_true",
                        help="Weight negative samples by their envelope-"
                             "derived weights (default off = original "
                             "behavior).")
    parser.add_argument("--batch-pos-frac", type=float, nargs="+",
                        default=None,
                        help="Batch composition control. Default (no "
                             "flag): ALTERNATING 25/75 <-> 75/25 batches "
                             "- net 50/50 per pair, but no single batch "
                             "rewards constant guessing. One value (e.g. "
                             "0.5): every batch fixed at that positive "
                             "fraction. Two values (e.g. 0.3 0.7): "
                             "alternate between them. -1: disable "
                             "stratification (plain shuffling).")
    parser.add_argument("--no-pretrained", action="store_true",
                        help="Skip ImageNet weights (offline/test runs).")
    parser.add_argument("--init-from", default=None,
                        help="Path to a self-supervised backbone "
                             "checkpoint from pretrain.py. Matching "
                             "tensors (stem, embeddings, ResNet stages, "
                             "CBAM, early-attn) are loaded and train in "
                             "the reduced-LR backbone group; head layers "
                             "stay fresh. Overwrites ImageNet weights "
                             "where they overlap, so pair with "
                             "--no-pretrained to skip the pointless "
                             "download. Geometry flags must match the "
                             "pretraining run for full transfer.")
    parser.add_argument("--save-path", default="grouse_single_best.pth")
    parser.add_argument("--cache-dir", default="data/cache",
                        help="Materialize patches once into a memmapped "
                             "array here. '' disables.")
    parser.add_argument("--jitter", type=int, default=0,
                        help="Random center offset in pixels for training "
                             "augmentation (0 = off).")
    parser.add_argument("--max-train-year-gap", type=int, default=2,
                        help="TRAINING records are EXCLUDED when their "
                             "sighting year has no raster within this "
                             "many years for one or more features - "
                             "environmental data that stale describes a "
                             "different landscape than the sighting saw. "
                             "Validation is never filtered (metrics stay "
                             "comparable across runs). -1 disables and "
                             "restores nearest-year-whatever-the-gap.")
    parser.add_argument("--augment", action=argparse.BooleanOptionalAction,
                        default=True,
                        help="Random D4 orientation (+ jitter, if set) per "
                             "training access, instead of the fixed idx%%4 "
                             "rotation. --no-augment for the old behavior.")
    parser.add_argument("--metrics-csv", default=None,
                        help="Append per-epoch metrics to this CSV.")
    parser.add_argument("--pool", default="attn",
                        choices=["mean", "center", "gauss", "attn"],
                        help="How the spatial logit map collapses to one "
                             "logit. 'mean' spreads the center point's "
                             "label over the whole 1.9km patch.")
    parser.add_argument("--keep-early-resolution",
                        action=argparse.BooleanOptionalAction, default=False,
                        help="Flatten the stem maxpool's stride so the "
                             "feature map stays at 32x32 (one 30m pixel "
                             "per token) through layer1, instead of the "
                             "default 16x16. Required for --early-attn "
                             "to operate at full pixel fidelity.")
    parser.add_argument("--early-attn",
                        action=argparse.BooleanOptionalAction, default=False,
                        help="Insert a self-attention transformer block "
                             "after layer1 - computes genuine pairwise "
                             "relationships between spatial tokens before "
                             "any downsampling has smeared them together "
                             "(unlike --pool attn, which only attends "
                             "over the already-downsampled final map). "
                             "Pair with --keep-early-resolution for full "
                             "pixel-level attention.")
    parser.add_argument("--early-attn-heads", type=int, default=4)
    parser.add_argument("--early-attn-dropout", type=float, default=0.1,
                        help="Dropout on the early-attn block's attention "
                             "weights. The block sits outside the reach "
                             "of --dropout/--embed-dropout, so this is "
                             "its only activation-level regularizer.")
    parser.add_argument("--early-attn-droppath", type=float, default=0.1,
                        help="Per-sample stochastic depth on the early-"
                             "attn block's two residual branches.")
    parser.add_argument("--early-attn-lr-factor", type=float, default=0.1,
                        help="LR multiplier for the early-attn block's "
                             "parameters (relative to --lr). At 1.0 the "
                             "block was the fastest-learning module in "
                             "the network and memorized hard examples "
                             "once focal loss switched on; 0.1 paces it "
                             "to the pretrained trunk.")
    parser.add_argument("--early-attn-pos", default="rel",
                        choices=["rel", "abs", "none"],
                        help="How the early-attn block sees position. "
                             "'rel' (default): 2D rotary embeddings on "
                             "Q/K plus a learned relative-offset bias - "
                             "every attention score is a joint function "
                             "of two pixels' feature stacks AND their "
                             "relative (drow, dcol) offset, identical "
                             "wherever the pair sits in the patch. This "
                             "directly encodes juxtaposition-driven "
                             "habitat structure (regenerating cover NEXT "
                             "TO conifer NEXT TO an opening). 'abs': "
                             "fixed 2D sin-cos added to Q/K (position-"
                             "aware but location-specific - relationships "
                             "must be relearned per location). 'none': "
                             "position-blind attention (the original "
                             "block; only a global content fingerprint - "
                             "a memorization channel).")
    parser.add_argument("--early-attn-kv-stride", type=int, default=1,
                        help="1 = full self-attention (every token "
                             "attends to every other - expensive: "
                             "O((HW)^2)). >1 = downsample keys/values by "
                             "this factor via a strided conv first "
                             "(queries stay full-res) - roughly "
                             "kv_stride^2 cheaper, small fidelity cost.")
    parser.add_argument("--dual-branch", default="off",
                        choices=["off", "unet", "dilated"],
                        help="Add a second, resolution-preserving "
                             "multi-scale branch ('Branch B') alongside "
                             "the ResNet trunk, fused into the final "
                             "logit through a zero-init head. The trunk "
                             "downsamples away exactly WHERE an edge or "
                             "conifer/deciduous transition sits; Branch "
                             "B keeps the native 64x64 grid and grows "
                             "its receptive field by dilation instead. "
                             "'unet' = shallow U-Net-lite with a "
                             "dilated bottleneck (recommended); "
                             "'dilated' = pure ASPP-style stack, no "
                             "downsampling at all. Ablate against "
                             "'off' - if the trunk (esp. with "
                             "--keep-early-resolution/--early-attn) "
                             "already captures it, B adds cost without "
                             "signal.")
    parser.add_argument("--dual-branch-channels", type=int, default=64)
    parser.add_argument("--center-skip",
                        action=argparse.BooleanOptionalAction, default=True,
                        help="Feed the center pixel's feature vector "
                             "straight to the head alongside the pooled "
                             "convolutional output.")
    parser.add_argument("--dropout", type=float, default=0.2)
    parser.add_argument("--embed-dropout", type=float, default=0.0)
    parser.add_argument("--label-smoothing", type=float, default=0.05)
    parser.add_argument("--ema", type=float, default=0.999,
                        help="Weight-EMA decay (e.g. 0.999); 0 = off.")
    parser.add_argument("--lr", type=float, default=3e-4,
                        help=f"Learning rate AT --batch-size "
                             f"{REFERENCE_BATCH_SIZE}; see --lr-scaling.")
    parser.add_argument("--lr-scaling", default="sqrt",
                        choices=["sqrt", "linear", "none"],
                        help="How --lr is adjusted for a batch size "
                             f"other than {REFERENCE_BATCH_SIZE}. A "
                             "bigger batch averages more samples per "
                             "gradient, so the same LR takes a smaller "
                             "effective step and the run sees "
                             "proportionally fewer of them. 'sqrt' "
                             "(default) is the standard rule for Adam-"
                             "family optimizers, whose update is already "
                             "gradient-magnitude normalized; 'linear' is "
                             "the SGD rule and is aggressive here; "
                             "'none' uses --lr verbatim. At --batch-size "
                             f"{REFERENCE_BATCH_SIZE} all three are "
                             "identical.")
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--loss", default="focal",
                        choices=["focal", "an_full"],
                        help="Training objective. 'focal' (default): the "
                             "existing BCE-warmup -> FocalLoss recipe. "
                             "'an_full': Cole et al.'s L_AN-full (full "
                             "assume-negative) - lambda-weighted BCE "
                             "where every negative (curated AND random "
                             "background, see --an-background) is "
                             "assumed to be a true negative and the "
                             "positive up-weight absorbs the resulting "
                             "false-negative noise. No focal phase; "
                             "--warmup-epochs/--focal-gamma are ignored.")
    parser.add_argument("--an-pos-weight", type=float, default=None,
                        help="lambda for --loss an_full: multiplier on "
                             "the positive loss terms. Default (auto): "
                             "1.0 under stratified batching (batches "
                             "are already class-balanced, so no "
                             "compensation is needed); the dataset's "
                             "neg:pos ratio when stratification is "
                             "disabled (--batch-pos-frac -1), matching "
                             "Cole et al.'s role for lambda of "
                             "offsetting the assumed-negative flood.")
    parser.add_argument("--an-background", type=float, default=0.0,
                        help="Random background assumed-negatives added "
                             "to TRAINING, as a multiple of each "
                             "region's positive count (Cole et al. use "
                             "1 random location per data location -> "
                             "1.0). Sampled uniformly over the region's "
                             "raster, valid-data filtered, NOT buffered "
                             "away from presences (assumed negative is "
                             "the point). Validation is untouched so "
                             "metrics stay comparable. 0 = off. Usable "
                             "with either --loss, but designed for "
                             "an_full.")
    parser.add_argument("--focal-gamma", type=float, default=2.0)
    parser.add_argument("--backbone-lr-factor", type=float, default=0.1)
    parser.add_argument("--sched", default="cosine",
                        choices=["warm_restarts", "cosine"])
    parser.add_argument("--warmup-epochs", type=int, default=3,
                        help="Epochs of alpha-weighted BCE (gamma=0) "
                             "before switching to FocalLoss.")
    parser.add_argument("--select-by", default="rank",
                        choices=["loss", "auc", "rank", "strict"],
                        help="Metric the best checkpoint is chosen on. "
                             "'rank' (default) = mean of per-point TTA AUC "
                             "and TTA AP - the two ranking metrics that "
                             "matter for deployment, which disagree "
                             "exactly when late-training memorization "
                             "inflates one at the other's expense "
                             "(measured: selecting on AUC alone kept "
                             "saving through epochs 12-30 for +0.002 AUC "
                             "- a third of that AUC's ~0.006 standard "
                             "error on this val set - while AP fell and "
                             "val loss rose 38%%). 'auc' = TTA AUC alone "
                             "(the old default). 'strict' = the "
                             "confidence-demanding accuracy defined by "
                             "--pos-threshold/--neg-threshold.")
    parser.add_argument("--select-min-delta", type=float, default=1e-3,
                        help="A new checkpoint must beat the LAST SAVED "
                             "one's selection score by at least this "
                             "margin. Filters noise-level 'improvements' "
                             "(max-based selection otherwise creeps "
                             "upward on measurement noise and replaces a "
                             "genuinely better earlier model); cumulative "
                             "real gains still save because comparison is "
                             "against the saved reference, not the "
                             "running max. 0 disables. Applies to every "
                             "--select-by mode ('loss' compares on "
                             "-val_loss, same magnitude).")
    parser.add_argument("--pos-threshold", type=float, default=0.75,
                        help="STRICT accuracy: a positive val point only "
                             "counts as correct when the model's "
                             "probability is >= this (default 0.75). "
                             "Predictions between the two thresholds "
                             "count as WRONG - hedging is penalized.")
    parser.add_argument("--neg-threshold", type=float, default=0.25,
                        help="STRICT accuracy: a negative val point only "
                             "counts as correct when the probability is "
                             "<= this (default 0.25).")
    parser.add_argument("--strict-objective",
                        action=argparse.BooleanOptionalAction, default=None,
                        help="Train with threshold-margin loss (positives "
                             "pushed past --pos-threshold, negatives past "
                             "--neg-threshold, hedging penalized). "
                             "Default: automatically ON when --select-by "
                             "strict, OFF otherwise.")
    parser.add_argument("--divergence-patience", type=int, default=3,
                        help="Consecutive epochs of strict accuracy "
                             "RISING while AUC and AP both FALL before "
                             "--on-divergence fires.")
    parser.add_argument("--on-divergence", default="warn",
                        choices=["warn", "dampen", "stop"],
                        help="'warn': log it, keep training (default). "
                             "'dampen': weaken the strict margins by "
                             "--divergence-dampen-factor and continue. "
                             "'stop': halt training at that epoch.")
    parser.add_argument("--divergence-dampen-factor", type=float,
                        default=0.5,
                        help="Multiplier applied to the strict-objective "
                             "margins each time 'dampen' triggers.")
    parser.add_argument("--flip-tta", action=argparse.BooleanOptionalAction,
                        default=True,
                        help="Average each validation view with its mirror "
                             "(completes the D4 group with the 4 stored "
                             "rotations).")
    parser.add_argument("--seed", type=int, default=0,
                        help="Seeds torch/numpy so two configurations can "
                             "be compared without run-to-run noise "
                             "masquerading as an effect.")
    parser.add_argument("--ensemble", type=int, default=1, metavar="N",
                        help="Train N members and score their averaged "
                             "prediction. Members differ in seed AND in "
                             "pooling/regularization (see ENSEMBLE_MEMBERS) "
                             "- disagreement between differently-shaped "
                             "models is what makes the average beat its "
                             "members. Saved as <save-path>.member<i>.")
    args = parser.parse_args()

    import numpy as _np
    import torch as _torch
    _torch.manual_seed(args.seed)
    _torch.cuda.manual_seed_all(args.seed)
    _np.random.seed(args.seed)

    data = GrouseData()
    features = args.features or discover_features(data, args.regions)
    if not features:
        raise SystemExit("No usable features found on disk for "
                         f"{args.regions} - check landfire_data/.")
    print(f"Model features ({'explicit' if args.features else 'discovered'}): "
          f"{features}")

    train_ds, val_ds, train_labels = build_datasets(
        data, args.regions, features, args.img_size,
        cache_dir=args.cache_dir or None, jitter=args.jitter,
        augment=args.augment, background_per_pos=args.an_background,
        seed=args.seed, train_year_gap=args.max_train_year_gap)
    print(f"Train samples: {len(train_ds):,} | Val samples: {len(val_ds):,}")

    disable = (args.batch_pos_frac is not None
               and len(args.batch_pos_frac) == 1
               and args.batch_pos_frac[0] < 0)
    if disable:
        frac_arg = None
    elif args.batch_pos_frac is None:
        frac_arg = None          # sampler's alternating default (25/75)
    elif len(args.batch_pos_frac) == 1:
        frac_arg = args.batch_pos_frac[0]
    else:
        frac_arg = tuple(args.batch_pos_frac)

    # lambda for L_AN-full. Under the default STRATIFIED batching the
    # sampler feeds every batch pair at net 50/50 regardless of dataset
    # composition (minority indices recycle), so the assumed-negative
    # flood Cole et al. offset with lambda never reaches the loss -
    # auto lambda is 1.0. Only with stratification disabled does the
    # raw dataset imbalance hit each batch, and lambda = neg:pos
    # restores the balance.
    an_pos_weight = 1.0
    if args.loss == 'an_full':
        if args.an_pos_weight is not None:
            an_pos_weight = float(args.an_pos_weight)
            why = "explicit"
        elif disable:
            n_pos = int((train_labels == 1).sum())
            n_neg = int((train_labels == 0).sum())
            an_pos_weight = n_neg / max(n_pos, 1)
            why = f"auto = neg:pos {n_neg:,}:{n_pos:,} (plain shuffling)"
        else:
            why = "auto = 1.0 (stratified batches are already balanced)"
        print(f"L_AN-full lambda (positive weight): {an_pos_weight:g} "
              f"[{why}]")

    # Scale the LR to the batch size. A batch of N averages N samples
    # into one gradient and one step, so at N=128 the run takes a
    # quarter as many steps as the recipe was tuned with; leaving --lr
    # alone would quietly turn a batch-size change into a much shorter
    # training run.
    ratio = args.batch_size / REFERENCE_BATCH_SIZE
    factor = {"sqrt": ratio ** 0.5, "linear": ratio, "none": 1.0}[
        args.lr_scaling]
    lr = args.lr * factor
    if abs(factor - 1.0) > 1e-9:
        print(f"LR scaling ({args.lr_scaling}): batch {args.batch_size} "
              f"is {ratio:g}x the reference {REFERENCE_BATCH_SIZE}, so "
              f"lr {args.lr:.2e} -> {lr:.2e}. Use --lr-scaling none to "
              f"disable, or --batch-size {REFERENCE_BATCH_SIZE} to "
              f"reproduce the tuned recipe exactly.")

    members = []
    for i in range(max(1, args.ensemble)):
        overrides = (ENSEMBLE_MEMBERS[i % len(ENSEMBLE_MEMBERS)]
                     if args.ensemble > 1 else {})
        if args.ensemble > 1:
            _torch.manual_seed(args.seed + i)
            _torch.cuda.manual_seed_all(args.seed + i)
            _np.random.seed(args.seed + i)
            path = f"{args.save_path}.member{i}"
            print(f"\n=== Ensemble member {i + 1}/{args.ensemble}: "
                  f"{overrides} ===")
        else:
            path = args.save_path
        handler = GrouseModelHandler(
            features,
            pretrained=not args.no_pretrained,
            use_sample_weights=args.use_weights,
            save_path=path,
            pool=overrides.get('pool', args.pool),
            dropout=overrides.get('dropout', args.dropout),
            center_skip=args.center_skip,
            embed_dropout=args.embed_dropout,
            keep_early_resolution=args.keep_early_resolution,
            early_attn=args.early_attn,
            early_attn_heads=args.early_attn_heads,
            early_attn_kv_stride=args.early_attn_kv_stride,
            early_attn_dropout=args.early_attn_dropout,
            early_attn_droppath=args.early_attn_droppath,
            early_attn_pos_mode=args.early_attn_pos,
            early_attn_lr_factor=args.early_attn_lr_factor,
            dual_branch=args.dual_branch,
            dual_branch_channels=args.dual_branch_channels,
            label_smoothing=overrides.get('label_smoothing',
                                          args.label_smoothing),
            ema_decay=args.ema, lr=lr,
            weight_decay=overrides.get('weight_decay', args.weight_decay),
            loss=args.loss, an_pos_weight=an_pos_weight,
            focal_gamma=args.focal_gamma,
            backbone_lr_factor=args.backbone_lr_factor,
            sched=args.sched,
            warmup_epochs=args.warmup_epochs,
            select_by=args.select_by,
            select_min_delta=args.select_min_delta,
            pos_threshold=args.pos_threshold,
            neg_threshold=args.neg_threshold,
            strict_objective=args.strict_objective,
            divergence_patience=args.divergence_patience,
            on_divergence=args.on_divergence,
            divergence_dampen_factor=args.divergence_dampen_factor,
            flip_tta=args.flip_tta)
        if args.init_from:
            handler.load_backbone(args.init_from)
        handler.fit(train_ds, val_ds, epochs=args.epochs,
                    batch_size=args.batch_size,
                    eval_batch_size=args.eval_batch_size,
                    workers=args.workers,
                    train_labels=None if disable else train_labels,
                    batch_pos_frac=frac_arg,
                    metrics_csv=args.metrics_csv)
        members.append((path, overrides.get('pool', args.pool)))

    if len(members) > 1:
        score_ensemble(members, features, val_ds, args)


if __name__ == "__main__":
    main()
