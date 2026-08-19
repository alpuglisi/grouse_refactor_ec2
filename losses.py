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

