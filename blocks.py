"""
blocks.py

CBAM (Convolutional Block Attention Module) - REFERENCE IMPLEMENTATION.
The original project's blocks.py was never received, so this is the
standard published formulation (Woo et al. 2018): channel attention
(shared MLP over avg+max pooled descriptors) followed by spatial
attention (7x7 conv over channel-wise avg+max maps). If your original
CBAM differed (reduction ratio, kernel size), adjust the two defaults
below - the model class passes only the channel count, matching how
models.py called CBAM(64)/CBAM(128)/CBAM(256)/CBAM(512).
"""
import torch
import torch.nn as nn


class ChannelAttention(nn.Module):
    def __init__(self, channels, reduction=16):
        super().__init__()
        self.avg_pool = nn.AdaptiveAvgPool2d(1)
        self.max_pool = nn.AdaptiveMaxPool2d(1)
        self.mlp = nn.Sequential(
            nn.Conv2d(channels, channels // reduction, kernel_size=1, bias=False),
            nn.ReLU(inplace=True),
            nn.Conv2d(channels // reduction, channels, kernel_size=1, bias=False),
        )
        self.sigmoid = nn.Sigmoid()

    def forward(self, x):
        attn = self.mlp(self.avg_pool(x)) + self.mlp(self.max_pool(x))
        return x * self.sigmoid(attn)


class SpatialAttention(nn.Module):
    def __init__(self, kernel_size=7):
        super().__init__()
        self.conv = nn.Conv2d(2, 1, kernel_size=kernel_size,
                              padding=kernel_size // 2, bias=False)
        self.sigmoid = nn.Sigmoid()

    def forward(self, x):
        avg_map = torch.mean(x, dim=1, keepdim=True)
        max_map, _ = torch.max(x, dim=1, keepdim=True)
        attn = self.conv(torch.cat([avg_map, max_map], dim=1))
        return x * self.sigmoid(attn)


class CBAM(nn.Module):
    """Channel attention then spatial attention, as in the paper."""

    def __init__(self, channels, reduction=16, spatial_kernel=7):
        super().__init__()
        self.channel = ChannelAttention(channels, reduction)
        self.spatial = SpatialAttention(spatial_kernel)

    def forward(self, x):
        return self.spatial(self.channel(x))

