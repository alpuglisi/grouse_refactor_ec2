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
from losses import FocalLoss, ANFullLoss
from grouse_data import NLCD_NAMES

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
                 loss='focal', an_pos_weight=1.0,
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
                 dual_branch='off', dual_branch_channels=64,
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
        if loss not in ('focal', 'an_full'):
            raise ValueError(f"loss must be 'focal' or 'an_full', "
                             f"got {loss!r}")
        self.loss_type = loss
        self.an_pos_weight = float(an_pos_weight)
        self.hp = dict(lr=lr, weight_decay=weight_decay,
                       loss=loss, an_pos_weight=self.an_pos_weight,
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
        # Base/ceiling values for --dynamic-dropout (see _set_dropout):
        # the network is built with these fixed values below exactly as
        # before, dynamic scaling is opt-in per fit() call.
        self._base_dropout = float(dropout)
        self._base_embed_dropout = float(embed_dropout)

        self.model = GrouseResNet(
            self.cat_features, self.cont_features, spec=self.spec,
            pretrained=pretrained, pool=pool, dropout=dropout,
            embed_dropout=embed_dropout, center_skip=center_skip,
            keep_early_resolution=keep_early_resolution,
            early_attn=early_attn, early_attn_heads=early_attn_heads,
            early_attn_kv_stride=early_attn_kv_stride,
            early_attn_dropout=early_attn_dropout,
            early_attn_droppath=early_attn_droppath,
            early_attn_pos_mode=early_attn_pos_mode,
            dual_branch=dual_branch,
            dual_branch_channels=dual_branch_channels).to(self.device)
        if dual_branch != 'off':
            n_b = (sum(p.numel() for p in
                       self.model.spatial_branch.parameters())
                   + sum(p.numel() for p in
                         self.model.spatial_head.parameters()))
            print(f"   Dual-branch head active: Branch B = "
                  f"{dual_branch} ({dual_branch_channels} ch, full-"
                  f"resolution multi-scale via dilation), pooled with "
                  f"'{pool}', +{n_b:,} params, zero-init head "
                  f"(identity at start).")
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
                                else 'none'),
                           "dual_branch": self.model.dual_branch,
                           "dual_branch_channels":
                               self.model._dual_branch_channels,
                           # Not geometry, but consumers of the LOGITS
                           # need it: an asymmetric objective (an_full
                           # with lambda != 1, focal with alpha != 0.5)
                           # builds a constant logit bias into the
                           # trained model, which temperature scaling
                           # (a pure scale) can never remove -
                           # predict.py/calibrate.py read these to warn
                           # when a fitted temperature can't mean what
                           # it claims.
                           "loss": self.loss_type,
                           "an_pos_weight": self.an_pos_weight,
                           "focal_alpha": float(self.hp['focal_alpha'])}}

    @staticmethod
    def unwrap_checkpoint(obj):
        """-> (state_dict, config|None) for either checkpoint format."""
        if isinstance(obj, dict) and "state_dict" in obj:
            return obj["state_dict"], obj.get("config")
        return obj, None

    def _set_dropout(self, value):
        """--dynamic-dropout's actuator: every plain nn.Dropout/
        nn.Dropout2d module in the network (self.drop, plus
        center_head's/spatial_head's if those heads are active) reads
        its .p fresh on every forward call, so mutating it here takes
        effect on the very next batch - no rebuild needed. embed_dropout
        is a manually-applied float rather than a module (see
        GrouseResNet.embed), so it's set directly, scaled by its
        construction-time ratio to --dropout so the two move together
        under one schedule instead of needing separate tuning."""
        for m in self.model.modules():
            if isinstance(m, (nn.Dropout, nn.Dropout2d)):
                m.p = value
        if self._base_dropout > 0:
            self.model.embed_dropout = (
                value * self._base_embed_dropout / self._base_dropout)

    def _resume_path(self):
        return self.save_path + ".resume"

    def _save_resume_state(self, next_epoch, optimizer, scheduler, scaler,
                           sel_ref, best_epoch, best_loss, best_auc,
                           best_strict, best_rank, dd_value=None,
                           dd_prev_gap=None):
        """Everything --resume needs to continue this exact run, not just
        the weights: optimizer momentum (Adam's moment estimates would
        otherwise restart from zero) and scheduler position (critical
        for warm restarts - losing schedule phase means silently
        reheating the LR right where a previous run may have just
        crashed from doing that). self.model.state_dict() here is the
        LIVE training weights (any EMA context has already exited by
        this point in the epoch loop, restoring them - see ModelEMA.
        applied), which is what the optimizer actually stepped and what
        resuming must continue from, not the EMA snapshot that gets
        saved to self.save_path instead."""
        torch.save({
            "model_state": self.model.state_dict(),
            "optimizer_state": optimizer.state_dict(),
            "scheduler_state": scheduler.state_dict(),
            "scaler_state": scaler.state_dict() if scaler is not None
                           else None,
            "ema_state": ({k: v.cpu() for k, v in self.ema.shadow.items()}
                         if self.ema is not None else None),
            "epoch": next_epoch,
            "sel_ref": sel_ref,
            "best_epoch": best_epoch,
            "best_loss": best_loss,
            "best_auc": best_auc,
            "best_strict": best_strict,
            "best_rank": best_rank,
            "dynamic_dropout_value": dd_value,
            "dynamic_dropout_prev_gap": dd_prev_gap,
            "config": self._wrap_checkpoint(None)["config"],
        }, self._resume_path())

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

    def load_backbone(self, path):
        """Initialize matching weights from a pretraining checkpoint -
        pretrain.py's self-supervised SimSiam backbone, or any
        GrouseResNet-keyed state dict. Tensors absent from the
        checkpoint (conv_out, center_head, ...) keep their fresh
        initialization; shape mismatches (e.g. a different feature set)
        are skipped with a report rather than failing. Every loaded
        parameter joins fit()'s reduced-LR backbone group: after
        pretraining it is no longer "fresh", and full-LR churn is what
        the differential-LR scheme exists to prevent."""
        state, cfg = self.unwrap_checkpoint(
            torch.load(path, map_location=self.device, weights_only=True))
        msd = self.model.state_dict()
        matched = {k: v for k, v in state.items()
                   if k in msd and msd[k].shape == v.shape}
        mismatched = [k for k in state
                      if k in msd and k not in matched]
        absent = [k for k in state if k not in msd]
        self.model.load_state_dict(matched, strict=False)
        self._transfer_loaded = set(matched)
        print(f"   Backbone init from {path}: {len(matched)} tensors "
              f"loaded ({len(msd) - len(matched)} stay at fresh init - "
              f"head layers etc.)"
              f"{f'; {len(mismatched)} shape-mismatched skipped' if mismatched else ''}"
              f"{f'; {len(absent)} checkpoint-only ignored' if absent else ''}. "
              f"Loaded parameters train in the backbone LR group.")
        if cfg and cfg.get("features"):
            here = set(self.cat_features) | set(self.cont_features)
            if set(cfg["features"]) != here:
                print(f"   [warn] pretraining used features "
                      f"{sorted(cfg['features'])} but this model uses "
                      f"{sorted(here)} - shared tensors transferred, "
                      f"the rest stay fresh.")
        return set(matched)

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
            eval_batch_size=None, tb_writer=None, tb_log_every=50,
            tb_images=True, tb_attention=True, tb_embeddings=True,
            tb_embeddings_every=10, resume_from=None, dynamic_dropout=False,
            dynamic_dropout_min=None, dynamic_dropout_max=None,
            dynamic_dropout_step=0.01):
        """train_labels + optional batch_pos_frac enable STRATIFIED
        batching: every training batch contains both classes at a fixed
        composition (dataset's global ratio by default), so a constant
        'lazy guess' predictor is penalized within every batch. Without
        train_labels, plain shuffled batching (original behavior)."""
        if dynamic_dropout and self._base_dropout <= 0:
            raise SystemExit(
                "--dynamic-dropout requires --dropout > 0: it scales "
                "dropout up/down from that value each epoch, and 0 has "
                "nothing to scale.")
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
        # ONE fixed batch (loader is unshuffled), grabbed once and
        # reused every epoch: image/attention diagnostics then show the
        # SAME patches evolving across training, which is what makes
        # them useful for troubleshooting (a per-epoch random batch
        # would make "did this change" impossible to eyeball).
        vis_batch = None
        if tb_writer is not None and tb_images:
            try:
                vis_batch = next(iter(val_loader))
            except StopIteration:
                vis_batch = None

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
        # Parameters initialized from a pretraining checkpoint
        # (load_backbone) also count as backbone: pretrained weights get
        # the reduced LR whatever their module name. early_attn keeps
        # its own group either way.
        transfer = getattr(self, '_transfer_loaded', frozenset())
        backbone_params, attn_params, fresh_params = [], [], []
        for name, p in self.model.named_parameters():
            if name.startswith("early_attn."):
                attn_params.append(p)
            elif name.startswith(pretrained_prefixes) or name in transfer:
                backbone_params.append(p)
            else:
                fresh_params.append(p)
        groups = [{"params": backbone_params,
                   "lr": self.hp['lr'] * BACKBONE_LR_FACTOR}]
        group_names = ["backbone"]
        if attn_params:
            groups.append({"params": attn_params,
                           "lr": self.hp['lr']
                                 * self.hp['early_attn_lr_factor']})
            group_names.append("early_attn")
        groups.append({"params": fresh_params, "lr": self.hp['lr']})
        group_names.append("fresh")
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
        if self.loss_type == 'an_full':
            # L_AN-full (Cole et al.): lambda-weighted BCE with every
            # negative ASSUMED. No focal phase exists in this objective,
            # so the BCE->focal warmup schedule is moot: the same
            # criterion runs start to finish (and it is already plain
            # BCE at lambda=1, i.e. the warmup's own recipe).
            criterion_focal = ANFullLoss(pos_weight=self.an_pos_weight,
                                         reduction=reduction)
            criterion_warmup = criterion_focal
            n_warm = 0
            loss_label = "AN-full Loss"
            print(f"   AN-full loss active (Cole et al., L_AN-full): "
                  f"positive terms weighted x{self.an_pos_weight:g}, all "
                  f"negatives assumed true negatives"
                  f"{'; --warmup-epochs ignored (no focal phase).' if self.hp['warmup_epochs'] else '.'}"
                  f" Val loss is on the AN-full scale - not comparable "
                  f"to focal runs.")
        else:
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
            loss_label = "Focal Loss"
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
        start_epoch = 0
        # --dynamic-dropout: reacts to the val/train loss gap rather than
        # a fixed clock. dd_value starts at the CLI --dropout/--embed-
        # dropout values (so epoch 1 behaves exactly as without the
        # flag) and is nudged toward dd_max as the gap WIDENS
        # (overfitting worsening) or dd_min as it NARROWS, each epoch,
        # once a previous epoch's gap exists to compare against.
        dd_value = self._base_dropout if dynamic_dropout else None
        dd_prev_gap = None
        dd_min = dd_max = None
        if dynamic_dropout:
            dd_min = (dynamic_dropout_min if dynamic_dropout_min is not None
                     else 0.3 * self._base_dropout)
            dd_max = (dynamic_dropout_max if dynamic_dropout_max is not None
                     else min(0.6, 1.6 * self._base_dropout))
            if not (0 <= dd_min <= dd_value <= dd_max):
                raise SystemExit(
                    f"--dynamic-dropout range must satisfy 0 <= min <= "
                    f"--dropout <= max, got min={dd_min:g} dropout="
                    f"{dd_value:g} max={dd_max:g}.")
        if resume_from:
            # A SEPARATE file from self.save_path: the deployment
            # checkpoint stays the lean {state_dict, config} predict.py/
            # calibrate.py load with weights_only=True, while resuming
            # needs optimizer/scheduler momentum and step position too
            # (without them, Adam's moment estimates restart from zero
            # and a warm-restart schedule loses its phase - a "resume"
            # that silently reheats the LR at the exact point that just
            # crashed the run is worse than a clean restart).
            state = torch.load(resume_from, map_location=self.device,
                               weights_only=False)
            saved_cfg = state.get('config')
            cur_cfg = self._wrap_checkpoint(None)['config']
            if saved_cfg is not None and saved_cfg != cur_cfg:
                raise SystemExit(
                    f"--resume checkpoint geometry doesn't match this "
                    f"run's model - rebuild with the SAME flags as the "
                    f"original run.\n  saved:   {saved_cfg}\n"
                    f"  current: {cur_cfg}")
            self.model.load_state_dict(state['model_state'])
            optimizer.load_state_dict(state['optimizer_state'])
            scheduler.load_state_dict(state['scheduler_state'])
            if scaler is not None and state.get('scaler_state') is not None:
                scaler.load_state_dict(state['scaler_state'])
            if self.ema is not None and state.get('ema_state') is not None:
                self.ema.shadow = {k: v.to(self.device)
                                   for k, v in state['ema_state'].items()}
            start_epoch = state['epoch']
            sel_ref = state.get('sel_ref')
            best_epoch = state.get('best_epoch', 0)
            best_loss = state.get('best_loss', best_loss)
            best_auc = state.get('best_auc', best_auc)
            best_strict = state.get('best_strict', best_strict)
            best_rank = state.get('best_rank', best_rank)
            if dynamic_dropout:
                # Falls back to the fresh-start values above if this
                # resume file predates --dynamic-dropout (key absent) or
                # the original run didn't use it (value stored as None)
                # - a crash-and-resume shouldn't reset an in-progress
                # dropout schedule back to the base value either way.
                saved_dd = state.get('dynamic_dropout_value')
                dd_value = saved_dd if saved_dd is not None else dd_value
                dd_prev_gap = state.get('dynamic_dropout_prev_gap')
            if start_epoch >= epochs:
                raise SystemExit(
                    f"--resume checkpoint is already at epoch "
                    f"{start_epoch}/{epochs} - raise --epochs to "
                    f"continue past it.")
            print(f"   Resumed from {resume_from}: continuing at epoch "
                 f"{start_epoch + 1}/{epochs} (best so far: epoch "
                 f"{best_epoch}, {self.select_by} sel_ref="
                 f"{sel_ref if sel_ref is None else f'{sel_ref:.4f}'}). "
                 f"Pass the SAME hyperparameters as the original run - "
                 f"only geometry is verified above, not LR/schedule/loss "
                 f"settings.")
        if dynamic_dropout:
            self._set_dropout(dd_value)
            print(f"   Dynamic dropout: starting at {dd_value:.3f} "
                 f"(range [{dd_min:.3f}, {dd_max:.3f}]), reacting to the "
                 f"val/train loss gap each epoch.")
        guard = DivergenceGuard(self._divergence_patience,
                                self.on_divergence,
                                self._divergence_dampen_factor)
        stop_early = False
        for epoch in range(start_epoch, epochs):
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
            for batch_idx, (cat_x, cont_x, y, w) in enumerate(train_bar):
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
                    total_norm = torch.nn.utils.clip_grad_norm_(
                        self._clip_params, self.grad_clip)
                    scaler.step(optimizer)
                    scaler.update()
                else:
                    outputs = self._pooled_logits(cat_x, cont_x)
                    loss = self._batch_loss(criterion, outputs, y, w,
                                                margin=True)
                    loss.backward()
                    total_norm = torch.nn.utils.clip_grad_norm_(
                        self._clip_params, self.grad_clip)
                    optimizer.step()

                # Gradient diagnostics, gated to every tb_log_every-th
                # step: this is the ONE place in the loop that
                # deliberately re-introduces a device sync (float() on
                # the norms) the accumulate-on-device pattern above
                # exists to avoid - opt-in only, and it's what would
                # have shown directly (rather than requiring offline
                # reasoning) whether the original epoch-8 divergence
                # was the whole network or just the early_attn group
                # blowing up.
                if (tb_writer is not None and tb_log_every > 0
                        and batch_idx % tb_log_every == 0):
                    gstep = epoch * len(train_loader) + batch_idx
                    named_groups = [("backbone", backbone_params)]
                    if attn_params:
                        named_groups.append(("early_attn", attn_params))
                    named_groups.append(("fresh", fresh_params))
                    self._tb_log_grad_step(tb_writer, gstep, total_norm,
                                           named_groups)

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

            # Validation always scored with the MAIN criterion (focal,
            # or AN-full when loss='an_full'), even
            # during warmup - otherwise warmup-epoch val losses (BCE
            # scale, numerically larger) aren't comparable with focal
            # epochs and best-checkpoint selection breaks.
            named_groups = [("backbone", backbone_params)]
            if attn_params:
                named_groups.append(("early_attn", attn_params))
            named_groups.append(("fresh", fresh_params))

            def _eval_with_extras():
                # Weight histograms / sample patches / attention maps
                # must be computed against whatever weights JUST
                # produced this epoch's metrics - called inside the EMA
                # context below when EMA is on, so what's visualized
                # matches what was evaluated (and, if this epoch
                # improves, what gets saved) rather than the raw
                # in-progress training weights.
                m = self.evaluate(val_loader, criterion_focal, epoch, epochs)
                if tb_writer is not None:
                    self._tb_log_epoch_extras(
                        tb_writer, epoch + 1, vis_batch, tb_images,
                        tb_attention, tb_embeddings, tb_embeddings_every,
                        named_groups)
                return m

            if self.ema is not None:
                with self.ema.applied(self.model):
                    metrics = _eval_with_extras()
                    ema_state = {k: v.detach().clone()
                                 for k, v in self.model.state_dict().items()}
            else:
                metrics = _eval_with_extras()
                ema_state = None
            metrics['train_loss'] = tr_loss_sum / max(tr_steps, 1)
            metrics['train_accuracy'] = 100.0 * tr_correct / max(tr_total, 1)
            if dynamic_dropout:
                # Reacts to the TREND (this epoch's gap vs. last epoch's),
                # not the gap's absolute size - a small-but-widening gap
                # and a large-but-shrinking one call for opposite moves,
                # which a threshold on the raw gap can't tell apart. No
                # prior epoch to compare against yet on the very first
                # one (or the epoch right after a resume) - hold and just
                # record it.
                gap = metrics['val_loss'] - metrics['train_loss']
                if dd_prev_gap is not None:
                    if gap > dd_prev_gap:
                        dd_value = min(dd_max, dd_value + dynamic_dropout_step)
                    elif gap < dd_prev_gap:
                        dd_value = max(dd_min, dd_value - dynamic_dropout_step)
                    self._set_dropout(dd_value)
                dd_prev_gap = gap
                metrics['dropout'] = dd_value
            thr = self.best_threshold(tr_logits.numpy(), tr_ys.numpy())
            metrics['threshold'] = thr
            self.threshold = thr
            for src, dst in (("_logits", "tuned_accuracy"),
                             ("_tta_logits", "tuned_tta_accuracy")):
                if src in metrics:
                    ykey = "_y" if src == "_logits" else "_tta_y"
                    metrics[dst] = 100.0 * float(
                        ((metrics[src] >= thr) == (metrics[ykey] == 1)).mean())
            raw_tta_logits = metrics.get('_tta_logits')
            raw_tta_y = metrics.get('_tta_y')
            raw_tta_nlcd = metrics.get('_tta_nlcd')
            metrics = {k: v for k, v in metrics.items()
                       if not k.startswith('_')}
            metrics['epoch'] = epoch + 1
            metrics['lr'] = optimizer.param_groups[-1]['lr']
            metrics['rank_score'] = self.selection_score('rank', metrics)
            status = (f"   Epoch {epoch + 1}/{epochs} | "
                      f"{loss_label}: {metrics['val_loss']:.4f} | "
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
            # UNCONDITIONAL, every epoch (not just on improvement) - a
            # crash between two improving epochs should only cost the
            # epochs since the last one COMPLETED, not force a restart
            # from the last SAVED (best) checkpoint. Separate file from
            # self.save_path (see the resume_from block above for why).
            self._save_resume_state(
                epoch + 1, optimizer, scheduler, scaler, sel_ref,
                best_epoch, best_loss, best_auc, best_strict, best_rank,
                dd_value, dd_prev_gap)
            if metrics_csv:
                self._log_metrics(metrics_csv, metrics)
            if tb_writer is not None:
                step = metrics['epoch']
                for tag, key in (("Loss/train", "train_loss"),
                                 ("Loss/val", "val_loss"),
                                 ("Accuracy/train", "train_accuracy"),
                                 ("Accuracy/val", "accuracy"),
                                 ("Accuracy/tuned_tta", "tuned_tta_accuracy"),
                                 ("AUC/val", "auc"), ("AUC/tta", "tta_auc"),
                                 ("AP/val", "ap"), ("AP/tta", "tta_ap"),
                                 ("Rank/score", "rank_score"),
                                 ("Strict/accuracy", "strict_accuracy"),
                                 ("Strict/hedged_pct", "hedged_pct"),
                                 ("Diagnostics/logit_std", "logit_std"),
                                 ("Diagnostics/logit_mean", "logit_mean"),
                                 ("Diagnostics/pred_pos_pct", "pred_pos_pct"),
                                 ("Regularization/dropout", "dropout")):
                    if key in metrics:
                        tb_writer.add_scalar(tag, metrics[key], step)
                if dynamic_dropout:
                    tb_writer.add_scalar("Regularization/embed_dropout",
                                         self.model.embed_dropout, step)
                    tb_writer.add_scalar("Regularization/val_train_gap",
                                         dd_prev_gap, step)
                tb_writer.add_scalar(f"Selection/{self.select_by}_score",
                                     sel, step)
                for name, g in zip(group_names, optimizer.param_groups):
                    tb_writer.add_scalar(f"LR/{name}", g['lr'], step)
                if raw_tta_logits is not None and len(raw_tta_logits):
                    # NaN/Inf-safe (see _tb_log_grad_step): a diverging
                    # run can hand back non-finite logits, and
                    # add_histogram crashes outright on an all-non-
                    # finite tensor rather than just logging it oddly.
                    finite = np.isfinite(raw_tta_logits)
                    n_bad = int(len(raw_tta_logits) - finite.sum())
                    if n_bad:
                        tb_writer.add_text(
                            "events/nonfinite_grad",
                            f"epoch {step}: {n_bad}/{len(raw_tta_logits)} "
                            f"non-finite (NaN/Inf) validation logits - "
                            f"the run is likely diverging. Histogram/PR "
                            f"curve below use the finite remainder only.",
                            step)
                    fl, fy = raw_tta_logits[finite], raw_tta_y[finite]
                    if len(fl):
                        tb_writer.add_histogram("Diagnostics/val_logits",
                                                fl, step)
                        # Full precision/recall-vs-threshold curve, not
                        # just the single accuracy number at one
                        # operating point - cheap (numpy only, no GPU)
                        # since evaluate() already computed both arrays.
                        tb_writer.add_pr_curve(
                            "PR/val_tta", fy, 1.0 / (1.0 + np.exp(-fl)),
                            step)
                if raw_tta_nlcd is not None:
                    self._tb_log_class_breakdown(
                        tb_writer, step, raw_tta_logits, raw_tta_y,
                        raw_tta_nlcd)
                if improved:
                    tb_writer.add_text(
                        "events/checkpoint",
                        f"Saved at epoch {step} ({self.select_by} "
                        f"score={sel:.4f})", step)

            if guard.update(metrics.get('strict_accuracy', float('-inf')),
                            metrics['tta_auc'], metrics['ap']):
                streak_epochs = f"epochs {epoch - self._divergence_patience + 2}-{epoch + 1}"
                if self.on_divergence == 'warn':
                    msg = (f"   [!] DIVERGENCE: strict accuracy rose while "
                          f"AUC and AP both fell for "
                          f"{self._divergence_patience} straight epochs "
                          f"({streak_epochs}) - the model may be buying "
                          f"confidence at ranking's expense.")
                elif self.on_divergence == 'dampen':
                    self._m_pos *= self._divergence_dampen_factor
                    self._m_neg *= self._divergence_dampen_factor
                    msg = (f"   [!] DIVERGENCE over {streak_epochs} - "
                          f"DAMPENING margins to +{self._m_pos:.3f}/"
                          f"{self._m_neg:.3f} (x{self._divergence_dampen_factor}) "
                          f"to ease off the strict objective.")
                elif self.on_divergence == 'stop':
                    msg = (f"   [!] DIVERGENCE over {streak_epochs} - "
                          f"STOPPING at epoch {epoch + 1}/{epochs}. Best "
                          f"checkpoint on disk is unaffected.")
                    stop_early = True
                print(msg)
                if tb_writer is not None:
                    tb_writer.add_text("events/divergence", msg,
                                       metrics['epoch'])
            if stop_early:
                break

        print(f"\nTraining finished{' (stopped on divergence)' if stop_early else ''}."
             f" Best {loss_label}: {best_loss:.4f} | "
             f"Best TTA AUC: {best_auc:.4f} | "
             f"Best rank: {best_rank:.4f} | "
             f"Best strict acc: {best_strict:.2f}% "
             f"(selection metric: {self.select_by}"
             f"{f', min delta {self.select_min_delta:g}' if self.select_min_delta else ''}"
             f" -> saved checkpoint is epoch {best_epoch})"
             f"{f' | divergence triggers: {guard.n_triggers}' if guard.n_triggers else ''}")
        if tb_writer is not None and tb_embeddings:
            self._tb_log_embeddings(tb_writer, step=best_epoch)
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

    @staticmethod
    def _tb_log_grad_step(tb_writer, step, total_norm, named_groups):
        """Gradient diagnostics for one training step: the pre-clip
        total norm (clip_grad_norm_'s own return value - no extra
        compute) plus, per LR group, its own gradient norm and a
        histogram. This is the resolution that would have told "the
        whole network is diverging" from "one LR group (e.g.
        early_attn) is diverging while the rest is fine" directly,
        instead of requiring after-the-fact reasoning from val
        metrics alone.

        NaN/Inf-safe: a warm-restart LR spike (or any other instability)
        can genuinely blow a group's gradients up to non-finite values -
        exactly the event this instrumentation exists to catch - and
        add_histogram crashes outright on an all-non-finite tensor
        ("the histogram is empty"), which took down a live 150-epoch
        run. Non-finite entries are filtered before norm/histogram
        (computed on the finite remainder, if any) and reported as a
        text event instead of a crash - a surfaced warning, not a
        silent drop, since non-finite gradients are real information."""
        tb_writer.add_scalar("Grad/total_norm_preclip", float(total_norm),
                             step)
        for name, params in named_groups:
            grads = [p.grad.detach() for p in params if p.grad is not None]
            if not grads:
                continue
            flat = torch.cat([g.reshape(-1) for g in grads])
            finite = torch.isfinite(flat)
            n_bad = int(flat.numel() - int(finite.sum()))
            if n_bad:
                tb_writer.add_text(
                    "events/nonfinite_grad",
                    f"step {step}: {n_bad}/{flat.numel()} non-finite "
                    f"(NaN/Inf) gradient values in '{name}' - likely an "
                    f"LR-spike instability (e.g. a warm restart). "
                    f"Norm/histogram below are computed on the finite "
                    f"remainder only.", step)
                flat = flat[finite]
            if flat.numel() == 0:
                continue
            tb_writer.add_scalar(f"Grad/norm_{name}", float(flat.norm()),
                                 step)
            tb_writer.add_histogram(f"Grad/hist_{name}", flat, step)

    @staticmethod
    def _tb_log_class_breakdown(tb_writer, step, logits, y, nlcd_codes,
                                min_count=10):
        """Per-NLCD-class val mean score / AUC, every epoch - the live
        counterpart to diagnose_wetland.py's per-class analysis, which
        previously required a separate offline pass after training
        finished. A class-specific shortcut emerging (one class's mean
        score pulling away from the rest, or its own AUC diverging from
        the overall trend) is now visible as it happens. Codes with
        fewer than min_count val points are skipped as too noisy to
        read; <=0 is nodata/padding, always skipped."""
        import numpy as np
        probs = 1.0 / (1.0 + np.exp(-logits))
        for code in sorted(set(int(c) for c in nlcd_codes)):
            if code <= 0:
                continue
            m = nlcd_codes == code
            if m.sum() < min_count:
                continue
            name = NLCD_NAMES.get(code, f"class_{code}").replace(
                ' ', '_').replace('/', '-')
            tb_writer.add_scalar(f"Class/mean_score/{name}",
                                 float(probs[m].mean()), step)
            yy = y[m]
            if len(np.unique(yy)) > 1:
                tb_writer.add_scalar(f"Class/auc/{name}",
                                     roc_auc(logits[m], yy), step)

    @staticmethod
    def _class_map_rgb(idx_map, cmap_name='tab20'):
        """(B,1,H,W) integer class-index map -> (B,3,H,W) RGB float in
        [0,1] via a FIXED categorical palette (same color for the same
        class code across every sample/epoch - unlike a per-sample
        min-max normalization, which would repaint colors depending on
        which classes happen to appear in one patch, making two crops
        visually incomparable). Index 0 (every categorical feature's
        padding_idx) always renders black. High-vocab features (e.g.
        evt/sclass, thousands of codes) wrap the 20-color palette, so
        colors stop being globally unique past ~20 distinct codes in
        view at once - still shows boundary/patch structure, just not
        a reliable color-to-class legend at that point."""
        import numpy as np
        import matplotlib
        # matplotlib.cm.get_cmap() was removed in 3.9+; colormaps[] is
        # the replacement, still current back through 3.7.
        palette = matplotlib.colormaps[cmap_name]
        idx = idx_map.squeeze(1).detach().cpu().numpy()
        rgb = np.zeros((*idx.shape, 3), dtype=np.float32)
        for v in np.unique(idx):
            if v == 0:
                continue
            rgb[idx == v] = palette((int(v) % 20) / 20.0)[:3]
        return torch.from_numpy(rgb).permute(0, 3, 1, 2)

    def _tb_log_epoch_extras(self, tb_writer, step, vis_batch, tb_images,
                             tb_attention, tb_embeddings,
                             tb_embeddings_every, named_groups):
        """Once-per-epoch diagnostics beyond the scalar metrics: weight
        histograms per LR group; a grid of sample validation patches
        per continuous AND categorical feature; the model's own
        pre-pool spatial logit map (and attn-pool score map, if
        pool='attn') for those same patches; the dual-branch head's own
        feature-activation and pooling maps, if active; and - if
        early_attn is active - its attention weights, both per-head at
        the patch center and head-averaged at several patch positions;
        plus a periodic embedding-table snapshot. Called from inside
        fit()'s EMA context when EMA is on, so what's visualized is the
        SAME weights that just produced this epoch's metrics (and, if
        this epoch improves, get saved), not the raw in-progress
        training weights EMA is smoothing over."""
        for name, params in named_groups:
            flat = torch.cat([p.detach().reshape(-1) for p in params])
            # NaN/Inf-safe (see _tb_log_grad_step): a NaN gradient can
            # propagate into the weights themselves via the optimizer
            # step, and add_histogram crashes outright on an all-non-
            # finite tensor.
            finite = torch.isfinite(flat)
            n_bad = int(flat.numel() - int(finite.sum()))
            if n_bad:
                tb_writer.add_text(
                    "events/nonfinite_grad",
                    f"step {step}: {n_bad}/{flat.numel()} non-finite "
                    f"(NaN/Inf) WEIGHT values in '{name}' - gradient "
                    f"corruption has reached the weights themselves. "
                    f"This checkpoint is likely unusable.", step)
                flat = flat[finite]
            if flat.numel() == 0:
                continue
            tb_writer.add_histogram(f"Weights/{name}", flat, step)
        if (tb_embeddings and tb_embeddings_every > 0
                and step % tb_embeddings_every == 0):
            self._tb_log_embedding_tables(tb_writer, step,
                                          self.model.state_dict())
        if vis_batch is None:
            return
        import torchvision
        cat_x, cont_x, _, _ = vis_batch
        cat_x = cat_x.to(self.device)
        cont_x = cont_x.to(self.device, memory_format=self._mem_fmt)
        n = min(8, cont_x.shape[0])
        cat_x, cont_x = cat_x[:n], cont_x[:n]

        def norm01(m):
            lo = m.amin(dim=(2, 3), keepdim=True)
            hi = m.amax(dim=(2, 3), keepdim=True)
            return ((m - lo) / (hi - lo).clamp_min(1e-6)).float().cpu()

        with torch.no_grad():
            if tb_images:
                for ci, fname in enumerate(self.cont_features):
                    grid = torchvision.utils.make_grid(
                        norm01(cont_x[:, ci:ci + 1]), nrow=n)
                    tb_writer.add_image(f"Patches/{fname}", grid, step)
                for ci, fname in enumerate(self.cat_features):
                    grid = torchvision.utils.make_grid(
                        self._class_map_rgb(cat_x[:, ci:ci + 1]), nrow=n)
                    tb_writer.add_image(f"Patches/{fname}", grid, step)
                embedded = self.model.embed(cat_x, cont_x)
                spatial = self.model.trunk(embedded)
                tb_writer.add_image(
                    "Patches/logit_map",
                    torchvision.utils.make_grid(norm01(spatial[:, :1]),
                                                nrow=n), step)
                if spatial.shape[1] > 1:      # pool='attn' score channel
                    b, _, h, w = spatial.shape
                    sm = torch.softmax(
                        spatial[:, 1:2].reshape(b, 1, h * w), dim=2
                    ).reshape(b, 1, h, w)
                    tb_writer.add_image(
                        "Patches/attn_pool_map",
                        torchvision.utils.make_grid(norm01(sm), nrow=n),
                        step)
                if self.model.dual_branch != 'off':
                    # Branch B's own multi-channel feature map has no
                    # single natural image - mean absolute activation
                    # across channels is the standard "where is this
                    # branch active" summary. Its pooling map is the
                    # Branch-A attn_pool_map's counterpart (content-
                    # dependent for pool='attn', one shared fixed map
                    # otherwise - see DualSpatialBranch.pooling_map).
                    fmap = self.model.spatial_branch.feature_map(embedded)
                    act = fmap.abs().mean(dim=1, keepdim=True)
                    tb_writer.add_image(
                        "Patches/branchB_activation",
                        torchvision.utils.make_grid(norm01(act), nrow=n),
                        step)
                    pool_map = self.model.spatial_branch.pooling_map(
                        embedded)
                    if pool_map.shape[0] == 1:
                        pool_map = pool_map.expand(n, -1, -1, -1)
                    tb_writer.add_image(
                        "Patches/branchB_pool_map",
                        torchvision.utils.make_grid(norm01(pool_map),
                                                    nrow=n), step)
            if tb_attention and self.model.early_attn is not None:
                na = min(4, n)
                result = self.model.attention_diagnostics(cat_x[:na],
                                                           cont_x[:na])
                if result is not None:
                    w_attn, (h, wd, kh, kw) = result
                    num_heads = w_attn.shape[1]
                    # Five fixed query positions (center + quadrant
                    # midpoints) so off-center attention behavior is
                    # visible, not just the patch center - each
                    # head-averaged, arranged one row per sample.
                    positions = [(0.5, 0.5), (0.25, 0.25), (0.25, 0.75),
                                (0.75, 0.25), (0.75, 0.75)]
                    idxs = [int(round(py * (h - 1))) * wd
                           + int(round(px * (wd - 1)))
                           for py, px in positions]
                    center = idxs[0]
                    pos_maps = torch.stack(
                        [w_attn[:, :, i, :].mean(dim=1) for i in idxs],
                        dim=1)                    # (na, 5, kh*kw)
                    pos_maps = pos_maps.reshape(na * len(idxs), 1, kh, kw)
                    tb_writer.add_image(
                        "Patches/attn_query_grid",
                        torchvision.utils.make_grid(norm01(pos_maps),
                                                    nrow=len(idxs)), step)
                    # Same center query, but one tile per HEAD instead
                    # of averaged - a head that specializes (local vs.
                    # global, directional) is invisible in the average.
                    head_maps = w_attn[:, :, center, :].reshape(
                        na, num_heads, kh, kw
                    ).reshape(na * num_heads, 1, kh, kw)
                    tb_writer.add_image(
                        "Patches/attn_center_per_head",
                        torchvision.utils.make_grid(norm01(head_maps),
                                                    nrow=num_heads), step)
                    # The original single head-averaged center tile,
                    # kept as-is for a quick low-noise glance.
                    center_map = pos_maps[0::len(idxs)]
                    tb_writer.add_image(
                        "Patches/attn_center_query",
                        torchvision.utils.make_grid(norm01(center_map),
                                                    nrow=na), step)

    @staticmethod
    def _tb_log_embedding_tables(tb_writer, step, state_dict,
                                 cat_features=None):
        """Shared by the periodic (live/EMA weights, from
        _tb_log_epoch_extras) and end-of-training (saved checkpoint,
        from _tb_log_embeddings) snapshots: log each categorical
        feature's embedding table under ONE tag per feature with `step`
        as the TensorBoard projector's slider, so a single tag's
        history across steps is browsable as "how did this class's
        representation move over training" instead of only ever
        showing the final state."""
        cat_features = (cat_features if cat_features is not None
                        else [k[len("embeddings."):-len(".weight")]
                              for k in state_dict
                              if k.startswith("embeddings.")
                              and k.endswith(".weight")])
        for name in cat_features:
            key = f"embeddings.{name}.weight"
            if key not in state_dict:
                continue
            w = state_dict[key]
            tb_writer.add_embedding(w, metadata=[str(i) for i in
                                                 range(w.shape[0])],
                                    tag=f"Embedding/{name}",
                                    global_step=step)

    def _tb_log_embeddings(self, tb_writer, step=0):
        """Categorical feature embedding tables from the SAVED (best)
        checkpoint - not necessarily the model's current live weights,
        since checkpoint selection may have kept an earlier epoch."""
        state, _ = self.unwrap_checkpoint(
            torch.load(self.save_path, map_location='cpu',
                      weights_only=True))
        first = next(iter(state))
        if first.startswith("_orig_mod."):
            state = {k[len("_orig_mod."):]: v for k, v in state.items()}
        self._tb_log_embedding_tables(tb_writer, step, state,
                                      self.cat_features)

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
        # Center-pixel NLCD class per sample, gathered straight from the
        # SAME tensor already fed to the model (no extra raster I/O,
        # unlike diagnose_wetland.py's disk re-read) - lets fit() log a
        # live per-class score breakdown every epoch instead of that
        # analysis only being available as a separate offline pass
        # after training finishes. None when the model wasn't trained
        # with 'nlcd' at all.
        nlcd_idx = (self.cat_features.index('nlcd')
                   if 'nlcd' in self.cat_features else None)
        all_nlcd = [] if nlcd_idx is not None else None
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
                if all_nlcd is not None:
                    hh, ww = cat_x.shape[-2:]
                    all_nlcd.append(
                        cat_x[:, nlcd_idx, hh // 2, ww // 2].cpu())
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
        nlcd_codes = (torch.cat(all_nlcd).numpy()
                     if all_nlcd is not None else None)
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
            if nlcd_codes is not None:
                # One code per point: the 4 stored rotations share a
                # label by construction (asserted above), and rotating
                # a square patch about its own center maps that center
                # to itself, so all 4 rotations' center-pixel reads are
                # the same land-cover cell in practice - take the first
                # rather than re-derive an invariance proof here.
                out["_tta_nlcd"] = nlcd_codes.reshape(-1, tta_group)[:, 0]
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
