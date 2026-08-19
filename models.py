"""
models.py

GrouseResNet refactored for DYNAMIC GEOMETRY: the network's input side
(embedding layers, clamp ranges, channel ordering, stem width) is built
from FEATURE_SPEC + whichever features are actually available, instead
of four hardcoded embedding attributes and positional clamps. Add or
remove a feature = edit FEATURE_SPEC (or just have the raster present/
absent on disk); no model-code changes.

Everything architectural is preserved from the original:
  - ImageNet-pretrained ResNet-18 backbone
  - layer3[0] and layer4[0] strides flattened to 1 (holds 16x16 spatial
    resolution through the deep stages)
  - CBAM attention after every ResNet stage
  - custom wide-input stem conv (trained from scratch), pretrained
    bn1/relu/maxpool reused
  - 1x1 conv_out head producing a SPATIAL logit map; no avgpool in
    forward() - the trainer mean-pools logits, exactly as before
"""
import torch
import torch.nn as nn
from torchvision import models

from blocks import CBAM


class EarlyAttentionBlock(nn.Module):
    """Standard pre-norm transformer block (multi-head self-attention +
    MLP, both with residuals) operating on a spatial feature map as a
    sequence of per-pixel tokens.

    WHY THIS SITS WHERE IT DOES: by the final pooling stage (where the
    existing pool='attn' mode already applies attention), stacked
    convolution+downsampling has reduced the map to an 8x8 grid - each
    token already an average over an 8x8 pixel block (240m on the
    ground at this project's 30m/px, 64px patches). Whatever fine-
    grained arrangement of individual pixel-level features existed has
    already been smeared together by the time any attention runs.
    Placed here (after layer1, which never downsamples on its own, with
    the stem maxpool's stride flattened via keep_early_resolution), it
    sees a 32x32 grid - each token still a single original 30m pixel -
    so genuine pixel-level spatial relationships are available to
    attend over before any pooling has destroyed them.

    kv_stride=1: full self-attention (every token attends to every
      other token - expensive, O(HW)^2, but keeps 100% fidelity).
    kv_stride>1: keys/values are downsampled by a strided conv first
      (queries stay full-resolution) - every fine pixel still attends
      OUT to the whole map, just against a coarser summary of it,
      trading some fidelity for roughly kv_stride^2 less attention
      compute."""

    def __init__(self, channels, num_heads=4, kv_stride=1):
        super().__init__()
        self.kv_stride = int(kv_stride)
        self.norm1 = nn.LayerNorm(channels)
        self.attn = nn.MultiheadAttention(channels, num_heads,
                                          batch_first=True)
        if self.kv_stride > 1:
            self.kv_proj = nn.Conv2d(channels, channels,
                                     kernel_size=self.kv_stride,
                                     stride=self.kv_stride)
        self.norm2 = nn.LayerNorm(channels)
        self.mlp = nn.Sequential(
            nn.Linear(channels, channels * 4), nn.GELU(),
            nn.Linear(channels * 4, channels))

    def forward(self, x):
        b, c, h, w = x.shape
        q_tokens = x.flatten(2).transpose(1, 2)           # (B, HW, C)
        q_normed = self.norm1(q_tokens)
        if self.kv_stride > 1:
            kv_map = self.kv_proj(x)                       # downsample
            kv_tokens = kv_map.flatten(2).transpose(1, 2)
            kv_normed = self.norm1(kv_tokens)
        else:
            kv_normed = q_normed
        attn_out, _ = self.attn(q_normed, kv_normed, kv_normed)
        x_tokens = q_tokens + attn_out
        x_tokens = x_tokens + self.mlp(self.norm2(x_tokens))
        return x_tokens.transpose(1, 2).reshape(b, c, h, w)

# ==========================================
# FEATURE SPEC - single source of truth for model input geometry.
# kind: 'categorical' -> nn.Embedding(vocab, dim, padding_idx=0), values
#        clamped to [0, vocab-1] (so nodata/-1 sentinels map to padding)
# kind: 'continuous'  -> one input channel, values divided by 'scale'
# Order here fixes channel order; only features actually requested at
# construction are instantiated.
# ==========================================
FEATURE_SPEC = {
    "evt":    {"kind": "categorical", "vocab": 10000, "dim": 32},
    "evh":    {"kind": "categorical", "vocab": 300,   "dim": 16},
    "evc":    {"kind": "categorical", "vocab": 300,   "dim": 16},
    "sclass": {"kind": "categorical", "vocab": 300,   "dim": 16},
    # FDist codes run into the low thousands (year/type/severity
    # composites); vocab sized generously - embedding memory is trivial.
    # FDIST_NONE=-1 clamps to 0 = padding_idx, i.e. "no disturbance"
    # is represented as the padding vector.
    "fdist":  {"kind": "categorical", "vocab": 10000, "dim": 16},
    # CH is height in coded units (~0-510), CC is percent (0-100);
    # scale brings both to roughly unit range.
    "ch":     {"kind": "continuous", "scale": 100.0},
    "cc":     {"kind": "continuous", "scale": 100.0},
}


def split_features(feature_names, spec=None):
    """Partition requested features into (categorical, continuous) lists,
    preserving spec order. Unknown names raise immediately."""
    spec = spec or FEATURE_SPEC
    unknown = [f for f in feature_names if f not in spec]
    if unknown:
        raise ValueError(f"Features not in FEATURE_SPEC: {unknown}. "
                         f"Add them to the spec in models.py.")
    ordered = [f for f in spec if f in feature_names]
    cat = [f for f in ordered if spec[f]["kind"] == "categorical"]
    cont = [f for f in ordered if spec[f]["kind"] == "continuous"]
    return cat, cont


class GrouseResNet(nn.Module):
    def __init__(self, cat_features, cont_features, spec=None,
                 pretrained=True, pool='mean', dropout=0.0,
                 embed_dropout=0.0, center_skip=False,
                 keep_early_resolution=False, early_attn=False,
                 early_attn_heads=4, early_attn_kv_stride=1):
        """cat_features / cont_features: ordered feature-name lists (from
        split_features). Geometry is derived from them + the spec.

        pool: how the spatial logit map collapses to one logit per sample.
          'mean'   - plain average over every cell (the original).
          'center' - average of the 2x2 cells covering the patch center.
          'gauss'  - center-weighted average, sigma = 1/4 of the map.
          'attn'   - learned softmax attention over cells.
        The label describes the CENTER point, but a 64x64 patch at 30 m is
        ~1.9 km across, so 'mean' spreads one point's label over ~3.7 km2
        of mostly irrelevant ground and gives the center cell 1/64 of the
        vote. A naive-Bayes model on the center pixel's codes alone scores
        val AUC 0.865 on this data, so that dilution is expensive."""
        super(GrouseResNet, self).__init__()
        spec = spec or FEATURE_SPEC
        self.pool_mode = pool
        self.cat_features = list(cat_features)
        self.cont_features = list(cont_features)
        self._vocab = {f: spec[f]["vocab"] for f in self.cat_features}

        # Dynamic embedding bank - one entry per categorical feature.
        self.embeddings = nn.ModuleDict({
            f: nn.Embedding(spec[f]["vocab"], spec[f]["dim"], padding_idx=0)
            for f in self.cat_features
        })

        weights = models.ResNet18_Weights.IMAGENET1K_V1 if pretrained else None
        resnet = models.resnet18(weights=weights)

        # Hold spatial resolution: flatten layer3/layer4 entry strides
        # (and their residual-shortcut downsamples) to 1, as original.
        resnet.layer3[0].conv1.stride = (1, 1)
        resnet.layer3[0].downsample[0].stride = (1, 1)
        resnet.layer4[0].conv1.stride = (1, 1)
        resnet.layer4[0].downsample[0].stride = (1, 1)

        # Stem width derived from the live feature set.
        total_in_channels = (sum(spec[f]["dim"] for f in self.cat_features)
                             + len(self.cont_features))
        self.total_in_channels = total_in_channels
        self.conv1 = nn.Conv2d(total_in_channels, 64, kernel_size=7,
                               stride=2, padding=3, bias=False)
        self.bn1 = resnet.bn1
        self.relu = resnet.relu
        self.maxpool = resnet.maxpool
        self.keep_early_resolution = bool(keep_early_resolution)
        if self.keep_early_resolution:
            # Stem conv already halves 64->32; the stock maxpool would
            # halve again to 16. Flattening its stride to 1 (kernel=3,
            # padding=1 already preserves size at stride 1) keeps the
            # map at 32x32 through layer1 - one 30m pixel per token,
            # for early_attn to operate on before layer2's stride-2
            # downsamples it further.
            self.maxpool.stride = 1

        self.layer1 = resnet.layer1
        self.cbam1 = CBAM(64)
        self.early_attn = (
            EarlyAttentionBlock(64, num_heads=early_attn_heads,
                               kv_stride=early_attn_kv_stride)
            if early_attn else None)
        self._early_attn_kv_stride = int(early_attn_kv_stride)
        if early_attn and not self.keep_early_resolution:
            print("   [note] early_attn=True without "
                 "keep_early_resolution=True: attention runs on the "
                 "default 16x16 grid (60m/token), not the intended "
                 "32x32 (30m/token) - pass both together for full "
                 "pixel-level attention.")
        self.layer2 = resnet.layer2
        self.cbam2 = CBAM(128)
        self.layer3 = resnet.layer3
        self.cbam3 = CBAM(256)
        self.layer4 = resnet.layer4
        self.cbam4 = CBAM(512)

        self.avgpool = resnet.avgpool   # kept for parity; unused in forward
        # Dropout on the 512-d feature map before the head. ~12.7k
        # training points against ~12M parameters overfits hard, and this
        # is the cheapest place to fight it that costs no features.
        self.drop = nn.Dropout2d(dropout) if dropout > 0 else nn.Identity()
        self.embed_dropout = float(embed_dropout)
        # conv_out emits the logit map, plus an attention score map when
        # pool='attn'.
        self.conv_out = nn.Conv2d(512, 2 if pool == 'attn' else 1,
                                  kernel_size=1)
        # Center-pixel skip path ("wide & deep"). The 7x7 stride-2 stem
        # blends the labelled center pixel into its neighbours on the very
        # first op, so its exact codes are never available downstream on
        # their own - yet a naive-Bayes model on those codes alone scores
        # val AUC 0.865, which is the whole CNN's score. This gives the
        # head the center vector directly and leaves the convolutional
        # trunk to contribute context on top of it.
        self.center_skip = bool(center_skip)
        if self.center_skip:
            self.center_head = nn.Sequential(
                nn.Linear(total_in_channels, 128), nn.ReLU(),
                nn.Dropout(dropout), nn.Linear(128, 1))

    def embed(self, cat_x, cont_x):
        """Stack every feature into the (B, C, H, W) input tensor: one
        embedding block per categorical feature, one raw channel per
        continuous one."""
        parts = []
        for k, name in enumerate(self.cat_features):
            idx = torch.clamp(cat_x[:, k], 0, self._vocab[name] - 1)
            e = self.embeddings[name](idx).permute(0, 3, 1, 2)
            if self.training and self.embed_dropout > 0:
                # Drop whole feature planes, not scattered activations:
                # that forces the head to survive without any single
                # categorical layer instead of leaning entirely on EVT.
                keep = (torch.rand(e.shape[0], 1, 1, 1, device=e.device)
                        >= self.embed_dropout).float()
                e = e * keep / (1.0 - self.embed_dropout)
            parts.append(e)
        if len(self.cont_features) > 0:
            parts.append(cont_x)
        return torch.cat(parts, dim=1)

    def forward(self, cat_x, cont_x):
        """cat_x: (B, n_cat, H, W) integer codes in spec order.
        cont_x: (B, n_cont, H, W) floats (already scaled by the dataset).
        Returns the SPATIAL logit map (B, 1, H', W') - the trainer
        pools it, as in the original."""
        return self.trunk(self.embed(cat_x, cont_x))

    def trunk(self, x):
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu(x)
        x = self.maxpool(x)

        x = self.layer1(x)
        x = self.cbam1(x)
        if self.early_attn is not None:
            x = self.early_attn(x)
        x = self.layer2(x)
        x = self.cbam2(x)
        x = self.layer3(x)
        x = self.cbam3(x)
        x = self.layer4(x)
        x = self.cbam4(x)

        return self.conv_out(self.drop(x))

    def logits(self, cat_x, cont_x):
        """The single scalar logit per sample that training optimizes:
        pooled trunk output, plus the center-pixel skip when enabled."""
        x = self.embed(cat_x, cont_x)
        out = self.pool_logits(self.trunk(x))
        if self.center_skip:
            out = out + self.center_head(self._center_vector(cat_x, cont_x, x))
        return out

    def _center_vector(self, cat_x, cont_x, x):
        """The 2x2 center average of the embedded input - a 2x2 window,
        so the path is robust to the exact parity of the patch size
        rather than keyed to one pixel.

        Taken by embedding the 2x2 center of the INPUTS rather than
        slicing the full embedded tensor. The two are exactly equal
        (embed() is pointwise in space: embed(x)[..., r, c] is
        embed(x[..., r, c])), but slicing x makes autograd allocate and
        zero-fill a whole (B, 98, 64, 64) gradient buffer on every step
        just to deposit four pixels into it - measured at 7% of all GPU
        time. Embedding four pixels directly costs nothing.
        """
        _, _, h, w = x.shape
        r0, c0 = (h - 1) // 2, (w - 1) // 2
        if self.training and self.embed_dropout > 0:
            # embed() draws a fresh dropout mask per call, so with
            # embed_dropout on, a second call would drop different
            # feature planes than the trunk saw. Reuse the trunk's own
            # tensor to keep the two paths consistent.
            return x[:, :, r0:r0 + 2, c0:c0 + 2].mean(dim=(2, 3))
        return self.embed(cat_x[:, :, r0:r0 + 2, c0:c0 + 2],
                          cont_x[:, :, r0:r0 + 2, c0:c0 + 2]).mean(dim=(2, 3))

    def pool_logits(self, out_map):
        """Collapse the spatial map from forward() to (B, 1) logits."""
        if self.pool_mode == 'attn':
            logit, score = out_map[:, :1], out_map[:, 1:]
            b, _, h, w = logit.shape
            a = torch.softmax(score.reshape(b, 1, h * w), dim=2)
            return (a * logit.reshape(b, 1, h * w)).sum(dim=2)
        if self.pool_mode == 'mean':
            return out_map.mean(dim=(2, 3))
        b, _, h, w = out_map.shape
        if self.pool_mode == 'center':
            r0, r1 = (h - 1) // 2, h // 2 + 1
            c0, c1 = (w - 1) // 2, w // 2 + 1
            return out_map[:, :, r0:r1, c0:c1].mean(dim=(2, 3))
        if self.pool_mode == 'gauss':
            if getattr(self, '_gauss_hw', None) != (h, w):
                yy = torch.arange(h, dtype=torch.float32) - (h - 1) / 2.0
                xx = torch.arange(w, dtype=torch.float32) - (w - 1) / 2.0
                sigma = max(h, w) / 4.0
                g = torch.exp(-(yy[:, None] ** 2 + xx[None, :] ** 2)
                              / (2 * sigma ** 2))
                self.register_buffer('_gauss_w', (g / g.sum()).to(
                    out_map.device), persistent=False)
                self._gauss_hw = (h, w)
            w_ = self._gauss_w.to(out_map.dtype)
            return (out_map * w_).sum(dim=(2, 3))
        raise ValueError(f"Unknown pool mode {self.pool_mode!r}")
