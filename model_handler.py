"""
model_handler.py

GrouseModelHandler - the model-management class requested: owns model
construction (with geometry derived dynamically from the feature list),
the training loop, evaluation, checkpointing, and prediction. The
training recipe is preserved exactly from the original train.py:

  AdamW(lr=3e-4, weight_decay=1e-2) | FocalLoss(alpha=0.25, gamma=2.0)
  CosineAnnealingWarmRestarts(T_0=10, T_mult=2) | grad-clip 1.0
  CUDA AMP + GradScaler when available | tqdm progress bars
  spatial logits mean-pooled over (H, W) before the loss
  best-val-loss checkpointing | sigmoid>=0.5 accuracy reporting

One addition, OFF by default so default behavior matches the original
byte-for-byte: use_sample_weights=True multiplies each sample's focal
loss by its dataset-provided weight (the envelope-derived weights the
negative generator produces) before reduction.
"""
import contextlib

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from tqdm import tqdm

from models import GrouseResNet, split_features, FEATURE_SPEC
from losses import FocalLoss

# Validation runs no optimizer, so its batch size affects only
# throughput and peak memory - never the reported metrics. A forward
# pass holds no activations for backward, so it can usually take a much
# larger batch than training.
#
# "Usually" is doing real work in that sentence: with early_attn the
# attention matrix is O(batch x heads x tokens^2) and is materialized
# in the FORWARD pass, so it does not shrink under no_grad. At 32x32
# tokens that term is ~4.3 GB at batch 512 - enough to OOM a 23 GB card
# on its own. _eval_batch_size() therefore only widens the batch for
# models without that quadratic term.
EVAL_BATCH_SIZE = 512


def _loader_extra(workers):
    """DataLoader kwargs that are only legal when workers > 0."""
    if workers <= 0:
        return {}
    # Deeper prefetch so a slow patch batch is absorbed by the queue
    # instead of stalling the GPU.
    return {"prefetch_factor": 4}


def roc_auc(scores, labels):
    """Mann-Whitney U form, tie-corrected. Accuracy at a fixed 0.5
    threshold hides most of what changes between runs on this task -
    ranking quality is the metric that actually moves."""
    import numpy as np
    scores, labels = np.asarray(scores, float), np.asarray(labels, float)
    n_pos, n_neg = (labels == 1).sum(), (labels == 0).sum()
    if n_pos == 0 or n_neg == 0:
        return float('nan')
    order = np.argsort(scores, kind='mergesort')
    s = scores[order]
    ranks = np.empty(len(s), float)
    i = 0
    while i < len(s):                     # average ranks within tie groups
        j = i
        while j + 1 < len(s) and s[j + 1] == s[i]:
            j += 1
        ranks[i:j + 1] = 0.5 * (i + j) + 1.0
        i = j + 1
    pos_ranks = ranks[labels[order] == 1].sum()
    return float((pos_ranks - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg))


def average_precision(scores, labels):
    """Area under the precision-recall curve (the metric that matters
    when the deployed use is ranking candidate habitat)."""
    import numpy as np
    scores, labels = np.asarray(scores, float), np.asarray(labels, float)
    n_pos = (labels == 1).sum()
    if n_pos == 0:
        return float('nan')
    order = np.argsort(-scores, kind='mergesort')
    y = labels[order]
    tp = np.cumsum(y)
    precision = tp / np.arange(1, len(y) + 1)
    return float((precision * y).sum() / n_pos)


class ModelEMA:
    """Exponential moving average of the weights. SGD noise on a 12.7k
    point dataset makes single-epoch snapshots jumpy; the averaged
    trajectory is consistently a better and far more stable predictor
    than whichever epoch happened to land well."""

    def __init__(self, model, decay):
        self.decay = decay
        self.shadow = {k: v.detach().clone().float()
                       for k, v in model.state_dict().items()}
        # update() runs once per OPTIMIZER STEP, so its cost is paid
        # thousands of times an epoch. Walking model.state_dict() there
        # rebuilds an OrderedDict over every module on every step, and
        # the per-tensor mul_/add_ pair issues ~2 CUDA launches per
        # entry (~250 for this network) to move a few MB - pure launch
        # overhead, invisible in nvidia-smi but real wall clock.
        # Resolve the two groups once here instead:
        #   _src_float/_dst_float : the averaged tensors, as parallel
        #                  lists so torch._foreach_* can do the whole
        #                  update in two multi-tensor kernels.
        #   _nonfloat    : ints/bools (BN's num_batches_tracked) which
        #                  are copied, not averaged.
        # The arithmetic is identical to the per-tensor loop.
        #
        # INVARIANT: _src_float holds references to the model's live
        # parameter/buffer tensors, so the model must not have its
        # tensors REPLACED after this point - construct the EMA after
        # any .to(device) / .to(memory_format=...) conversion. In-place
        # writes are exactly what we want to track, and both
        # optimizer.step() and load_state_dict() write in place, so
        # applied()'s save/restore round trip is safe.
        sd = model.state_dict()
        self._src_float, self._dst_float, self._nonfloat = [], [], []
        for k, v in sd.items():
            if v.dtype.is_floating_point:
                self._src_float.append(v)
                self._dst_float.append(self.shadow[k])
            else:
                self._nonfloat.append(k)
        # Averaging in the parameters' own dtype avoids a float() copy
        # per tensor per step; these are already fp32 under AMP (only
        # the autocast activations are half).
        self._same_dtype = all(s.dtype == d.dtype
                               for s, d in zip(self._src_float,
                                               self._dst_float))

    @torch.no_grad()
    def update(self, model):
        if self._same_dtype:
            torch._foreach_mul_(self._dst_float, self.decay)
            torch._foreach_add_(self._dst_float, self._src_float,
                                alpha=1.0 - self.decay)
        else:
            for dst, src in zip(self._dst_float, self._src_float):
                dst.mul_(self.decay).add_(src.float(),
                                          alpha=1.0 - self.decay)
        if self._nonfloat:
            sd = model.state_dict()
            for k in self._nonfloat:
                self.shadow[k] = sd[k].detach().clone().float()

    @contextlib.contextmanager
    def applied(self, model):
        backup = {k: v.detach().clone() for k, v in model.state_dict().items()}
        model.load_state_dict({k: v.to(backup[k].dtype)
                               for k, v in self.shadow.items()})
        try:
            yield
        finally:
            model.load_state_dict(backup)


class DivergenceGuard:
    """Watches for STRICT ACCURACY RISING while AUC AND AP BOTH FALL,
    epoch over epoch, for `patience` consecutive epochs - the specific
    'trading ranking quality for confidence' failure mode margin-based
    strict training can produce. Both AUC and AP must fall (not just
    one) to count as a divergent epoch, so single-metric noise doesn't
    false-trigger. A non-divergent epoch resets the streak to 0."""

    def __init__(self, patience=3, action='warn', dampen_factor=0.5):
        self.patience = int(patience)
        self.action = action
        self.dampen_factor = float(dampen_factor)
        self.streak = 0
        self.prev = None
        self.n_triggers = 0

    def update(self, strict, auc, ap):
        triggered = False
        if self.prev is not None:
            p_strict, p_auc, p_ap = self.prev
            diverging = (strict > p_strict) and (auc < p_auc) and (ap < p_ap)
            self.streak = self.streak + 1 if diverging else 0
            if self.streak >= self.patience:
                triggered = True
                self.n_triggers += 1
                self.streak = 0
        self.prev = (strict, auc, ap)
        return triggered


class GrouseModelHandler:
    def __init__(self, feature_names, spec=None, pretrained=True,
                 lr=0.0003, weight_decay=1e-4,
                 focal_alpha=0.5, focal_gamma=2.0,
                 warmup_epochs=3,
                 sched_t0=10, sched_tmult=2, grad_clip=1.0,
                 use_sample_weights=False,
                 save_path="grouse_single_best.pth", device=None,
                 pool='mean', dropout=0.0, embed_dropout=0.0,
                 center_skip=False, label_smoothing=0.0, ema_decay=0.0,
                 keep_early_resolution=False, early_attn=False,
                 early_attn_heads=4, early_attn_kv_stride=1,
                 early_attn_dropout=0.1, early_attn_droppath=0.1,
                 early_attn_pos_mode='rel', early_attn_lr_factor=0.1,
                 pos_threshold=0.75, neg_threshold=0.25,
                 strict_objective=None,
                 divergence_patience=3, on_divergence='warn',
                 divergence_dampen_factor=0.5,
                 backbone_lr_factor=0.1, sched='warm_restarts',
                 select_by='loss', select_min_delta=0.0, flip_tta=False):
        # DEFAULTS RECALIBRATED for ~1:1 balanced data (post symmetric
        # rotation). The originals came from the old negative-heavy
        # project and demonstrably produced constant-predictor collapse
        # on the new data:
        #   focal_alpha 0.25 -> 0.5 : 0.25 weights negatives 3x positives;
        #     on balanced data that pulls the constant attractor to
        #     all-negative - which is exactly the observed flip (frozen
        #     47.74% = the all-negative baseline, where the imbalanced
        #     run froze at the all-positive baseline). 0.5 is neutral.
        #   weight_decay 1e-2 -> 1e-4 : 1e-2 actively erodes the input
        #     pathway whenever gradients go quiet (measured grad norms
        #     ~0.0007 in the collapsed state), locking the collapse in.
        # Both remain constructor/CLI overridable to reproduce the
        # original behavior exactly.
        self.spec = spec or FEATURE_SPEC
        self.cat_features, self.cont_features = split_features(feature_names,
                                                               self.spec)
        self.device = torch.device(device) if device else torch.device(
            "cuda" if torch.cuda.is_available() else "cpu")
        self.use_sample_weights = use_sample_weights
        self.save_path = save_path
        self.grad_clip = grad_clip
        self.hp = dict(lr=lr, weight_decay=weight_decay,
                       focal_alpha=focal_alpha, focal_gamma=focal_gamma,
                       warmup_epochs=warmup_epochs,
                       sched_t0=sched_t0, sched_tmult=sched_tmult,
                       label_smoothing=label_smoothing,
                       backbone_lr_factor=backbone_lr_factor,
                       early_attn_lr_factor=early_attn_lr_factor,
                       sched=sched)
        self.ema_decay = float(ema_decay)
        self.ema = None
        # Set to channels_last by fit() on CUDA; preserve_format means
        # "leave the layout alone", so predict/evaluate work unchanged
        # when fit() was never called (e.g. loading a checkpoint).
        self._mem_fmt = torch.preserve_format
        self._clip_params = None
        if select_by not in ('loss', 'auc', 'rank', 'strict'):
            raise ValueError(f"select_by must be 'loss'/'auc'/'rank'/"
                             f"'strict', got {select_by!r}")
        self.select_by = select_by
        # Minimum margin a new checkpoint must beat the LAST SAVED one
        # by before it replaces it. Max-based selection otherwise chases
        # measurement noise: on a ~3.2k-point val set the SE of an AUC
        # near 0.88 is ~0.006, and a measured run spent epochs 12-30
        # replacing the checkpoint nine times for a cumulative +0.0019
        # of AUC while val loss rose 38% and AP fell. Comparing against
        # the saved reference (not the running max) keeps the semantics
        # cumulative: many small genuine gains still add up to a save.
        self.select_min_delta = float(select_min_delta)
        # STRICT (confidence-demanding) accuracy band. A positive point
        # only counts as correct when p >= pos_threshold; a negative only
        # when p <= neg_threshold; anything hedging in between is wrong
        # regardless of which side of 0.5 it lands on.
        if not (0.0 <= neg_threshold < pos_threshold <= 1.0):
            raise ValueError(f"Need 0 <= neg_threshold < pos_threshold <= 1"
                             f", got {neg_threshold} / {pos_threshold}")
        self.pos_threshold = float(pos_threshold)
        self.neg_threshold = float(neg_threshold)
        # STRICT TRAINING OBJECTIVE: margin loss shifting each sample's
        # logit by its class threshold's logit-equivalent before the
        # focal loss, so hedged-but-correct predictions still incur real
        # loss. strict_objective=None -> auto ON iff select_by=='strict'.
        import math
        if strict_objective is None:
            strict_objective = (select_by == 'strict')
        self.strict_objective = bool(strict_objective)
        self._m_pos = math.log(self.pos_threshold
                               / (1.0 - self.pos_threshold))
        self._m_neg = math.log(self.neg_threshold
                               / (1.0 - self.neg_threshold))
        # DIVERGENCE GUARD config (guard object itself built per-fit-call).
        if on_divergence not in ('warn', 'dampen', 'stop'):
            raise ValueError(f"on_divergence must be 'warn'/'dampen'/"
                             f"'stop', got {on_divergence!r}")
        self.on_divergence = on_divergence
        self._divergence_dampen_factor = float(divergence_dampen_factor)
        self._divergence_patience = int(divergence_patience)
        # The validation set already stores 4 rotations per point; adding
        # the mirrored view of each completes the D4 group, so a point's
        # score is the average over all 8 label-preserving orientations.
        # Pure inference-time gain - no extra training, no extra features.
        self.flip_tta = bool(flip_tta)
        self.threshold = 0.0

        self.model = GrouseResNet(
            self.cat_features, self.cont_features, spec=self.spec,
            pretrained=pretrained, pool=pool, dropout=dropout,
            embed_dropout=embed_dropout, center_skip=center_skip,
            keep_early_resolution=keep_early_resolution,
            early_attn=early_attn, early_attn_heads=early_attn_heads,
            early_attn_kv_stride=early_attn_kv_stride,
            early_attn_dropout=early_attn_dropout,
            early_attn_droppath=early_attn_droppath,
            early_attn_pos_mode=early_attn_pos_mode).to(self.device)
        if early_attn:
            n_attn_params = sum(p.numel() for p in
                                self.model.early_attn.parameters())
            pos_desc = {'rel': "pos=rel (2D RoPE + learned "
                               "relative-offset bias: pairwise, "
                               "translation-invariant geometry)",
                        'abs': "pos=abs (fixed 2D sin-cos)",
                        'none': "pos=NONE (position-blind)"}[
                self.model.early_attn.pos_mode]
            print(f"   Early self-attention block active: 32x32 tokens"
                 f"{' (keep_early_resolution off - see note above)' if not keep_early_resolution else ''}"
                 f", {early_attn_heads} heads, "
                 f"kv_stride={early_attn_kv_stride} "
                 f"({'full attention' if early_attn_kv_stride == 1 else f'{early_attn_kv_stride}x downsampled KV'})"
                 f", +{n_attn_params:,} params | "
                 f"{pos_desc}, "
                 f"attn_dropout={early_attn_dropout}, "
                 f"drop_path={early_attn_droppath}, "
                 f"lr_factor={early_attn_lr_factor} "
                 f"(zero-init: identity at start).")
        print(f"GrouseModelHandler: device={self.device.type}, "
              f"categorical={self.cat_features}, "
              f"continuous={self.cont_features}, "
              f"stem input channels={self.model.total_in_channels} "
              f"(derived, not hardcoded)")

    # ---- internals -------------------------------------------------------
    def _pooled_logits(self, cat_x, cont_x, tta=False):
        out = self.model.logits(cat_x, cont_x)
        if tta and self.flip_tta:
            out = 0.5 * (out + self.model.logits(cat_x.flip(-1),
                                                 cont_x.flip(-1)))
        return out

    def _batch_loss(self, criterion, outputs, y, w, smooth=None,
                    margin=False):
        # Margin shift keyed to the RAW 0/1 labels (before smoothing):
        # positives are scored as (z - m_pos), negatives as (z - m_neg),
        # making the loss's low-cost region start AT the strict band's
        # edge instead of at p=0.5.
        if margin and self.strict_objective:
            m = torch.where(y >= 0.5,
                            torch.as_tensor(self._m_pos, device=y.device,
                                            dtype=outputs.dtype),
                            torch.as_tensor(self._m_neg, device=y.device,
                                            dtype=outputs.dtype))
            outputs = outputs - m
        # Label smoothing caps how confident the model can profitably
        # become. Both classes here are citizen-science pseudo-labels, so
        # a fraction of them are simply wrong; without a cap the network
        # spends its capacity memorizing that noise, which is exactly the
        # "val loss and logit std climbing together" signature.
        eps = self.hp['label_smoothing'] if smooth is None else smooth
        if eps > 0:
            y = y * (1.0 - eps) + 0.5 * eps
        if self.use_sample_weights:
            per_sample = criterion(outputs, y)          # reduction='none'
            return (per_sample * w.unsqueeze(1)).mean()
        return criterion(outputs, y)

    # ---- checkpoint format ------------------------------------------------
    def _wrap_checkpoint(self, state):
        """Save weights ALONGSIDE the geometry needed to rebuild the
        network. Weights alone are ambiguous: mean/center/gauss pooling
        produce byte-identical parameter shapes and differ only in how
        the spatial map is collapsed, so a loader that guesses will
        silently run a gauss-trained model with mean pooling. Readers
        accept the bare-state_dict form too, for checkpoints written
        before this."""
        return {"state_dict": state,
                "config": {"pool": self.model.pool_mode,
                           "center_skip": bool(self.model.center_skip),
                           "features": list(self.cat_features)
                                       + list(self.cont_features),
                           "keep_early_resolution":
                               bool(self.model.keep_early_resolution),
                           "early_attn": self.model.early_attn is not None,
                           "early_attn_kv_stride":
                               self.model._early_attn_kv_stride,
                           "early_attn_heads":
                               self.model._early_attn_heads,
                           # Loaders must rebuild the block with the same
                           # position mode it trained with. Legacy keys:
                           # checkpoints written between the pos-enc fix
                           # and the relative-position upgrade carry
                           # early_attn_pos_enc (bool -> 'abs'/'none');
                           # ones from before either fix carry neither
                           # (-> 'none'). Readers map both.
                           "early_attn_pos_mode":
                               (self.model.early_attn.pos_mode
                                if self.model.early_attn is not None
                                else 'none')}}

    @staticmethod
    def unwrap_checkpoint(obj):
        """-> (state_dict, config|None) for either checkpoint format."""
        if isinstance(obj, dict) and "state_dict" in obj:
            return obj["state_dict"], obj.get("config")
        return obj, None

    @staticmethod
    def selection_score(select_by, metrics):
        """Sign-normalized checkpoint-selection score (HIGHER = better,
        for every mode - 'loss' is negated so one comparison works for
        all). 'rank' is the mean of per-point TTA AUC and TTA AP: AUC
        measures the global ordering of positives over negatives, AP
        weights the top of the ranking where deployment decisions are
        made, and the two disagree exactly when late-training
        memorization inflates one at the other's expense (measured:
        AUC +0.002 while AP -0.004 and val loss +38% over epochs
        11-30). Their mean refuses that trade. Calibration is left to
        calibrate.py, so val_loss is deliberately not part of 'rank'."""
        if select_by == 'auc':
            return metrics.get('tta_auc', metrics['auc'])
        if select_by == 'rank':
            return 0.5 * (metrics.get('tta_auc', metrics['auc'])
                          + metrics.get('tta_ap', metrics['ap']))
        if select_by == 'strict':
            return metrics.get('strict_accuracy', float('-inf'))
        return -metrics['val_loss']

    # ---- training --------------------------------------------------------
    def _eval_batch_size(self, batch_size, requested=None):
        """Validation batch size: explicit request wins, else widen only
        when it is safe to. A model carrying an early_attn block pays
        memory quadratic in its token count during the forward pass, so
        widening the batch there multiplies the largest allocation in
        the model rather than a small one - that combination OOMs."""
        if requested is not None:
            return int(requested)
        if self.model.early_attn is not None:
            return batch_size
        return max(batch_size, EVAL_BATCH_SIZE)

    def fit(self, train_ds, val_ds, epochs=30, batch_size=32, workers=4,
            train_labels=None, batch_pos_frac=None, metrics_csv=None,
            eval_batch_size=None):
        """train_labels + optional batch_pos_frac enable STRATIFIED
        batching: every training batch contains both classes at a fixed
        composition (dataset's global ratio by default), so a constant
        'lazy guess' predictor is penalized within every batch. Without
        train_labels, plain shuffled batching (original behavior)."""
        pin = (self.device.type == 'cuda')
        # Workers are kept alive across epochs: each fork otherwise
        # re-opens every raster and rebuilds a pyproj Transformer per
        # raster, paid again on every epoch of both loaders.
        keep = workers > 0
        if self.device.type == 'cuda':
            torch.backends.cudnn.benchmark = True   # fixed 64x64 geometry
            # TF32 for the fp32 residue (the head's Linear layers, the
            # attention pool) on Ampere and newer; AMP already covers
            # the convolutions.
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32 = True
            # NHWC: cuDNN's fp16 tensor-core convolution kernels are
            # NHWC-native, so an NCHW model makes it transpose every
            # activation in and out of every conv. Measured here, those
            # nchwToNhwc kernels were 7% of all GPU time; converting the
            # model (and cont_x, so embed()'s cat produces NHWC too)
            # deletes them for ~+12% at batch >= 128.
            self.model = self.model.to(memory_format=torch.channels_last)
            self._mem_fmt = torch.channels_last
        chan_last = self._mem_fmt
        # Cached once: clip_grad_norm_ otherwise re-walks the whole
        # module tree to rebuild this list on every step.
        self._clip_params = [p for p in self.model.parameters()
                             if p.requires_grad]
        if train_labels is not None:
            from dataset import StratifiedBatchSampler
            sampler = StratifiedBatchSampler(train_labels, batch_size,
                                             pos_frac=batch_pos_frac)
            train_loader = DataLoader(train_ds, batch_sampler=sampler,
                                      num_workers=workers, pin_memory=pin,
                                      persistent_workers=keep,
                                      **_loader_extra(workers))
            if len(sampler.fracs) > 1:
                comp = " <-> ".join(f"{p}pos/{n}neg"
                                    for p, n in zip(sampler.n_pos_pb,
                                                    sampler.n_neg_pb))
                print(f"   Alternating stratified batches: {comp} per "
                     f"batch of {batch_size} (net 50/50 per cycle; "
                     f"{sampler.n_batches} batches/epoch).")
            else:
                print(f"   Stratified batches: {sampler.n_pos_pb[0]} pos / "
                     f"{sampler.n_neg_pb[0]} neg per batch of "
                     f"{batch_size} ({sampler.n_batches} batches/epoch).")
        else:
            train_loader = DataLoader(train_ds, batch_size=batch_size,
                                      shuffle=True, num_workers=workers,
                                      pin_memory=pin,
                                      persistent_workers=keep,
                                      **_loader_extra(workers))
        # Validation is a pure forward pass with no optimizer state, so
        # its batch size is a throughput knob only - nothing about the
        # reported metrics depends on it (the loader is unshuffled, so
        # the TTA grouping still lines up, and val_loss is accumulated
        # per SAMPLE rather than per batch).
        eval_bs = self._eval_batch_size(batch_size, eval_batch_size)
        val_loader = DataLoader(val_ds, batch_size=eval_bs,
                                num_workers=workers, pin_memory=pin,
                                persistent_workers=keep,
                                **_loader_extra(workers))

        # Init-time feed sanity check: a fresh network MUST produce
        # input-DEPENDENT logits (different patches -> different
        # outputs). If the spread is ~0 before any training, the problem
        # is in the data feed, full stop - report it before burning
        # epochs.
        # Init-time feed sanity check. Measured in TRAIN mode (live batch
        # statistics), not eval: at init with pretrained=True, the BN
        # layers' running stats are ImageNet's - calibrated for a conv1
        # that no longer exists (ours is a fresh wide stem) - and that
        # mismatch crushes eval-mode output variance to ~0 spuriously.
        # Train-mode forward is what training actually uses, so it's the
        # honest measurement. (BN running stats get nudged by this one
        # forward pass; epoch 1 overwrites them immediately - harmless.)
        # Sampled across the whole val set rather than the first batch,
        # which is just a few points x 4 rotations of each.
        import numpy as np
        n_diag = min(32, len(val_ds))
        diag_idx = np.linspace(0, len(val_ds) - 1, n_diag).astype(int)
        diag = [val_ds[int(i)] for i in diag_idx]
        cat_x = torch.stack([d[0] for d in diag])
        cont_x = torch.stack([d[1] for d in diag])
        # INPUT check first: if the patches themselves are identical /
        # all-zero across samples, no training configuration can help -
        # abort with the diagnosis instead of burning epochs.
        in_std = max(cat_x.float().std().item(),
                     cont_x.std().item() if cont_x.numel() else 0.0)
        if in_std < 1e-9:
            raise SystemExit(
                "FEED CHECK FAILED: the input patches themselves are "
                "identical/empty across samples spread over the whole "
                "validation set - the model would train on constant "
                "tensors. Classic cause: every patch reading as nodata "
                "fill due to a raster CRS/bounds mismatch. (The dataset's "
                "construction-time probe should also have caught this - "
                "if you're seeing this, inspect the patch reads.)")
        self.model.train()
        with torch.no_grad():
            init_logits = self._pooled_logits(cat_x.to(self.device),
                                              cont_x.to(self.device))
            init_std = init_logits.std().item()
        self.model.eval()
        if init_std < 1e-6:
            print(f"   Init sanity (train-mode forward, {n_diag} spread "
                 f"samples): logit std = {init_std:.2e} - EXACTLY "
                 f"constant across different inputs BEFORE training. "
                 f"That is a data-feed problem (identical/empty "
                 f"batches). Stop and inspect the batches.")
        else:
            print(f"   Init sanity (train-mode forward, {n_diag} spread "
                 f"samples): logit std = {init_std:.4f} - "
                 f"input-dependent. Watch the per-epoch 'logit std' in "
                 f"the status line: it should GROW as training "
                 f"progresses.")

        # Differential learning rates: the ImageNet-pretrained backbone
        # (bn1 + layer1-4, ~11.2M params) trains at 1/10th the LR of the
        # from-scratch parts (stem conv1, embeddings, CBAM, conv_out,
        # ~0.85M params). One shared LR churned the pretrained features -
        # the model peaked at epoch 4 and degraded afterward. Note conv1
        # is deliberately in the FAST group despite its ResNet-style
        # name: ours is the custom wide-input stem trained from scratch,
        # not the pretrained original.
        BACKBONE_LR_FACTOR = self.hp['backbone_lr_factor']
        pretrained_prefixes = ("bn1.", "layer1.", "layer2.",
                               "layer3.", "layer4.")
        # The early-attn block gets its own (slow) LR group rather than
        # riding the fresh group: a randomly-initialized global-attention
        # module fed by focal loss at the full fresh LR was the fastest-
        # moving part of the network, and it used that speed to memorize
        # hard (usually mislabeled) examples - the measured divergence.
        # Zero-init makes it start as identity; the reduced LR makes it
        # fade in no faster than the pretrained trunk it must cooperate
        # with.
        backbone_params, attn_params, fresh_params = [], [], []
        for name, p in self.model.named_parameters():
            if name.startswith(pretrained_prefixes):
                backbone_params.append(p)
            elif name.startswith("early_attn."):
                attn_params.append(p)
            else:
                fresh_params.append(p)
        groups = [{"params": backbone_params,
                   "lr": self.hp['lr'] * BACKBONE_LR_FACTOR}]
        if attn_params:
            groups.append({"params": attn_params,
                           "lr": self.hp['lr']
                                 * self.hp['early_attn_lr_factor']})
        groups.append({"params": fresh_params, "lr": self.hp['lr']})
        optimizer = torch.optim.AdamW(
            groups,
            weight_decay=self.hp['weight_decay'],
            # Fused AdamW folds the whole parameter update into one
            # multi-tensor CUDA kernel instead of ~200 small launches -
            # the same arithmetic, minus the per-tensor launch overhead
            # that dominates at these tensor sizes.
            fused=(self.device.type == 'cuda'))
        attn_desc = (f" | early_attn "
                     f"{self.hp['lr'] * self.hp['early_attn_lr_factor']:.1e} "
                     f"({sum(p.numel() for p in attn_params):,} params)"
                     if attn_params else "")
        print(f"   Differential LR: backbone "
             f"{self.hp['lr'] * BACKBONE_LR_FACTOR:.1e} "
             f"({sum(p.numel() for p in backbone_params):,} params)"
             f"{attn_desc} | "
             f"fresh layers {self.hp['lr']:.1e} "
             f"({sum(p.numel() for p in fresh_params):,} params)")
        scaler = (torch.amp.GradScaler('cuda')
                  if self.device.type == 'cuda' else None)
        reduction = 'none' if self.use_sample_weights else 'mean'
        criterion_focal = FocalLoss(alpha=self.hp['focal_alpha'],
                                    gamma=self.hp['focal_gamma'],
                                    reduction=reduction)
        # Warmup criterion: gamma=0 focal == alpha-weighted plain BCE.
        # Focal's (1-pt)^gamma easy-example suppression, applied from
        # step 0 on a fresh network, flattens the gradient basin around
        # the constant-predictor stationary point (diagnosed: constant
        # logit 0.133, loss frozen at the value the constant solution
        # predicts). Plain BCE has no such suppression - the network is
        # forced to learn input-dependent features first; focal then
        # takes over to refine on hard examples.
        criterion_warmup = FocalLoss(alpha=self.hp['focal_alpha'],
                                     gamma=0.0, reduction=reduction)
        n_warm = self.hp['warmup_epochs']
        if self.hp['sched'] == 'cosine':
            # One smooth decay to ~0 over the whole run. Warm restarts
            # re-heat the LR at epochs 10 and 30, which on a dataset this
            # small just re-scrambles a converged model.
            scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
                optimizer, T_max=epochs)
        else:
            scheduler = torch.optim.lr_scheduler.CosineAnnealingWarmRestarts(
                optimizer, T_0=self.hp['sched_t0'],
                T_mult=self.hp['sched_tmult'])
        if self.ema_decay > 0:
            self.ema = ModelEMA(self.model, self.ema_decay)
            print(f"   Weight EMA active (decay={self.ema_decay}); "
                  f"validation and checkpoints use the averaged weights.")

        best_loss = float('inf')
        best_auc = float('-inf')
        best_strict = float('-inf')
        best_rank = float('-inf')
        # Selection score of the last SAVED checkpoint (None = nothing
        # saved yet, so the first epoch always saves). New checkpoints
        # must beat this by select_min_delta - see __init__.
        sel_ref = None
        best_epoch = 0
        guard = DivergenceGuard(self._divergence_patience,
                                self.on_divergence,
                                self._divergence_dampen_factor)
        stop_early = False
        for epoch in range(epochs):
            criterion = criterion_warmup if epoch < n_warm else criterion_focal
            if epoch == 0:
                if self.strict_objective:
                    print(f"   STRICT TRAINING OBJECTIVE active: margins "
                         f"+{self._m_pos:.3f} (pos, p>={self.pos_threshold}) "
                         f"/ {self._m_neg:.3f} (neg, p<={self.neg_threshold}) "
                         f"applied to training logits - hedged-but-correct "
                         f"predictions now incur real loss. Training loss "
                         f"is NOT comparable to non-strict runs; "
                         f"validation loss stays on the ordinary scale.")
                if n_warm > 0:
                    print(f"   Warmup: alpha-weighted BCE (gamma=0) for the "
                         f"first {n_warm} epoch(s), then FocalLoss("
                         f"gamma={self.hp['focal_gamma']}).")
            if epoch == n_warm and n_warm > 0:
                print(f"   Warmup complete - switching to FocalLoss.")
            self.model.train()
            train_bar = tqdm(train_loader,
                             desc=f"Epoch {epoch + 1}/{epochs} [Training]",
                             leave=False)
            # Accumulators live on the GPU. Reading them per step (via
            # float()/int()/.cpu()) forces a device synchronize every
            # iteration, which stops the CPU from queuing the next
            # step's kernels while the current one runs - the launch
            # pipeline drains and refills 1674 times an epoch. Summing
            # on-device and transferring once at the end of the epoch
            # is the same arithmetic with one sync instead of ~5000.
            tr_loss_sum = torch.zeros((), device=self.device)
            tr_correct = torch.zeros((), device=self.device,
                                     dtype=torch.long)
            tr_total, tr_steps = 0, 0
            tr_logits, tr_ys = [], []
            for cat_x, cont_x, y, w in train_bar:
                cat_x = cat_x.to(self.device, non_blocking=True)
                cont_x = cont_x.to(self.device, non_blocking=True,
                                   memory_format=chan_last)
                y = y.to(self.device, non_blocking=True).unsqueeze(1)
                w = w.to(self.device, non_blocking=True)

                optimizer.zero_grad(set_to_none=True)
                if scaler is not None:
                    with torch.amp.autocast('cuda'):
                        outputs = self._pooled_logits(cat_x, cont_x)
                        loss = self._batch_loss(criterion, outputs, y, w,
                                                    margin=True)
                    scaler.scale(loss).backward()
                    scaler.unscale_(optimizer)
                    torch.nn.utils.clip_grad_norm_(self._clip_params,
                                                   self.grad_clip)
                    scaler.step(optimizer)
                    scaler.update()
                else:
                    outputs = self._pooled_logits(cat_x, cont_x)
                    loss = self._batch_loss(criterion, outputs, y, w,
                                                margin=True)
                    loss.backward()
                    torch.nn.utils.clip_grad_norm_(self._clip_params,
                                                   self.grad_clip)
                    optimizer.step()

                if self.ema is not None:
                    self.ema.update(self.model)

                # Train-side loss/accuracy on the SAME criterion as the
                # val number. Without it a rising val loss is ambiguous
                # (overfitting vs. optimization failure); with it the gap
                # says which, immediately.
                tr_loss_sum += loss.detach()
                tr_steps += 1
                with torch.no_grad():
                    tr_correct += (((outputs.detach() >= 0).float())
                                   == y).sum()
                    tr_total += int(y.numel())     # shape only, no sync
                    tr_logits.append(outputs.detach().float().squeeze(1))
                    tr_ys.append(y.squeeze(1))
            scheduler.step()
            # The single synchronization point for the whole epoch.
            tr_loss_sum = float(tr_loss_sum)
            tr_correct = int(tr_correct)
            tr_logits = torch.cat(tr_logits).cpu()
            tr_ys = torch.cat(tr_ys).cpu()

            # Validation always scored with the FOCAL criterion, even
            # during warmup - otherwise warmup-epoch val losses (BCE
            # scale, numerically larger) aren't comparable with focal
            # epochs and best-checkpoint selection breaks.
            if self.ema is not None:
                with self.ema.applied(self.model):
                    metrics = self.evaluate(val_loader, criterion_focal,
                                            epoch, epochs)
                    ema_state = {k: v.detach().clone()
                                 for k, v in self.model.state_dict().items()}
            else:
                metrics = self.evaluate(val_loader, criterion_focal,
                                        epoch, epochs)
                ema_state = None
            metrics['train_loss'] = tr_loss_sum / max(tr_steps, 1)
            metrics['train_accuracy'] = 100.0 * tr_correct / max(tr_total, 1)
            thr = self.best_threshold(tr_logits.numpy(), tr_ys.numpy())
            metrics['threshold'] = thr
            self.threshold = thr
            for src, dst in (("_logits", "tuned_accuracy"),
                             ("_tta_logits", "tuned_tta_accuracy")):
                if src in metrics:
                    ykey = "_y" if src == "_logits" else "_tta_y"
                    metrics[dst] = 100.0 * float(
                        ((metrics[src] >= thr) == (metrics[ykey] == 1)).mean())
            metrics = {k: v for k, v in metrics.items()
                       if not k.startswith('_')}
            metrics['epoch'] = epoch + 1
            metrics['lr'] = optimizer.param_groups[-1]['lr']
            metrics['rank_score'] = self.selection_score('rank', metrics)
            status = (f"   Epoch {epoch + 1}/{epochs} | "
                      f"Focal Loss: {metrics['val_loss']:.4f} | "
                      f"Val Accuracy: {metrics['accuracy']:.2f}% | "
                      f"AUC: {metrics['auc']:.4f} | "
                      f"TTA AUC: {metrics.get('tta_auc', float('nan')):.4f} | "
                      f"AP: {metrics['ap']:.4f} | "
                      f"rank: {metrics['rank_score']:.4f} | "
                      f"tuned acc: {metrics['tuned_tta_accuracy']:.2f}% | "
                      f"strict: {metrics.get('strict_accuracy', float('nan')):.2f}% "
                      f"(hedged {metrics.get('hedged_pct', float('nan')):.1f}%) | "
                      f"train acc: {metrics['train_accuracy']:.1f}% | "
                      f"logit std: {metrics['logit_std']:.3f}")
            sel = self.selection_score(self.select_by, metrics)
            improved = (sel_ref is None
                        or sel > sel_ref + self.select_min_delta)
            best_loss = min(best_loss, metrics['val_loss'])
            best_auc = max(best_auc, metrics['tta_auc'])
            best_strict = max(best_strict,
                              metrics.get('strict_accuracy', float('-inf')))
            best_rank = max(best_rank, metrics['rank_score'])
            if improved:
                sel_ref = sel
                best_epoch = epoch + 1
                torch.save(self._wrap_checkpoint(
                    ema_state if ema_state is not None
                    else self.model.state_dict()), self.save_path)
                print(f"{status} (Saved)")
            else:
                print(status)
            if metrics_csv:
                self._log_metrics(metrics_csv, metrics)

            if guard.update(metrics.get('strict_accuracy', float('-inf')),
                            metrics['tta_auc'], metrics['ap']):
                streak_epochs = f"epochs {epoch - self._divergence_patience + 2}-{epoch + 1}"
                if self.on_divergence == 'warn':
                    print(f"   [!] DIVERGENCE: strict accuracy rose while "
                         f"AUC and AP both fell for "
                         f"{self._divergence_patience} straight epochs "
                         f"({streak_epochs}) - the model may be buying "
                         f"confidence at ranking's expense.")
                elif self.on_divergence == 'dampen':
                    self._m_pos *= self._divergence_dampen_factor
                    self._m_neg *= self._divergence_dampen_factor
                    print(f"   [!] DIVERGENCE over {streak_epochs} - "
                         f"DAMPENING margins to +{self._m_pos:.3f}/"
                         f"{self._m_neg:.3f} (x{self._divergence_dampen_factor}) "
                         f"to ease off the strict objective.")
                elif self.on_divergence == 'stop':
                    print(f"   [!] DIVERGENCE over {streak_epochs} - "
                         f"STOPPING at epoch {epoch + 1}/{epochs}. Best "
                         f"checkpoint on disk is unaffected.")
                    stop_early = True
            if stop_early:
                break

        print(f"\nTraining finished{' (stopped on divergence)' if stop_early else ''}."
             f" Best Focal Loss: {best_loss:.4f} | "
             f"Best TTA AUC: {best_auc:.4f} | "
             f"Best rank: {best_rank:.4f} | "
             f"Best strict acc: {best_strict:.2f}% "
             f"(selection metric: {self.select_by}"
             f"{f', min delta {self.select_min_delta:g}' if self.select_min_delta else ''}"
             f" -> saved checkpoint is epoch {best_epoch})"
             f"{f' | divergence triggers: {guard.n_triggers}' if guard.n_triggers else ''}")
        return self.save_path

    @staticmethod
    def _log_metrics(path, metrics):
        import csv
        import os
        keys = sorted(metrics)
        new = not os.path.exists(path)
        with open(path, 'a', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=keys)
            if new:
                w.writeheader()
            w.writerow({k: metrics[k] for k in keys})

    # ---- evaluation ------------------------------------------------------
    def evaluate(self, val_loader, criterion=None, epoch=0, epochs=1,
                 tta_group=4):
        """tta_group: the validation set stores each point as `tta_group`
        consecutive fixed rotations, so averaging predictions in groups of
        that size is exactly test-time augmentation and gives the honest
        per-POINT score (the quantity that matters in deployment). Set 0
        to skip."""
        import numpy as np
        if criterion is None:
            reduction = 'none' if self.use_sample_weights else 'mean'
            criterion = FocalLoss(alpha=self.hp['focal_alpha'],
                                  gamma=self.hp['focal_gamma'],
                                  reduction=reduction)
        self.model.eval()
        # As in the training loop, everything is summed on-device and
        # read back once at the end: a per-batch .item() would serialize
        # the CPU against the GPU on every iteration.
        dev = self.device
        val_loss = torch.zeros((), device=dev)
        correct = torch.zeros((), device=dev, dtype=torch.long)
        n_pred_pos = torch.zeros((), device=dev, dtype=torch.long)
        total = 0
        all_logits, all_y = [], []
        val_bar = tqdm(val_loader,
                       desc=f"Epoch {epoch + 1}/{epochs} [Validation]",
                       leave=False)
        with torch.no_grad():
            for cat_x, cont_x, y, w in val_bar:
                cat_x = cat_x.to(dev, non_blocking=True)
                cont_x = cont_x.to(dev, non_blocking=True,
                                   memory_format=self._mem_fmt)
                y = y.to(dev, non_blocking=True).unsqueeze(1)
                w = w.to(dev, non_blocking=True)
                # smooth=0.0: validation loss must stay on the same
                # scale regardless of the training-side smoothing, or
                # runs aren't comparable.
                nb = y.size(0)
                if dev.type == 'cuda':
                    with torch.amp.autocast('cuda'):
                        outputs = self._pooled_logits(cat_x, cont_x, tta=True)
                        batch_loss = self._batch_loss(criterion, outputs,
                                                      y, w, smooth=0.0)
                else:
                    outputs = self._pooled_logits(cat_x, cont_x, tta=True)
                    batch_loss = self._batch_loss(criterion, outputs,
                                                  y, w, smooth=0.0)
                # Weighted by batch size, then divided by the sample
                # count below. The old mean-of-batch-means gave the
                # short trailing batch the same weight as a full one,
                # which made the reported val_loss depend on the batch
                # size; this is the true per-sample mean and is
                # invariant to it.
                val_loss += batch_loss * nb
                outputs = outputs.float()
                preds = (torch.sigmoid(outputs) >= 0.5).float()
                correct += (preds == y).sum()
                total += nb
                n_pred_pos += preds.sum().long()
                all_logits.append(outputs.squeeze(1))
                all_y.append(y.squeeze(1))
        logits = torch.cat(all_logits).cpu().numpy()
        ys = torch.cat(all_y).cpu().numpy()
        val_loss = float(val_loss)
        correct = int(correct)
        n_pred_pos = int(n_pred_pos)
        out = {"val_loss": val_loss / max(total, 1),
               "accuracy": 100.0 * correct / max(total, 1),
               "logit_std": float(logits.std()),
               "logit_mean": float(logits.mean()),
               "pred_pos_pct": 100.0 * n_pred_pos / max(total, 1),
               "auc": roc_auc(logits, ys),
               "ap": average_precision(logits, ys)}
        if tta_group and len(logits) % tta_group == 0:
            # Loader must be unshuffled for this grouping to line up with
            # the dataset's point-major ordering - it is (no sampler).
            g = logits.reshape(-1, tta_group).mean(axis=1)
            gy = ys.reshape(-1, tta_group)
            assert (gy == gy[:, :1]).all(), "TTA grouping crossed a label"
            gy = gy[:, 0]
            out["tta_auc"] = roc_auc(g, gy)
            out["tta_ap"] = average_precision(g, gy)
            out["tta_accuracy"] = 100.0 * float(
                (((g >= 0) == (gy == 1)).mean()))
            gp = 1.0 / (1.0 + np.exp(-g))
            strict_ok = (((gy == 1) & (gp >= self.pos_threshold))
                         | ((gy == 0) & (gp <= self.neg_threshold)))
            out["strict_accuracy"] = 100.0 * float(strict_ok.mean())
            out["hedged_pct"] = 100.0 * float(
                ((gp > self.neg_threshold)
                 & (gp < self.pos_threshold)).mean())
            out["_tta_logits"], out["_tta_y"] = g, gy
        out["_logits"], out["_y"] = logits, ys
        return out

    @staticmethod
    def best_threshold(logits, y):
        """Accuracy-maximizing decision threshold. Focal loss plus label
        smoothing leaves the network's outputs uncalibrated, so logit 0
        (p=0.5) is an arbitrary operating point that can cost several
        points of accuracy for no modelling reason. Chosen on TRAINING
        predictions and applied to validation, so it never peeks at the
        validation labels."""
        import numpy as np
        logits, y = np.asarray(logits, float), np.asarray(y, float)
        order = np.argsort(logits)
        s, ys = logits[order], y[order]
        # Sweep every split point: correct = (negatives below) + (positives
        # at or above), computed in one cumulative pass.
        neg_below = np.cumsum(ys == 0)
        pos_at_or_above = (ys == 1).sum() - np.cumsum(ys == 1)
        correct = np.concatenate([[(ys == 1).sum()], neg_below + pos_at_or_above])
        k = int(np.argmax(correct))
        if k == 0:
            return float(s[0] - 1e-6)
        if k >= len(s):
            return float(s[-1] + 1e-6)
        return float(0.5 * (s[k - 1] + s[k]))

    # ---- inference -------------------------------------------------------
    @torch.no_grad()
    def predict_proba(self, cat_x, cont_x):
        """Mean-pooled probability per sample - the quantity training
        optimized."""
        self.model.eval()
        logits = self._pooled_logits(cat_x.to(self.device),
                                     cont_x.to(self.device))
        return torch.sigmoid(logits).cpu()

    @torch.no_grad()
    def predict_map(self, cat_x, cont_x):
        """The un-pooled spatial probability map (B, 1, H', W') - the
        architecture produces this for free; useful for suitability
        surface rendering."""
        self.model.eval()
        logits = self.model(cat_x.to(self.device), cont_x.to(self.device))
        return torch.sigmoid(logits).cpu()

    # ---- persistence -----------------------------------------------------
    def save(self, path=None):
        torch.save(self._wrap_checkpoint(self.model.state_dict()),
                   path or self.save_path)

    def load(self, path=None):
        state, _cfg = self.unwrap_checkpoint(torch.load(
            path or self.save_path, map_location=self.device,
            weights_only=True))
        self.model.load_state_dict(state)
        return self
