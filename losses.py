"""
losses.py

FocalLoss preserved from the original project - behavior unchanged.
(Class default alpha=0.50 as in the original; the trainer passes
alpha=0.25 explicitly, also as in the original train.py.)
"""
import torch
import torch.nn as nn
import torch.nn.functional as F


class FocalLoss(nn.Module):
    def __init__(self, alpha=0.50, gamma=2.0, reduction='mean'):
        super(FocalLoss, self).__init__()
        self.alpha = alpha
        self.gamma = gamma
        self.reduction = reduction

    def forward(self, inputs, targets):
        BCE_loss = F.binary_cross_entropy_with_logits(inputs, targets,
                                                      reduction='none')
        pt = torch.exp(-BCE_loss)
        # `> 0.5`, not `== 1.0`: with label smoothing the positive target
        # is 1-eps/2, which an equality test would silently classify as
        # the negative class and invert the alpha weighting.
        alpha_factor = torch.where(targets > 0.5, self.alpha, 1.0 - self.alpha)
        F_loss = alpha_factor * (1 - pt) ** self.gamma * BCE_loss
        if self.reduction == 'mean':
            return torch.mean(F_loss)
        elif self.reduction == 'sum':
            return torch.sum(F_loss)
        else:
            return F_loss


class ANFullLoss(nn.Module):
    """L_AN-full - the "full assume-negative" loss of Cole et al.,
    "Spatial Implicit Neural Representations for Global-Scale Species
    Mapping" (ICML 2023), reduced to this project's single-species
    presence/background setting.

    In the multi-species original, each presence record supervises the
    observed species as positive (weighted lambda) and EVERY other
    species as negative at that location, plus every species as
    negative at a uniformly random background location - negatives are
    ASSUMED, never verified, and lambda is what keeps the (rare,
    trusted) positive signal from being drowned by (abundant, noisy)
    assumed negatives. With one species the per-location terms collapse
    and what remains is:

        loss = -( lambda * y * log sigmoid(z) + (1-y) * log sigmoid(-z) )

    i.e. lambda-weighted BCE on logits, with the random-background half
    of the objective supplied by the data pipeline (train.py
    --an-background samples uniform in-raster locations as assumed
    negatives). At lambda=1 this is exactly BCEWithLogits. Computed via
    logsigmoid, so it is finite at any logit (the reference
    implementation clamps probabilities instead).

    Accepts soft targets (label smoothing composes: y=1-eps/2 splits
    the sample between the weighted-positive and negative terms)."""

    def __init__(self, pos_weight=1.0, reduction='mean'):
        super().__init__()
        self.pos_weight = float(pos_weight)
        self.reduction = reduction

    def forward(self, inputs, targets):
        loss = -(self.pos_weight * targets * F.logsigmoid(inputs)
                 + (1.0 - targets) * F.logsigmoid(-inputs))
        if self.reduction == 'mean':
            return torch.mean(loss)
        elif self.reduction == 'sum':
            return torch.sum(loss)
        return loss

