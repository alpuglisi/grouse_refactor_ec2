"""
pretrain.py

Self-supervised pretraining of the GrouseResNet backbone on UNLABELED
LANDFIRE tiles, via SimSiam (Chen & He, "Exploring Simple Siamese
Representation Learning", CVPR 2021).

WHY SIMSIAM HERE: the labeled dataset is ~12.7k points, but the rasters
cover three whole states - millions of unlabeled 64x64 tiles. SimSiam
learns from them with no labels, no negative pairs, and no momentum
encoder: two independently augmented views of the same tile are encoded,
and each view's projection must predict the other's (with a stop-
gradient on the target). What survives that objective is exactly what
the supervised task needs - a representation of habitat STRUCTURE that
is invariant to orientation and small shifts - because those are the
augmentations. Contrastive methods (SimCLR) need large batches of
negatives; masked autoencoding wants a ViT decoder; SimSiam works at
batch 128-256 on one GPU against this CNN backbone.

AUGMENTATIONS (the invariances being taught): random jitter crop (two
crops of the same padded read overlap but do not coincide), the full D4
orientation group (habitat has no canonical compass direction), and
whole-feature embedding dropout inside the encoder (--embed-dropout;
each forward pass draws its own mask, so the two views also differ in
which feature layers they see). RGB-style photometric jitter is
deliberately absent: these channels are categorical codes and scaled
physical values, not colors.

OUTPUT: a checkpoint whose state dict uses GrouseResNet's own key names
(head layers excluded), so train.py loads it directly:

    python pretrain.py --tiles 10000 --epochs 50
    python train.py --init-from grouse_ssl_backbone.pth [--no-pretrained]

Geometry flags (--keep-early-resolution, --early-attn, ...) must match
the intended fine-tune architecture so every backbone tensor transfers.

COLLAPSE MONITORING: SimSiam's known failure mode is representational
collapse (every tile maps to the same vector). The per-epoch "z-std"
is the standard detector - the mean per-dimension std of the
L2-normalized projections. Healthy: ~1/sqrt(dim) (~0.044 at 512).
Falling toward 0 = collapse; the run warns loudly if it does.
"""
import os
import sys
import math
import argparse
import datetime as dt

_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _here)

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import ConcatDataset, DataLoader
from tqdm import tqdm

from grouse_data import GrouseData
from models import GrouseResNet, split_features
from dataset import SSLPairDataset
from train import discover_features, sample_background_points, WORKERS

# Head keys never saved: they belong to the supervised task, and saving
# their random init would drag them into the fine-tune's reduced-LR
# "loaded backbone" group for no benefit.
HEAD_PREFIXES = ("conv_out.", "center_head.", "drop.")


class SimSiam(nn.Module):
    """Projector + predictor over GrouseResNet.features(), with the
    stop-gradient negative-cosine objective. Dimensions are the paper's
    architecture scaled to a 512-d ResNet-18 feature (the paper's
    ResNet-50 used 2048): projector keeps width with BN (final BN
    affine-free, as published), predictor is the 1/4-width bottleneck."""

    def __init__(self, encoder, dim=512, pred_dim=128):
        super().__init__()
        self.encoder = encoder
        self.projector = nn.Sequential(
            nn.Linear(dim, dim, bias=False), nn.BatchNorm1d(dim),
            nn.ReLU(inplace=True),
            nn.Linear(dim, dim, bias=False),
            nn.BatchNorm1d(dim, affine=False))
        self.predictor = nn.Sequential(
            nn.Linear(dim, pred_dim, bias=False),
            nn.BatchNorm1d(pred_dim), nn.ReLU(inplace=True),
            nn.Linear(pred_dim, dim))

    def forward(self, cat1, cont1, cat2, cont2):
        """-> (loss, z_std). The symmetric SimSiam loss
        L = -[cos(p1, sg(z2)) + cos(p2, sg(z1))] / 2 in [-1, 1];
        z_std is the collapse indicator (see module docstring)."""
        z1 = self.projector(self.encoder.features(cat1, cont1))
        z2 = self.projector(self.encoder.features(cat2, cont2))
        p1, p2 = self.predictor(z1), self.predictor(z2)
        loss = -0.5 * (F.cosine_similarity(p1, z2.detach(), dim=1).mean()
                       + F.cosine_similarity(p2, z1.detach(), dim=1).mean())
        with torch.no_grad():
            z_std = F.normalize(z1.float(), dim=1).std(dim=0).mean()
        return loss, z_std

    def backbone_state(self):
        """GrouseResNet-keyed state dict, head layers stripped - the
        artifact train.py --init-from consumes."""
        return {k: v.detach().cpu().clone()
                for k, v in self.encoder.state_dict().items()
                if not k.startswith(HEAD_PREFIXES)}


def main():
    parser = argparse.ArgumentParser(
        description="SimSiam self-supervised pretraining on unlabeled "
                    "LANDFIRE tiles; produces a backbone checkpoint for "
                    "train.py --init-from.")
    parser.add_argument("--regions", nargs="+", default=["ME", "NH", "VT"])
    parser.add_argument("--tiles", type=int, default=10000,
                        help="Unlabeled tiles sampled per region "
                             "(uniform over the raster, valid-data "
                             "filtered).")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--img-size", type=int, default=64)
    parser.add_argument("--jitter", type=int, default=8,
                        help="Max crop offset in pixels between the two "
                             "views (tiles are read padded by this).")
    parser.add_argument("--embed-dropout", type=float, default=0.1,
                        help="Whole-feature embedding dropout inside the "
                             "encoder - an augmentation here: each view's "
                             "forward pass drops its own random subset "
                             "of feature layers.")
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--workers", type=int, default=WORKERS)
    parser.add_argument("--cache-dir", default="data/cache",
                        help="Patch cache directory ('' disables). The "
                             "first epoch pays the raster reads; the "
                             "rest run from the memmap.")
    parser.add_argument("--features", nargs="+", default=None)
    parser.add_argument("--no-pretrained", action="store_true",
                        help="Start the backbone from scratch instead of "
                             "ImageNet weights.")
    parser.add_argument("--keep-early-resolution",
                        action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--early-attn",
                        action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--early-attn-heads", type=int, default=4)
    parser.add_argument("--early-attn-kv-stride", type=int, default=1)
    parser.add_argument("--early-attn-pos", default="rel",
                        choices=["rel", "abs", "none"])
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--save-path", default="grouse_ssl_backbone.pth")
    args = parser.parse_args()

    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)
    np.random.seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    data = GrouseData()
    features = args.features or discover_features(data, args.regions)
    if not features:
        raise SystemExit(f"No usable features on disk for {args.regions}.")
    cat_f, cont_f = split_features(features)
    print(f"Features: {features}")

    parts = []
    for i, region in enumerate(args.regions):
        rd = data[region]
        df = sample_background_points(rd, features, args.tiles,
                                      seed=args.seed + i)
        parts.append(SSLPairDataset(df, rd, cat_f, cont_f,
                                    img_size=args.img_size,
                                    jitter=args.jitter,
                                    cache_dir=args.cache_dir or None))
        print(f"   {region}: {len(df):,} unlabeled tiles")
    ds = ConcatDataset(parts)
    print(f"Total tiles: {len(ds):,} "
          f"({math.ceil(len(ds) / args.batch_size)} batches/epoch)")

    loader = DataLoader(ds, batch_size=args.batch_size, shuffle=True,
                        num_workers=args.workers,
                        pin_memory=(device.type == 'cuda'),
                        persistent_workers=args.workers > 0,
                        drop_last=True)   # BN in the projector needs >1

    encoder = GrouseResNet(
        cat_f, cont_f, pretrained=not args.no_pretrained, pool='mean',
        dropout=0.0, embed_dropout=args.embed_dropout, center_skip=False,
        keep_early_resolution=args.keep_early_resolution,
        early_attn=args.early_attn,
        early_attn_heads=args.early_attn_heads,
        early_attn_kv_stride=args.early_attn_kv_stride,
        early_attn_pos_mode=args.early_attn_pos)
    model = SimSiam(encoder).to(device)
    if device.type == 'cuda':
        torch.backends.cudnn.benchmark = True

    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr,
                                  weight_decay=args.weight_decay)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=args.epochs)
    scaler = (torch.amp.GradScaler('cuda')
              if device.type == 'cuda' else None)

    healthy_std = 1.0 / math.sqrt(512)
    for epoch in range(args.epochs):
        model.train()
        loss_sum = std_sum = 0.0
        n_steps = 0
        bar = tqdm(loader, desc=f"Epoch {epoch + 1}/{args.epochs}",
                   leave=False)
        for cat1, cont1, cat2, cont2 in bar:
            cat1, cont1 = cat1.to(device), cont1.to(device)
            cat2, cont2 = cat2.to(device), cont2.to(device)
            optimizer.zero_grad(set_to_none=True)
            if scaler is not None:
                with torch.amp.autocast('cuda'):
                    loss, z_std = model(cat1, cont1, cat2, cont2)
                scaler.scale(loss).backward()
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                scaler.step(optimizer)
                scaler.update()
            else:
                loss, z_std = model(cat1, cont1, cat2, cont2)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
            loss_sum += float(loss)
            std_sum += float(z_std)
            n_steps += 1
        scheduler.step()
        mean_loss = loss_sum / max(n_steps, 1)
        mean_std = std_sum / max(n_steps, 1)
        note = ""
        if mean_std < 0.25 * healthy_std:
            note = ("  [!] COLLAPSE WARNING: z-std far below the "
                    f"healthy ~{healthy_std:.3f} - representations are "
                    "converging to a constant. Lower --lr or raise "
                    "--jitter/--embed-dropout.")
        print(f"   Epoch {epoch + 1}/{args.epochs} | loss {mean_loss:.4f} "
              f"(floor -1) | z-std {mean_std:.4f} "
              f"(healthy ~{healthy_std:.3f}) | "
              f"lr {optimizer.param_groups[0]['lr']:.2e}{note}")
        # Saved every epoch: an interrupted run still leaves a usable
        # backbone (SSL loss is near-monotone; last is best in practice).
        torch.save({
            "state_dict": model.backbone_state(),
            "config": {
                "features": list(cat_f) + list(cont_f),
                "keep_early_resolution": args.keep_early_resolution,
                "early_attn": args.early_attn,
                "early_attn_heads": args.early_attn_heads,
                "early_attn_kv_stride": args.early_attn_kv_stride,
                "early_attn_pos_mode": args.early_attn_pos,
            },
            "ssl": {"method": "simsiam", "epoch": epoch + 1,
                    "epochs": args.epochs,
                    "tiles_per_region": args.tiles,
                    "regions": list(args.regions),
                    "loss": mean_loss, "z_std": mean_std,
                    "written_at": dt.datetime.now().isoformat(
                        timespec="seconds")},
        }, args.save_path)

    print(f"\nPretraining finished. Backbone saved to {args.save_path} - "
          f"fine-tune with:\n    python train.py --init-from "
          f"{args.save_path}"
          f"{' --keep-early-resolution' if args.keep_early_resolution else ''}"
          f"{' --early-attn' if args.early_attn else ''}")


if __name__ == "__main__":
    main()
