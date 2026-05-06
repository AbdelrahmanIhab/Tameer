"""
ML model class definitions for Tameer inference.

VisionBackbone  — frozen EfficientNet-B0, outputs 5-class softmax probs
RadishFusionLSTM — fuses vision + sensor windows into a 64-dim state vector
ActorCritic      — PPO actor-critic head (4 actions)
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision.models import efficientnet_b0


class VisionBackbone(nn.Module):
    def __init__(self, checkpoint_path: str):
        super().__init__()
        self.net = efficientnet_b0(weights=None)
        self.net.classifier[1] = nn.Linear(self.net.classifier[1].in_features, 5)
        self.net.load_state_dict(torch.load(checkpoint_path, map_location="cpu", weights_only=True))
        for param in self.net.parameters():
            param.requires_grad = False
        self.net.eval()

    @torch.no_grad()
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, 3, 224, 224) → (B, 5) softmax
        return F.softmax(self.net(x), dim=-1)


class RadishFusionLSTM(nn.Module):
    def __init__(self, sensor_size: int = 3, vision_size: int = 5,
                 embed_dim: int = 64, hidden_size: int = 64, num_layers: int = 1):
        super().__init__()
        self.hidden_size = hidden_size
        self.fusion_proj = nn.Sequential(
            nn.Linear(vision_size + sensor_size, embed_dim),
            nn.LayerNorm(embed_dim),
            nn.ReLU(),
            nn.Linear(embed_dim, embed_dim),
            nn.ReLU(),
        )
        self.lstm = nn.LSTM(embed_dim, hidden_size, num_layers=num_layers, batch_first=True)

    def _normalize_sensors(self, x: torch.Tensor) -> torch.Tensor:
        t = (x[..., 0:1] - 5.0) / 30.0    # temperature 5–35°C
        h = (x[..., 1:2] - 20.0) / 80.0   # humidity 20–100%
        m = x[..., 2:3] / 100.0            # soil moisture 0–100%
        return torch.cat([t, h, m], dim=-1)

    def forward(self, vision_probs: torch.Tensor, sensor_data: torch.Tensor,
                hx=None):
        # vision_probs: (B, T, 5)   sensor_data: (B, T, 3)
        norm_s = self._normalize_sensors(sensor_data)
        fused  = torch.cat([vision_probs, norm_s], dim=-1)   # (B, T, 8)
        embed  = self.fusion_proj(fused)                      # (B, T, 64)
        out, (h, c) = self.lstm(embed, hx)
        return h[-1], (h, c)                                  # (B, 64), state


class ActorCritic(nn.Module):
    def __init__(self, state_dim: int = 64, action_dim: int = 4):
        super().__init__()
        self.actor = nn.Sequential(
            nn.Linear(state_dim, 64),
            nn.Tanh(),
            nn.Linear(64, action_dim),
        )
        self.critic = nn.Sequential(
            nn.Linear(state_dim, 64),
            nn.Tanh(),
            nn.Linear(64, 1),
        )
