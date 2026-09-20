"""
predict.py

Habitat-suitability prediction over a region (or custom bounding box),
refactored from the previous project's version for the current pipeline:

  - Rasters come from grouse_data (per-region, latest valid year,
    content-validated) instead of hardcoded CONUS mosaic paths; every
    layer is aligned to the reference grid through a WarpedVRT, so
    minor grid/CRS differences can't silently misalign channels.
  - Model geometry is DISCOVERED from FEATURE_SPEC + rasters on disk
    (same mechanism as train.py), so this script tracks the trained
    feature set automatically. A checkpoint/feature mismatch fails with
    an explanatory error instead of a bare size-mismatch traceback.
  - 4-rotation test-time augmentation preserved (it mirrors the
    training-time augmentation); the old aspect sin/cos "compass
    correction" is gone because no current channel is directional.
  - Tiled scanning (row strips) replaces the load-everything-into-RAM
    approach, so whole-state predictions fit in memory.
  - Nodata is handled honestly: cells whose center pixel is nodata on
    the reference layer are masked out (NaN in the GeoTIFF, transparent
    in the KMZ) instead of being predicted-on-garbage and hidden.

KMZ generation (present in the original, kept and fixed): the output
GeoTIFF is reprojected to lat/lon, colorized, and packaged as a Google
Earth GroundOverlay. Three explicit styles:
  --style absolute  (default) color = the model's actual probability;
                    comparable across regions and model versions
  --style quantile  color = the cell's rank within THIS map (0..1);
                    --alpha-below then hides everything below that
                    quantile ("0.8 = show the top 20% of the box").
                    The right product when the deployed use is ranking
                    candidate habitat inside an area of interest.
  --style stretched 2-98 percentile stretch + gamma, like the original
                    (which claimed "no normalization" while doing this);
                    maximizes local contrast, NOT comparable across maps

PROBABILITY SEMANTICS / why a whole-forest box can light up: the model
is trained and calibrated on a ~50/50 presence/pseudo-absence design
(see calibrate.py "HONEST LIMITS"), so p=0.5 means "even odds AGAINST A
SAMPLED PSEUDO-ABSENCE", not "50% of such cells hold grouse". Over a
real landscape whose suitable fraction is far below 50%, those
probabilities read inflated - and temperature scaling cannot shift
them, because sigmoid(logit/T) is symmetric about p=0.5: no T moves a
score across 0.5. Fixes: --prior <f> re-anchors the calibrated logits
to an expected deployment prevalence f (the standard
logit(f)-logit(0.5) prior correction), or --style quantile sidesteps
absolute probabilities entirely.

Usage:
    python predict.py --region ME
    python predict.py --region ME --bounds -70.5 44.2 -70.1 44.5
    python predict.py --region NH --stride 8 --style stretched
    python predict.py --region ME --tif-only
"""
import os
import sys
import json
import math
import zipfile
import argparse
import tempfile
import datetime as dt

import numpy as np
import torch
import rasterio
import rasterio.transform
from rasterio.vrt import WarpedVRT
from rasterio.windows import Window
from rasterio.warp import reproject, Resampling
from tqdm import tqdm
from pyproj import Transformer
from PIL import Image
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _here)
if not os.path.exists(os.path.join(_here, "grouse_data.py")):
    _parent = os.path.dirname(_here)
    if os.path.exists(os.path.join(_parent, "grouse_data.py")):
        sys.path.insert(0, _parent)

from grouse_data import GrouseData, NLCD_NAMES, NODATA_SENTINELS
from models import (GrouseResNet, FEATURE_SPEC, split_features,
                    config_to_model_kwargs, d4_tta_logits,
                    spec_with_checkpoint_vocab, checkpoint_vocab_notes)
from losses import loss_logit_bias
from prepare_training_data import BOXES

IMG_SIZE = 64
STRIP_TARGET_ROWS = 2048        # rows of raster processed per tile
OUT_DIR = "data/predictions"


# ==========================================
# Model loading
# ==========================================
def load_model(model_path, disk_features, device, cli_pool="attn",
               cli_center_skip=True):
    """Loads either checkpoint format:
      - WRAPPED (current): {"state_dict", "config": {pool, center_skip,
        features}} - geometry comes from the config, which is
        authoritative (the weights encode it).
      - BARE (older runs): a raw state_dict - geometry falls back to the
        CLI flags + disk-discovered features."""
    from model_handler import GrouseModelHandler
    obj = torch.load(model_path, map_location=device, weights_only=True)
    state, cfg = GrouseModelHandler.unwrap_checkpoint(obj)
    first_key = next(iter(state))
    if first_key.startswith("_orig_mod."):
        print("   Detected torch.compile checkpoint - stripping prefix.")
        state = {k[len("_orig_mod."):]: v for k, v in state.items()}
    # config_to_model_kwargs owns every geometry key and legacy chain
    # (pos-enc bools, dual-branch defaults, ...) in one place - the CLI
    # pool/center-skip flags act only as fallbacks for bare checkpoints.
    kw = config_to_model_kwargs(cfg, defaults=dict(
        pool=cli_pool, center_skip=cli_center_skip))
    if cfg is not None:
        features = cfg.get("features", disk_features)
        print(f"   Checkpoint config: pool={kw['pool']}, "
              f"center_skip={kw['center_skip']}")
        if set(features) != set(disk_features):
            print(f"   [note] checkpoint features {features} differ from "
                  f"disk {disk_features} - using the checkpoint's list.")
    else:
        features = disk_features
        print(f"   Bare (pre-config) checkpoint: assuming "
              f"pool={kw['pool']}, center_skip={kw['center_skip']} - "
              f"pass --pool/--center-skip matching the training run if "
              f"this is wrong.")
    cat_f, cont_f = split_features(features)
    # Embedding vocab sizes come from the checkpoint's own tables, not
    # today's FEATURE_SPEC - a checkpoint trained under the old evh/evc
    # vocab of 300 must keep loading (and keep clamping exactly as it
    # was trained to; see models.spec_with_checkpoint_vocab).
    spec = spec_with_checkpoint_vocab(state)
    for note in checkpoint_vocab_notes(spec, cat_f):
        print(f"   [note] checkpoint {note} - rebuilt with the "
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
    return model, cat_f, cont_f, features, cfg


# ==========================================
# Prediction
# ==========================================
def open_aligned_sources(rd, cat_f, cont_f):
    """Open every feature's latest valid raster; wrap all non-reference
    layers in a WarpedVRT matched to the reference grid so channel
    alignment is guaranteed even if grids differ slightly."""
    feats = cat_f + cont_f
    paths = {f: rd.latest_raster_path(f) for f in feats}
    ref = rasterio.open(paths[feats[0]])
    srcs = {feats[0]: ref}
    for f in feats[1:]:
        src = rasterio.open(paths[f])
        if (src.crs == ref.crs and src.transform == ref.transform
                and src.shape == ref.shape):
            srcs[f] = src
        else:
            srcs[f] = WarpedVRT(src, crs=ref.crs, transform=ref.transform,
                                width=ref.width, height=ref.height,
                                resampling=Resampling.nearest)
    for f in feats:
        print(f"   {f}: {os.path.basename(paths[f])}"
              + ("" if srcs[f] is ref or not isinstance(srcs[f], WarpedVRT)
                 else " (aligned via VRT)"))
    return srcs, ref


def bounds_to_window(ref, bounds, pad=100):
    min_lon, min_lat, max_lon, max_lat = bounds
    t = Transformer.from_crs("EPSG:4326", ref.crs, always_xy=True)
    xs, ys = t.transform([min_lon, min_lon, max_lon, max_lon],
                         [min_lat, max_lat, min_lat, max_lat])
    r0, c0 = ref.index(min(xs), max(ys))
    r1, c1 = ref.index(max(xs), min(ys))
    r_start = max(0, min(r0, r1) - pad)
    c_start = max(0, min(c0, c1) - pad)
    r_end = min(ref.height, max(r0, r1) + pad)
    c_end = min(ref.width, max(c0, c1) + pad)
    if r_end - r_start < IMG_SIZE or c_end - c_start < IMG_SIZE:
        raise SystemExit("Requested bounds cover less than one "
                         f"{IMG_SIZE}px window of the raster - enlarge "
                         "the bounding box.")
    return r_start, r_end, c_start, c_end


def _safe_windowed_read(src, window, fill_value=0):
    """Boundless-equivalent read that works for BOTH plain rasterio
    datasets and WarpedVRT sources. GDAL/rasterio does not support
    native boundless=True reads against a WarpedVRT (raises
    'WarpedVRT does not permit boundless reads') - this reads whatever
    portion of the window actually overlaps the source and manually
    pads the rest with fill_value, which is exactly what boundless=True
    does for a plain dataset, so behavior is identical for both."""
    col0, row0, w, h = (window.col_off, window.row_off,
                        int(window.width), int(window.height))
    rc0, rr0 = max(0, col0), max(0, row0)
    rc1, rr1 = min(src.width, col0 + w), min(src.height, row0 + h)
    out = np.full((h, w), fill_value, dtype=np.float32)
    if rc1 > rc0 and rr1 > rr0:
        data = src.read(1, window=Window(rc0, rr0, rc1 - rc0, rr1 - rr0)
                        ).astype(np.float32)
        dc, dr = rc0 - col0, rr0 - row0
        out[dr:dr + data.shape[0], dc:dc + data.shape[1]] = data
    return out


def read_window_stack(srcs, cat_f, cont_f, window):
    """One raster window -> the (cat int64, cont float32) stacks the
    model consumes: sentinels zeroed, continuous channels divided by
    their FEATURE_SPEC scale.

    THE single inference-side definition of "raw pixels -> model
    input". It was written out three times (read_strip,
    _tb_capture_windows, inspect_point) and a divergence between them
    would not crash - it would silently feed differently-scaled inputs
    at different points in the same pipeline.

    Note this is deliberately NOT shared with dataset.py's training
    path, which routes sentinels through NaN first so it can run its
    100%-nodata geolocation probe (impossible once 0 is in the array,
    since 0 is also a legitimate value). The two converge on the same
    numbers - dataset.py nan_to_num's to 0 - by different routes, for
    a reason."""
    cat = np.stack([_safe_windowed_read(srcs[f], window)
                   for f in cat_f]).astype(np.int64)
    cont = np.stack([_safe_windowed_read(srcs[f], window)
                    for f in cont_f]).astype(np.float32)
    for s in NODATA_SENTINELS:
        cat[cat == s] = 0
        cont[cont == s] = 0.0
    for i, f in enumerate(cont_f):
        cont[i] /= float(FEATURE_SPEC[f].get("scale", 1.0))
    return cat, cont


def read_strip(srcs, cat_f, cont_f, r0, rows, c0, cols):
    return read_window_stack(srcs, cat_f, cont_f,
                             Window(c0, r0, cols, rows))


def predict_region(model, device, srcs, ref, cat_f, cont_f,
                   window_bounds, stride, batch_size, use_compile,
                   flip_tta=True, temperature=1.0, logit_shift=0.0,
                   capture_features=None, edge_features=None):
    """capture_features: iterable of feature names (from cat_f and/or
    cont_f) to also capture per scored cell - the center-pixel value at
    each cell, read from the SAME tensors already loaded for scoring (no
    extra raster I/O). Returns feature_maps: {name: 2D array, same shape
    as heatmap} - int32 (-1 = not scored) for a categorical feature,
    float32 (NaN = not scored) for a continuous one (already the
    model-input SCALED value - see read_strip). Empty dict if
    capture_features is None/empty. Powers --tensorboard's per-feature
    score-correlation breakdown over the predicted region: which
    categorical classes and which continuous-feature ranges the model's
    score actually tracks in this specific deployment area, not just
    what the training data looked like.

    edge_features: iterable of feature names to ALSO capture a per-cell
    EDGE/CONTRAST magnitude for, computed over that same cell's WHOLE
    64x64 window (not just its center pixel) from the exact tensors
    already stacked for scoring - a hard-edge hypothesis (e.g. "the
    model is keying on the canopy/field contrast a road cuts, not on
    what's on either side of it") shows up here, not in
    capture_features's plain center-pixel values. Continuous feature:
    mean absolute finite-difference gradient. Categorical feature: rate
    of class change between adjacent pixels. Returns edge_maps in the
    same {name: 2D float32 array} shape as feature_maps, always
    continuous regardless of the source feature's own kind, since an
    edge magnitude is a continuous quantity either way."""
    r_start, r_end, c_start, c_end = window_bounds
    height, width = r_end - r_start, c_end - c_start
    out_h = (height - IMG_SIZE) // stride + 1
    out_w = (width - IMG_SIZE) // stride + 1
    heatmap = np.full((out_h, out_w), np.nan, dtype=np.float32)
    capture_features = list(capture_features or [])
    cat_capture = {f: cat_f.index(f) for f in capture_features if f in cat_f}
    cont_capture = {f: cont_f.index(f) for f in capture_features
                    if f in cont_f}
    feature_maps = {f: np.full((out_h, out_w), -1, dtype=np.int32)
                    for f in cat_capture}
    feature_maps.update({f: np.full((out_h, out_w), np.nan, dtype=np.float32)
                         for f in cont_capture})
    edge_features = list(edge_features or [])
    edge_cat_capture = {f: cat_f.index(f) for f in edge_features
                        if f in cat_f}
    edge_cont_capture = {f: cont_f.index(f) for f in edge_features
                         if f in cont_f}
    edge_maps = {f: np.full((out_h, out_w), np.nan, dtype=np.float32)
                for f in list(edge_cat_capture) + list(edge_cont_capture)}

    # Reference-layer nodata mask for honest masking of no-coverage cells.
    ref_nodata = ref.nodata if ref.nodata is not None else -9999

    if use_compile:
        print("   Compiling model graph (torch.compile)...")
        model = torch.compile(model)

    strip_rows = max(stride, (STRIP_TARGET_ROWS // stride) * stride)
    n_strips = math.ceil(max(height - IMG_SIZE + 1, 1) / strip_rows)
    autocast = (torch.amp.autocast('cuda') if device.type == 'cuda'
                else torch.autocast('cpu', enabled=False))

    with torch.no_grad():
        for s_i in range(n_strips):
            y0 = s_i * strip_rows                     # strip-local origin
            rows_here = min(strip_rows + IMG_SIZE - 1,
                            height - y0)
            if rows_here < IMG_SIZE:
                break
            cat_np, cont_np = read_strip(srcs, cat_f, cont_f,
                                         r_start + y0, rows_here,
                                         c_start, width)
            ref_band = cat_np[0] if cat_f else cont_np[0]

            ys = list(range(0, rows_here - IMG_SIZE + 1, stride))
            xs = list(range(0, width - IMG_SIZE + 1, stride))
            coords = [(y, x) for y in ys for x in xs]

            for b0 in tqdm(range(0, len(coords), batch_size),
                           desc=f"   strip {s_i + 1}/{n_strips}",
                           leave=False):
                chunk = coords[b0:b0 + batch_size]
                keep, cat_b, cont_b = [], [], []
                for (y, x) in chunk:
                    cy, cx = y + IMG_SIZE // 2, x + IMG_SIZE // 2
                    if ref_band[cy, cx] == 0 and ref_nodata != 0:
                        # center pixel had no data (filled to 0) - mask
                        continue
                    keep.append((y, x))
                    cat_b.append(cat_np[:, y:y + IMG_SIZE, x:x + IMG_SIZE])
                    cont_b.append(cont_np[:, y:y + IMG_SIZE, x:x + IMG_SIZE])
                if not keep:
                    continue
                t_cat = torch.from_numpy(np.stack(cat_b)).to(
                    device, non_blocking=True)
                t_cont = torch.from_numpy(np.stack(cont_b)).to(
                    device, non_blocking=True)

                # Edge/contrast magnitude per sample, on the canonical
                # (untransformed) orientation only - one pass, not per
                # TTA view, since this characterizes the WINDOW's own
                # content, not a scoring quantity. Categorical: rate of
                # class change between adjacent pixels (unrelated
                # values still count as "different", which is exactly
                # what a categorical edge is). Continuous: mean absolute
                # finite-difference gradient.
                edge_cat_vals, edge_cont_vals = {}, {}
                for f, idx in edge_cat_capture.items():
                    ch = t_cat[:, idx]
                    neq_x = (ch[:, :, 1:] != ch[:, :, :-1]).float().mean(
                        dim=(1, 2))
                    neq_y = (ch[:, 1:, :] != ch[:, :-1, :]).float().mean(
                        dim=(1, 2))
                    edge_cat_vals[f] = (0.5 * (neq_x + neq_y)).cpu().numpy()
                for f, idx in edge_cont_capture.items():
                    ch = t_cont[:, idx]
                    dx = (ch[:, :, 1:] - ch[:, :, :-1]).abs().mean(dim=(1, 2))
                    dy = (ch[:, 1:, :] - ch[:, :-1, :]).abs().mean(dim=(1, 2))
                    edge_cont_vals[f] = (0.5 * (dx + dy)).cpu().numpy()

                # D4 TTA through the shared scorer (models.d4_tta_logits
                # - the single definition, also used by
                # _tb_capture_windows and inspect_point.py).
                pooled_logit = d4_tta_logits(model, t_cat, t_cont,
                                             flip_tta=flip_tta,
                                             autocast=autocast)
                # Temperature first (calibrates the val-design scale),
                # then the prior shift (converts calibrated logits from
                # the 50/50 training prior to the deployment prior).
                probs = torch.sigmoid(
                    pooled_logit / temperature
                    + logit_shift).float().cpu().numpy()

                for i, (p, (y, x)) in enumerate(zip(probs, keep)):
                    gy = (y0 + y) // stride
                    gx = x // stride
                    if gy < out_h and gx < out_w:
                        heatmap[gy, gx] = p
                        if cat_capture or cont_capture:
                            cy, cx = y + IMG_SIZE // 2, x + IMG_SIZE // 2
                            for f, idx in cat_capture.items():
                                feature_maps[f][gy, gx] = int(
                                    cat_np[idx, cy, cx])
                            for f, idx in cont_capture.items():
                                feature_maps[f][gy, gx] = float(
                                    cont_np[idx, cy, cx])
                        for f, vals in edge_cat_vals.items():
                            edge_maps[f][gy, gx] = float(vals[i])
                        for f, vals in edge_cont_vals.items():
                            edge_maps[f][gy, gx] = float(vals[i])

    n_valid = int(np.isfinite(heatmap).sum())
    print(f"   Scored {n_valid:,}/{heatmap.size:,} cells "
          f"({100 * n_valid / heatmap.size:.1f}% - rest masked as "
          f"nodata).")
    new_trans = rasterio.Affine(
        ref.transform.a * stride, ref.transform.b,
        ref.transform.c + (c_start + IMG_SIZE // 2) * ref.transform.a,
        ref.transform.d, ref.transform.e * stride,
        ref.transform.f + (r_start + IMG_SIZE // 2) * ref.transform.e)
    return heatmap, new_trans, feature_maps, edge_maps


# ==========================================
# TensorBoard instrumentation
# ==========================================
def _tb_suitability_image(heatmap, cmap_name="jet", max_dim=1024):
    """The heatmap itself, colorized (nodata fully transparent) and
    downsampled to a sane TensorBoard image size - the region-scan
    analog of train.py's Patches/logit_map, at the scale that's
    actually the point of running predict.py at all."""
    valid = np.isfinite(heatmap)
    shown = np.nan_to_num(heatmap, nan=0.0)
    rgba = (plt.get_cmap(cmap_name)(np.clip(shown, 0, 1)) * 255
           ).astype(np.uint8)
    rgba[..., 3] = np.where(valid, 255, 0).astype(np.uint8)
    img = Image.fromarray(rgba, "RGBA")
    if max(img.size) > max_dim:
        ratio = max_dim / max(img.size)
        img = img.resize((max(1, int(img.width * ratio)),
                          max(1, int(img.height * ratio))),
                         Image.NEAREST)
    arr = np.asarray(img).astype(np.float32) / 255.0
    return torch.from_numpy(arr).permute(2, 0, 1)          # (4, H, W)


def _tb_log_categorical_breakdown(tb_writer, heatmap, code_map, feature,
                                  min_count=50, max_classes=15, names=None):
    """Per-class breakdown over the PREDICTED region for ONE categorical
    feature - the live, real-deployment counterpart to model_handler's
    per-class val breakdown and diagnose_wetland.py's area-composition
    analysis. Generalizes what used to be nlcd-only to every categorical
    feature the model actually uses (evt/evh/evc/sclass/fdist/nlcd),
    tagged under Class/<feature>/... so a "sticks to roads" pattern can
    be tested against EVERY feature, not just land cover - a strong
    fdist (disturbance) or sclass (succession stage) correlation would
    mean something very different than an nlcd one:
    - mean_score: does any class score anomalously high across this
      actual mapped area? No ground truth at inference, so no AUC -
      mean score is what's available.
    - score_hist: the SHAPE of each class's score distribution, not
      just its mean - a thin high tail over an otherwise ordinary bulk
      looks very different from uniformly elevated, and the mean alone
      can't tell those apart.
    - area_share: each class's share of the scored map area - a high
      mean score over a handful of pixels is a very different finding
      from the same mean over a large contiguous class.
    - lit_area_share: diagnose_wetland.py Part D's "landscape area
      share x mean score", normalized to sum to 1 across classes - each
      class's actual contribution to the map's total predicted
      suitability, the map-level answer to "does this class scoring
      high actually move the map, or is it a sliver."
    max_classes caps the tile count to the most areally significant
    classes (by area_share) - a high-cardinality feature like evt/sclass
    can have far more distinct codes on disk than are worth a tile each;
    the ones that don't even cover enough ground to matter for
    lit_area_share aren't worth the clutter."""
    valid = np.isfinite(heatmap) & (code_map >= 0)
    if not valid.any():
        return
    codes, scores = code_map[valid], heatmap[valid]
    total = float(valid.sum())
    rows = []
    for code in sorted(set(codes.tolist())):
        m = codes == code
        if m.sum() < min_count:
            continue
        label = (names.get(int(code), f"class_{code}") if names
                 else str(int(code))).replace(' ', '_').replace('/', '-')
        rows.append((label, float(m.sum()) / total,
                    float(scores[m].mean()), scores[m]))
    rows.sort(key=lambda r: -r[1])
    rows = rows[:max_classes]
    norm = sum(a * sc for _, a, sc, _ in rows) or 1.0
    for label, area_share, mean_score, class_scores in rows:
        tb_writer.add_scalar(f"Class/{feature}/mean_score/{label}",
                             mean_score, 0)
        tb_writer.add_histogram(f"Class/{feature}/score_hist/{label}",
                                class_scores, 0)
        tb_writer.add_scalar(f"Class/{feature}/area_share/{label}",
                             area_share, 0)
        tb_writer.add_scalar(f"Class/{feature}/lit_area_share/{label}",
                             (area_share * mean_score) / norm, 0)


def _tb_log_continuous_correlation(tb_writer, heatmap, value_map, feature,
                                   n_bins=20, tag_prefix="Correlation"):
    """Does the score actually track a CONTINUOUS quantity - a raw
    feature value (canopy height/cover, tree-canopy-cover%) or, via
    edge_maps/tag_prefix='Edge', a per-cell EDGE/CONTRAST magnitude
    instead - not just land-cover class? Logs a Pearson r scalar plus a
    binned mean-score-vs-value plot (quantile bins, so a skewed
    quantity like canopy cover or an edge-density fraction doesn't dump
    most cells into one or two equal-width bins) - the map-level analog
    of asking "if I sort every scored cell by this quantity, does the
    mean score trend with it." A strong trend under the default
    'Correlation' prefix means the pattern is a height/structure/value
    effect; a strong one under 'Edge' means it's a hard-boundary/
    contrast effect instead - e.g. a road's canopy/field edge, not
    what's actually on either side of it."""
    valid = np.isfinite(heatmap) & np.isfinite(value_map)
    if valid.sum() < n_bins * 5:
        return
    scores, values = heatmap[valid], value_map[valid]
    if np.ptp(values) == 0:
        return
    r = float(np.corrcoef(values, scores)[0, 1])
    tb_writer.add_scalar(f"{tag_prefix}/pearson_r/{feature}", r, 0)

    edges = np.unique(np.quantile(values, np.linspace(0, 1, n_bins + 1)))
    if len(edges) < 3:
        return
    bin_idx = np.clip(np.digitize(values, edges[1:-1]), 0, len(edges) - 2)
    bin_centers, bin_means, bin_counts = [], [], []
    for b in range(len(edges) - 1):
        m = bin_idx == b
        if not m.any():
            continue
        bin_centers.append(float(values[m].mean()))
        bin_means.append(float(scores[m].mean()))
        bin_counts.append(int(m.sum()))

    fig, ax1 = plt.subplots(figsize=(6, 4), dpi=110)
    ax1.plot(bin_centers, bin_means, 'o-', color='tab:blue')
    ax1.set_xlabel(feature)
    ax1.set_ylabel('mean predicted score', color='tab:blue')
    ax1.tick_params(axis='y', labelcolor='tab:blue')
    ax2 = ax1.twinx()
    ax2.bar(bin_centers, bin_counts,
           width=(max(bin_centers) - min(bin_centers) or 1) / n_bins * 0.8,
           alpha=0.15, color='gray')
    ax2.set_ylabel('cell count', color='gray')
    ax1.set_title(f"score vs {feature} (r={r:+.3f}, n={valid.sum():,})")
    fig.tight_layout()
    fig.canvas.draw()
    w, h = fig.canvas.get_width_height()
    arr = np.frombuffer(fig.canvas.buffer_rgba(), dtype=np.uint8).reshape(
        h, w, 4)
    plt.close(fig)
    tb_writer.add_image(f"{tag_prefix}/plot/{feature}",
                        torch.from_numpy(arr.copy()).permute(2, 0, 1), 0)


def _tb_capture_windows(model, device, srcs, cat_f, cont_f, heatmap,
                        window_bounds, stride, top_n, temperature,
                        logit_shift, flip_tta):
    """Re-reads the actual top-N and bottom-N scoring windows' input
    patches - cheap (top_n*2 windows total, not a rescan of the region)
    - so --tensorboard can show what the model literally saw at its
    most and least confident locations. srcs must still be open (call
    this before the caller's finally closes them). None if nothing
    scored."""
    r_start, r_end, c_start, c_end = window_bounds
    finite = np.isfinite(heatmap)
    if not finite.any():
        return None
    flat_idx = np.flatnonzero(finite)
    vals = heatmap.flat[flat_idx]
    order = np.argsort(vals)
    n = min(top_n, len(order))

    def gather(idxs):
        cat_list, cont_list = [], []
        for flat in idxs:
            gy, gx = np.unravel_index(flat, heatmap.shape)
            window = Window(c_start + int(gx) * stride,
                            r_start + int(gy) * stride, IMG_SIZE, IMG_SIZE)
            cat, cont = read_window_stack(srcs, cat_f, cont_f, window)
            cat_list.append(cat)
            cont_list.append(cont)
        t_cat = torch.from_numpy(np.stack(cat_list)).to(device)
        t_cont = torch.from_numpy(np.stack(cont_list)).to(device)
        with torch.no_grad():
            score = torch.sigmoid(
                d4_tta_logits(model, t_cat, t_cont, flip_tta=flip_tta)
                / temperature + logit_shift)
        return t_cat, t_cont, score.cpu().numpy()

    return {"top": gather(flat_idx[order[-n:][::-1]]),
           "bottom": gather(flat_idx[order[:n]])}


def _tb_log_windows(tb_writer, tag_prefix, model, cat_f, cont_f, window):
    """Logs one gather() result from _tb_capture_windows: each
    continuous feature's patch, the 'nlcd' category map (if present),
    the model's own pre-pool spatial logit map, and - if early_attn is
    active - its center-query attention (head-averaged, an off-center
    query grid, and per-head at the center), one tile per window, plus
    the windows' actual scores as text. Mirrors model_handler's
    _tb_log_epoch_extras patch/attention visualization, rebuilt here
    since predict.py scores bare windows directly rather than through
    a GrouseModelHandler/DataLoader."""
    import torchvision
    from model_handler import GrouseModelHandler
    t_cat, t_cont, scores = window
    n = t_cat.shape[0]

    def norm01(m):
        lo = m.amin(dim=(2, 3), keepdim=True)
        hi = m.amax(dim=(2, 3), keepdim=True)
        return ((m - lo) / (hi - lo).clamp_min(1e-6)).float().cpu()

    def clip01(m):
        """For raw INPUT feature channels only, not model outputs: see
        model_handler.py's _tb_log_epoch_extras.clip01 - the same bug,
        mirrored here since this function reimplements that
        visualization for bare windows. t_cont arrives already divided
        by FEATURE_SPEC scale (read_window_stack), so it's fixed and
        comparable across windows; norm01's per-sample min/max stretch
        was throwing that away."""
        return m.clamp(0, 1).float().cpu()

    with torch.no_grad():
        for ci, fname in enumerate(cont_f):
            grid = torchvision.utils.make_grid(
                clip01(t_cont[:, ci:ci + 1]), nrow=n)
            tb_writer.add_image(f"{tag_prefix}/{fname}", grid, 0)
        if "nlcd" in cat_f:
            ni = cat_f.index("nlcd")
            grid = torchvision.utils.make_grid(
                GrouseModelHandler._class_map_rgb(t_cat[:, ni:ni + 1]),
                nrow=n)
            tb_writer.add_image(f"{tag_prefix}/nlcd", grid, 0)
        spatial = model.trunk(model.embed(t_cat, t_cont))
        tb_writer.add_image(
            f"{tag_prefix}/logit_map",
            torchvision.utils.make_grid(norm01(spatial[:, :1]), nrow=n), 0)
        result = model.attention_diagnostics(t_cat, t_cont)
        if result is not None:
            w_attn, (h, wd, kh, kw) = result
            num_heads = w_attn.shape[1]
            center = (h // 2) * wd + (wd // 2)
            center_map = w_attn[:, :, center, :].mean(dim=1).reshape(
                n, 1, kh, kw)
            tb_writer.add_image(
                f"{tag_prefix}/attn_center",
                torchvision.utils.make_grid(norm01(center_map), nrow=n), 0)
            # Off-center query positions (center + quadrant midpoints),
            # head-averaged - mirrors train.py's Patches/attn_query_grid,
            # so a window's attention behavior away from the patch
            # center isn't invisible here the way a center-only tile
            # would leave it.
            positions = [(0.5, 0.5), (0.25, 0.25), (0.25, 0.75),
                        (0.75, 0.25), (0.75, 0.75)]
            idxs = [int(round(py * (h - 1))) * wd + int(round(px * (wd - 1)))
                   for py, px in positions]
            pos_maps = torch.stack(
                [w_attn[:, :, i, :].mean(dim=1) for i in idxs],
                dim=1).reshape(n * len(idxs), 1, kh, kw)
            tb_writer.add_image(
                f"{tag_prefix}/attn_query_grid",
                torchvision.utils.make_grid(norm01(pos_maps),
                                            nrow=len(idxs)), 0)
            # Same center query, one tile per head instead of averaged -
            # mirrors train.py's Patches/attn_center_per_head; a head
            # that specializes (local vs. global, directional) is
            # invisible in the head-averaged attn_center tile above.
            if num_heads > 1:
                head_maps = w_attn[:, :, center, :].reshape(
                    n, num_heads, kh, kw
                ).reshape(n * num_heads, 1, kh, kw)
                tb_writer.add_image(
                    f"{tag_prefix}/attn_center_per_head",
                    torchvision.utils.make_grid(norm01(head_maps),
                                                nrow=num_heads), 0)
    tb_writer.add_text(f"{tag_prefix}/scores",
                       ", ".join(f"{s:.3f}" for s in scores), 0)


# ==========================================
# KMZ
# ==========================================
def generate_kmz(input_tif, output_kmz, style="absolute",
                 cmap_name="jet", alpha_below=0.15, overlay_alpha=200):
    print(f"\nGenerating KMZ ({style} coloring)...")
    with rasterio.open(input_tif) as src:
        # Output resolution in degrees derived from the tif's own
        # resolution at its center latitude (the original hardcoded a
        # constant tied to stride=4).
        b = src.bounds
        t = Transformer.from_crs(src.crs, "EPSG:4326", always_xy=True)
        lons, lats = t.transform([b.left, b.left, b.right, b.right],
                                 [b.bottom, b.top, b.bottom, b.top])
        west, east = min(lons), max(lons)
        south, north = min(lats), max(lats)
        mid_lat = 0.5 * (south + north)
        res_m = abs(src.transform.a)
        deg_lat = res_m / 111_320.0
        deg_lon = res_m / (111_320.0 * max(math.cos(math.radians(mid_lat)),
                                           1e-6))
        width = max(1, int((east - west) / deg_lon))
        height = max(1, int((north - south) / deg_lat))
        transform = rasterio.transform.from_bounds(west, south, east,
                                                   north, width, height)
        dest = np.full((height, width), np.nan, dtype=np.float32)
        reproject(source=rasterio.band(src, 1), destination=dest,
                  src_transform=src.transform, src_crs=src.crs,
                  dst_transform=transform, dst_crs="EPSG:4326",
                  resampling=Resampling.nearest,
                  src_nodata=np.nan, dst_nodata=np.nan)

    valid = np.isfinite(dest)
    if style == "stretched" and valid.any():
        vals = dest[valid]
        p_low, p_high = np.percentile(vals, 2), np.percentile(vals, 98)
        if p_high > p_low:
            shown = np.clip((dest - p_low) / (p_high - p_low), 0, 1) ** 3.0
        else:
            shown = np.clip(dest, 0, 1)
    elif style == "quantile" and valid.any():
        # Color = the cell's rank among THIS map's valid cells (0..1).
        # Absolute probabilities from a 50/50 presence/pseudo-absence
        # model saturate over a uniformly-forested box; rank is the
        # quantity the deployed use ("where do I scout first in this
        # area") actually needs, and it guarantees exactly (1 -
        # alpha_below) of the valid area lights up.
        vals = dest[valid]
        sv = np.sort(vals)
        shown = np.zeros_like(dest)
        shown[valid] = np.searchsorted(sv, vals, side='right') / len(sv)
    else:
        shown = np.clip(dest, 0, 1)          # absolute: color==probability

    rgba = (plt.get_cmap(cmap_name)(np.nan_to_num(shown)) * 255
            ).astype(np.uint8)
    alpha = np.full(dest.shape, overlay_alpha, dtype=np.uint8)
    alpha[~valid] = 0                        # nodata fully transparent
    # absolute/stretched hide below an absolute probability; quantile
    # hides below a RANK ("0.8 = only the top 20% of this box visible").
    thr_vals = (shown if style == "quantile"
                else np.nan_to_num(dest))
    alpha[thr_vals < alpha_below] = 0
    rgba[:, :, 3] = alpha

    with tempfile.TemporaryDirectory() as td:
        png = os.path.join(td, "overlay.png")
        kml = os.path.join(td, "doc.kml")
        Image.fromarray(rgba, "RGBA").save(png)
        with open(kml, "w") as f:
            f.write(
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<kml xmlns="http://www.opengis.net/kml/2.2"><Folder>'
                '<GroundOverlay><name>Grouse Habitat Suitability</name>'
                '<Icon><href>overlay.png</href></Icon><LatLonBox>'
                f'<north>{north}</north><south>{south}</south>'
                f'<east>{east}</east><west>{west}</west>'
                '</LatLonBox></GroundOverlay></Folder></kml>')
        with zipfile.ZipFile(output_kmz, "w") as z:
            z.write(kml, arcname="doc.kml")
            z.write(png, arcname="overlay.png")
    print(f"   Saved {output_kmz}")


# ==========================================
# Entry
# ==========================================
def main():
    parser = argparse.ArgumentParser(
        description="Predict habitat suitability over a region and "
                    "export GeoTIFF + Google Earth KMZ.")
    parser.add_argument("--region", default="ME", choices=list(BOXES))
    parser.add_argument("--bounds", nargs=4, type=float, default=None,
                        metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"),
                        help="Custom bounding box; default: the whole "
                             "region.")
    parser.add_argument("--model", default="data/models/grouse_single_best.pth")
    parser.add_argument("--stride", type=int, default=4,
                        help="Cells between prediction centers, in "
                             "pixels (30m each). 4 -> 120m output "
                             "resolution.")
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--style",
                        choices=["absolute", "quantile", "stretched"],
                        default="absolute",
                        help="'absolute': color = calibrated probability. "
                             "'quantile': color = the cell's rank within "
                             "this map - the right product when the use "
                             "is ranking candidate habitat inside a box, "
                             "and immune to the 50/50-design probability "
                             "inflation. 'stretched': 2-98 percentile "
                             "stretch + gamma (local contrast only).")
    parser.add_argument("--cmap", default="jet")
    parser.add_argument("--alpha-below", type=float, default=0.15,
                        help="Cells below this render fully transparent "
                             "in the KMZ. For --style absolute/stretched "
                             "it is an absolute probability; for --style "
                             "quantile it is a rank (0.8 = show only the "
                             "top 20%% of the mapped area).")
    parser.add_argument("--prior", type=float, default=None,
                        help="Expected fraction of the mapped area that "
                             "is genuinely suitable (0-1). The model's "
                             "probabilities are calibrated to its 50/50 "
                             "presence/pseudo-absence design, so over a "
                             "real landscape they read inflated - and "
                             "temperature scaling cannot fix that (it "
                             "never moves a score across 0.5). This "
                             "applies the standard prior correction "
                             "(logits shifted by logit(prior)-logit(0.5)) "
                             "AFTER temperature: e.g. --prior 0.1 makes "
                             "a displayed 0.8 require a raw calibrated "
                             "score of ~0.97. Default: no correction.")
    parser.add_argument("--compile", action="store_true",
                        help="torch.compile the model (worthwhile on "
                             "GPU for large areas).")
    parser.add_argument("--tif-only", action="store_true")
    parser.add_argument("--flip-tta",
                        action=argparse.BooleanOptionalAction, default=True,
                        help="Mirror-average each view (matches the "
                             "training-time evaluation default).")
    parser.add_argument("--calibration",
                        default="data/calibration/calibration.json",
                        help="calibration.json from calibrate.py. Applied "
                             "automatically when the file exists; "
                             "--no-calibration disables.")
    parser.add_argument("--no-calibration", action="store_true",
                        help="Ignore calibration.json and score with raw "
                             "logits (T=1). Use when the checkpoint was "
                             "trained under a different --loss (or "
                             "retrained at all) since the calibration "
                             "was fitted - a temperature is specific to "
                             "both the weights and the objective they "
                             "were trained with.")
    parser.add_argument("--temperature", type=float, default=None,
                        help="Manual temperature override (logits are "
                             "divided by this before sigmoid). Overrides "
                             "--calibration.")
    parser.add_argument("--pool", default="attn",
                        choices=["mean", "center", "gauss", "attn"],
                        help="Only used for OLD bare checkpoints with no "
                             "embedded config.")
    parser.add_argument("--center-skip",
                        action=argparse.BooleanOptionalAction, default=True,
                        help="Only used for old bare checkpoints.")
    parser.add_argument("--tensorboard", action="store_true",
                        help="Log coverage/score-distribution scalars, "
                             "the rendered suitability map, a per-NLCD-"
                             "class mean-score breakdown, and the "
                             "model's own top/bottom-scoring window "
                             "patches (+ spatial logit map, + attention "
                             "if --early-attn was active) to "
                             "TensorBoard, under --tensorboard-dir/"
                             "<timestamp>_predict_<region>. Uses the "
                             "SAME base directory train.py does by "
                             "default, so a prediction run and the "
                             "training runs that produced its "
                             "checkpoint show up side by side. Requires "
                             "the tensorboard package (pip install "
                             "tensorboard).")
    parser.add_argument("--tensorboard-dir", default="runs",
                        help="Base directory for --tensorboard logs.")
    parser.add_argument("--tb-top-n", type=int, default=8,
                        help="Number of highest- and lowest-scoring "
                             "windows to visualize under --tensorboard.")
    args = parser.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    tb_writer = None
    if args.tensorboard:
        try:
            from torch.utils.tensorboard import SummaryWriter
        except ImportError:
            raise SystemExit(
                "--tensorboard requires the tensorboard package: "
                "pip install tensorboard")
        run_name = (f"{dt.datetime.now():%Y%m%d_%H%M%S}_predict_"
                   f"{args.region}{'_custom' if args.bounds else ''}")
        tb_logdir = os.path.join(args.tensorboard_dir, run_name)
        tb_writer = SummaryWriter(tb_logdir)
        tb_writer.add_text("run/command", " ".join(sys.argv), 0)
        tb_writer.add_text("run/args",
                           f"```\n{json.dumps(vars(args), indent=2, default=str)}\n```",
                           0)
        print(f"   TensorBoard logging to {tb_logdir} (view with: "
              f"tensorboard --logdir {args.tensorboard_dir})")

    data = GrouseData()
    rd = data[args.region]
    features = [f for f in rd.available_features() if f in FEATURE_SPEC]
    if not features:
        raise SystemExit(f"No usable features on disk for {args.region}.")
    print(f"Features (discovered): {features}")

    model, cat_f, cont_f, features, ckpt_cfg = load_model(
        args.model, features, device, cli_pool=args.pool,
        cli_center_skip=args.center_skip)

    def _say(msg, tag="events/calibration"):
        print(msg)
        if tb_writer is not None:
            tb_writer.add_text(tag, msg.strip(), 0)

    temperature = 1.0
    if args.temperature is not None:
        temperature = float(args.temperature)
        _say(f"Calibration: manual temperature T={temperature:.3f}")
    elif not args.no_calibration and os.path.exists(args.calibration):
        with open(args.calibration) as f:
            cal = json.load(f)
        temperature = float(cal.get("temperature", 1.0))
        _say(f"Calibration: T={temperature:.3f} from {args.calibration} "
             f"(fitted {cal.get('fitted_at', '?')}, "
             f"ECE {cal.get('ece_before', float('nan')):.3f} -> "
             f"{cal.get('ece_after', float('nan')):.3f})")
        if cal.get("model_path") and os.path.abspath(args.model) !=                 cal["model_path"]:
            _say(f"   [warn] calibration was fitted on "
                 f"{cal['model_path']}, but you're predicting with "
                 f"{os.path.abspath(args.model)} - temperatures are "
                 f"model-specific; re-run calibrate.py for this "
                 f"checkpoint.")
        # Same PATH is not same MODEL: retraining overwrites the .pth
        # in place (possibly with a different --loss entirely), and the
        # model_path check above cannot see that. A fit older than the
        # checkpoint file is a fit on weights that no longer exist.
        try:
            fitted = dt.datetime.fromisoformat(cal["fitted_at"])
            written = dt.datetime.fromtimestamp(
                os.path.getmtime(args.model))
            if fitted < written:
                _say(f"   [warn] calibration was fitted "
                     f"{fitted:%Y-%m-%d %H:%M} but the checkpoint file "
                     f"was written {written:%Y-%m-%d %H:%M} - the fit "
                     f"predates the current weights (retrained since, "
                     f"perhaps with a different --loss?). Re-run "
                     f"calibrate.py, or pass --no-calibration to score "
                     f"with raw logits.")
        except (KeyError, ValueError, OverflowError, OSError):
            pass
        bias = loss_logit_bias(ckpt_cfg)
        if bias is not None:
            reason, off = bias
            _say(f"   [warn] this checkpoint was trained with {reason}, "
                 f"which builds a constant logit offset (~{off:+.2f}) "
                 f"into the model. A temperature is a pure SCALE and "
                 f"cannot remove an offset, so calibrated probabilities "
                 f"remain shifted. Remedies: --prior (an explicit "
                 f"offset), --style quantile (rank-based, offset-"
                 f"immune), or --no-calibration to drop the "
                 f"temperature.", tag="events/bias_warning")
    else:
        _say("Calibration: none (raw probabilities). Run calibrate.py "
             "to fit one.")

    logit_shift = 0.0
    if args.prior is not None:
        if not (0.0 < args.prior < 1.0):
            raise SystemExit(f"--prior must be in (0, 1), got {args.prior}")
        logit_shift = math.log(args.prior / (1.0 - args.prior))
        _say(f"Prior correction: deployment prevalence {args.prior:g} "
             f"(training design 0.5) -> calibrated logits shifted by "
             f"{logit_shift:+.3f}. A displayed 0.5 now requires a raw "
             f"calibrated score of "
              f"{1.0 / (1.0 + args.prior / (1.0 - args.prior)):.3f}.")

    srcs, ref = open_aligned_sources(rd, cat_f, cont_f)
    try:
        bounds = args.bounds or list(BOXES[args.region])
        window_bounds = bounds_to_window(ref, bounds)
        # Every feature the model actually uses, captured per scored
        # cell for the --tensorboard per-feature correlation breakdown -
        # cheap (reused from the tensors already loaded for scoring), so
        # only paid when there's a writer to consume it. edge_features
        # (same list) additionally captures each feature's per-window
        # edge/contrast magnitude - tests the "hard boundary" hypothesis
        # (e.g. a road's canopy/field edge) separately from the plain
        # value correlation above.
        capture_features = (cat_f + cont_f) if tb_writer is not None else None
        edge_features = capture_features
        heatmap, transform, feature_maps, edge_maps = predict_region(
            model, device, srcs, ref, cat_f, cont_f, window_bounds,
            args.stride, args.batch_size, args.compile,
            flip_tta=args.flip_tta, temperature=temperature,
            logit_shift=logit_shift, capture_features=capture_features,
            edge_features=edge_features)
        # Captured here, before srcs close below: the top/bottom-scoring
        # windows need to be re-read from the SAME open sources.
        tb_windows = (_tb_capture_windows(
            model, device, srcs, cat_f, cont_f, heatmap, window_bounds,
            args.stride, args.tb_top_n, temperature, logit_shift,
            args.flip_tta) if tb_writer is not None else None)
    finally:
        for s in srcs.values():
            s.close()

    vals = heatmap[np.isfinite(heatmap)]
    if len(vals):
        pct5, pct8 = 100 * (vals >= 0.5).mean(), 100 * (vals >= 0.8).mean()
        print(f"Score distribution: min {vals.min():.3f} | median "
              f"{np.median(vals):.3f} | p90 {np.percentile(vals, 90):.3f} "
              f"| max {vals.max():.3f} | {pct5:.1f}% >= 0.5 | "
              f"{pct8:.1f}% >= 0.8")
        if args.prior is None and args.style != "quantile" and pct5 > 50.0:
            print(
                "   [note] Over half the scored area exceeds p=0.5. The "
                "model's probabilities are calibrated to its 50/50 "
                "presence/pseudo-absence design (calibrate.py 'HONEST "
                "LIMITS'), so over a real landscape they read inflated - "
                "and temperature scaling cannot shift them (it never "
                "moves a score across 0.5). Remedies: --prior <expected "
                "suitable fraction, e.g. 0.1> to re-anchor the "
                "probabilities, or --style quantile to color/threshold "
                "by within-map rank (--alpha-below 0.8 then shows only "
                "the top 20% of the box).")

    if tb_writer is not None:
        coverage = 100.0 * len(vals) / heatmap.size if heatmap.size else 0.0
        tb_writer.add_scalar("Predict/coverage_pct", coverage, 0)
        tb_writer.add_scalar("Predict/temperature", temperature, 0)
        tb_writer.add_scalar("Predict/prior_logit_shift", logit_shift, 0)
        if len(vals):
            tb_writer.add_scalar("Predict/score_min", float(vals.min()), 0)
            tb_writer.add_scalar("Predict/score_median",
                                 float(np.median(vals)), 0)
            tb_writer.add_scalar("Predict/score_p90",
                                 float(np.percentile(vals, 90)), 0)
            tb_writer.add_scalar("Predict/score_max", float(vals.max()), 0)
            tb_writer.add_scalar("Predict/pct_ge_0.5", float(pct5), 0)
            tb_writer.add_scalar("Predict/pct_ge_0.8", float(pct8), 0)
            tb_writer.add_histogram("Diagnostics/predicted_scores", vals, 0)
            tb_writer.add_image("Map/suitability",
                                _tb_suitability_image(heatmap, args.cmap), 0)
        for f in cat_f:
            if f in feature_maps:
                _tb_log_categorical_breakdown(
                    tb_writer, heatmap, feature_maps[f], f,
                    names=NLCD_NAMES if f == "nlcd" else None)
        for f in cont_f:
            if f in feature_maps:
                _tb_log_continuous_correlation(
                    tb_writer, heatmap, feature_maps[f], f)
        for f in cat_f + cont_f:
            if f in edge_maps:
                _tb_log_continuous_correlation(
                    tb_writer, heatmap, edge_maps[f], f, tag_prefix="Edge")
        if tb_windows is not None:
            for key, prefix in (("top", "Windows/top_score"),
                                ("bottom", "Windows/bottom_score")):
                w = tb_windows.get(key)
                if w is not None:
                    _tb_log_windows(tb_writer, prefix, model, cat_f,
                                    cont_f, w)
        tb_writer.close()

    tag = args.region + ("_custom" if args.bounds else "")
    tif_path = os.path.join(OUT_DIR, f"{tag}_suitability.tif")
    with rasterio.open(tif_path, "w", driver="GTiff",
                       height=heatmap.shape[0], width=heatmap.shape[1],
                       count=1, dtype=rasterio.float32, crs=ref.crs,
                       transform=transform, nodata=np.nan) as dst:
        dst.write(heatmap, 1)
    print(f"Saved GeoTIFF: {tif_path}")

    if not args.tif_only:
        kmz_path = os.path.join(OUT_DIR, f"{tag}_suitability.kmz")
        generate_kmz(tif_path, kmz_path, style=args.style,
                     cmap_name=args.cmap, alpha_below=args.alpha_below)


if __name__ == "__main__":
    main()
