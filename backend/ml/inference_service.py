"""
Tameer — ML Inference Service
==============================
Singleton that owns both loaded models and per-zone sliding windows.
Call inference_service.load() once at app startup.
"""

import logging
import os
from collections import defaultdict, deque
from io import BytesIO

import numpy as np
import torch
from PIL import Image
from torchvision import transforms

from backend.ml.models import ActorCritic, RadishFusionLSTM, VisionBackbone

log = logging.getLogger("tameer.inference")

DISEASE_NAMES = {
    0: "Pest damage",
    1: "Fungal disease",
    2: "Healthy",
    3: "Drought stress",
    4: "Overwatered",
}

ACTION_NAMES = {
    0: "Do nothing",
    1: "Irrigate",
    2: "Apply fungicide",
    3: "Apply pesticide",
}

_WINDOW_SIZE = 5

_preprocess = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])


class InferenceService:
    def __init__(self):
        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._backbone: VisionBackbone | None = None
        self._fusion: RadishFusionLSTM | None = None
        self._actor_crit: ActorCritic | None = None
        # per-zone sliding windows: zone_id → deque of tensors/arrays
        self._vision_windows: dict[int, deque] = defaultdict(lambda: deque(maxlen=_WINDOW_SIZE))
        self._sensor_windows: dict[int, deque] = defaultdict(lambda: deque(maxlen=_WINDOW_SIZE))

    def load(self) -> None:
        _default = os.path.join(os.path.dirname(__file__), "weights")
        models_path = os.getenv("ML_MODELS_PATH", _default)
        eff_path = os.path.join(models_path, "efficientnet_b0_radish.pth")
        ppo_path = os.path.join(models_path, "radish_ppo.pth")

        log.info("Loading EfficientNet-B0 from %s", eff_path)
        self._backbone = VisionBackbone(eff_path).to(self._device)
        self._backbone.eval()

        log.info("Loading PPO agent from %s", ppo_path)
        self._fusion = RadishFusionLSTM().to(self._device)
        self._actor_crit = ActorCritic().to(self._device)
        checkpoint = torch.load(ppo_path, map_location=self._device, weights_only=False)
        self._fusion.load_state_dict(checkpoint["fusion"])
        self._actor_crit.load_state_dict(checkpoint["actor_crit"])
        self._fusion.eval()
        self._actor_crit.eval()

        log.info("ML models loaded on %s", self._device)

    @property
    def ready(self) -> bool:
        return self._backbone is not None

    def _image_to_tensor(self, image_bytes: bytes) -> torch.Tensor:
        img = Image.open(BytesIO(image_bytes)).convert("RGB")
        return _preprocess(img).unsqueeze(0).to(self._device)  # (1, 3, 224, 224)

    def classify_image(self, image_bytes: bytes) -> dict:
        tensor = self._image_to_tensor(image_bytes)
        with torch.no_grad():
            probs = self._backbone(tensor)  # (1, 5)
        probs_list = probs.squeeze(0).cpu().tolist()
        disease_class = int(probs.argmax().item())
        confidence = float(probs.max().item())
        return {
            "disease_class": disease_class,
            "disease_name": DISEASE_NAMES[disease_class],
            "confidence": round(confidence, 4),
            "probabilities": [round(p, 4) for p in probs_list],
        }

    def recommend_action(
        self,
        zone_id: int,
        image_bytes: bytes,
        temp: float,
        humidity: float,
        soil_moisture: float,
    ) -> dict:
        tensor = self._image_to_tensor(image_bytes)
        with torch.no_grad():
            probs = self._backbone(tensor)  # (1, 5)
        probs_list = probs.squeeze(0).cpu().tolist()
        disease_class = int(probs.argmax().item())
        confidence = float(probs.max().item())
        disease_pred = {
            "disease_class": disease_class,
            "disease_name": DISEASE_NAMES[disease_class],
            "confidence": round(confidence, 4),
            "probabilities": [round(p, 4) for p in probs_list],
        }

        sensor_vec = np.array([temp, humidity, soil_moisture], dtype=np.float32)
        self._vision_windows[zone_id].append(probs.squeeze(0).cpu())  # (5,)
        self._sensor_windows[zone_id].append(sensor_vec)               # (3,)

        v_list = list(self._vision_windows[zone_id])
        s_list = list(self._sensor_windows[zone_id])
        # pad to window size if not enough history yet
        while len(v_list) < _WINDOW_SIZE:
            v_list.insert(0, v_list[0])
            s_list.insert(0, s_list[0])

        v = torch.stack(v_list).unsqueeze(0).to(self._device)   # (1, 5, 5)
        s = torch.tensor(np.array(s_list), dtype=torch.float32).unsqueeze(0).to(self._device)  # (1, 5, 3)

        with torch.no_grad():
            state_vec, _ = self._fusion(v, s)                     # (1, 64)
            logits = self._actor_crit.actor(state_vec.squeeze(0)) # (4,)
            action = int(logits.argmax().item())

        return {
            "action": action,
            "action_name": ACTION_NAMES[action],
            "disease_prediction": disease_pred,
            "sensor_readings": {
                "temp": temp,
                "humidity": humidity,
                "soil_moisture": soil_moisture,
            },
        }


inference_service = InferenceService()
