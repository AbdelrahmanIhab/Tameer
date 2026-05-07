import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision.models import efficientnet_b0


class VisionBackbone(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = efficientnet_b0(weights=None)
        self.net.classifier[1] = nn.Linear(
            self.net.classifier[1].in_features, 5
        )

    @torch.no_grad()
    def forward(self, x):
        return F.softmax(self.net(x), dim=-1)


class RadishFusionLSTM(nn.Module):
    def __init__(self, sensor_size=3, vision_size=5,
                 embed_dim=64, hidden_size=64, num_layers=1):
        super().__init__()
        self.hidden_size = hidden_size
        self.num_layers  = num_layers
        self.fusion_proj = nn.Sequential(
            nn.Linear(sensor_size + vision_size, embed_dim),
            nn.LayerNorm(embed_dim), nn.ReLU(),
            nn.Linear(embed_dim, embed_dim), nn.ReLU()
        )
        self.lstm = nn.LSTM(embed_dim, hidden_size,
                            num_layers=num_layers, batch_first=True)

    def normalize_sensors(self, x):
        t = (x[..., 0:1] - 5.0)  / 30.0
        h = (x[..., 1:2] - 20.0) / 80.0
        m =  x[..., 2:3]          / 100.0
        return torch.cat([t, h, m], dim=-1)

    def forward(self, vision_probs, sensor_data, hx=None):
        norm_s = self.normalize_sensors(sensor_data)
        fused  = torch.cat([vision_probs, norm_s], dim=-1)
        embed  = self.fusion_proj(fused)
        out, (h, c) = self.lstm(embed, hx)
        return h[-1], (h, c)


class ActorCritic(nn.Module):
    def __init__(self, state_dim=64, action_dim=4):
        super().__init__()
        self.actor = nn.Sequential(
            nn.Linear(state_dim, 64), nn.Tanh(),
            nn.Linear(64, action_dim)
        )
        self.critic = nn.Sequential(
            nn.Linear(state_dim, 64), nn.Tanh(),
            nn.Linear(64, 1)
        )