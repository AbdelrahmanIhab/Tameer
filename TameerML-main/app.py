from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import torch, torch.nn.functional as F
from torchvision import transforms
from PIL import Image
from collections import deque
import numpy as np, io
from models import VisionBackbone, RadishFusionLSTM, ActorCritic

DEVICE      = torch.device('cpu')   # HF free tier is CPU only
WINDOW_SIZE = 5

ACTION_NAMES = {0: 'do_nothing', 1: 'irrigate', 2: 'fungicide', 3: 'pesticide'}
STATE_NAMES  = {0: 'pest', 1: 'fungal', 2: 'healthy', 3: 'drought', 4: 'overwatered'}

transform = transforms.Compose([
    transforms.Resize(256), transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize([0.485,0.456,0.406],[0.229,0.224,0.225])
])

sessions = {}   # device_id → {vision: deque, sensor: deque}

def blend_vision_with_sensors(vision_probs: torch.Tensor, soil_moisture: float) -> torch.Tensor:
    # EfficientNet was never trained on drought/overwatered images, so override
    # vision with a mock signal matching what the PPO fusion was trained on.
    if soil_moisture < 30.0:
        probs = torch.full((5,), 0.01)
        probs[3] = 0.96   # drought
    elif soil_moisture > 90.0:
        probs = torch.full((5,), 0.01)
        probs[4] = 0.96   # overwatered
    else:
        probs = vision_probs
    return probs

def load_models():
    # Vision — checkpoint was saved from a bare efficientnet_b0 (no wrapper),
    # so keys lack the "net." prefix that VisionBackbone adds via self.net.
    backbone = VisionBackbone()
    raw = torch.load('efficientnet_b0.pth', map_location=DEVICE, weights_only=True)
    backbone.load_state_dict({'net.' + k: v for k, v in raw.items()})
    backbone.eval()

    # PPO
    ckpt = torch.load('ppo.pth', map_location=DEVICE, weights_only=True)
    fusion = RadishFusionLSTM()
    fusion.load_state_dict(ckpt['fusion'])
    fusion.eval()

    actor_crit = ActorCritic()
    actor_crit.load_state_dict(ckpt['actor_crit'])
    actor_crit.eval()

    return backbone, fusion, actor_crit

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.backbone, app.state.fusion, app.state.actor_crit = load_models()
    yield

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/predict")
async def predict(
    image:         UploadFile = File(...),
    temperature:   float      = Form(...),
    humidity:      float      = Form(...),
    soil_moisture: float      = Form(...),
    device_id:     str        = Form(default="node_1"),
):
    backbone   = app.state.backbone
    fusion     = app.state.fusion
    actor_crit = app.state.actor_crit

    # --- vision ---
    img = Image.open(io.BytesIO(await image.read())).convert('RGB')
    img_tensor = transform(img).unsqueeze(0)
    with torch.no_grad():
        vision_probs = backbone(img_tensor).squeeze(0)   # (5,)
    vision_probs = blend_vision_with_sensors(vision_probs, soil_moisture)

    sensors = np.array([temperature, humidity, soil_moisture], dtype=np.float32)

    # --- rolling window ---
    if device_id not in sessions:
        sessions[device_id] = {
            'vision': deque([vision_probs] * WINDOW_SIZE, maxlen=WINDOW_SIZE),
            'sensor': deque([sensors]       * WINDOW_SIZE, maxlen=WINDOW_SIZE),
        }
    else:
        sessions[device_id]['vision'].append(vision_probs)
        sessions[device_id]['sensor'].append(sensors)

    v = torch.stack(list(sessions[device_id]['vision'])).unsqueeze(0)   # (1,T,5)
    s = torch.tensor(np.array(sessions[device_id]['sensor']),
                     dtype=torch.float32).unsqueeze(0)                   # (1,T,3)

    # --- inference ---
    with torch.no_grad():
        state_vec, _ = fusion(v, s)
        logits        = actor_crit.actor(state_vec.squeeze(0))
        action_probs  = F.softmax(logits, dim=-1)
        action        = action_probs.argmax().item()

    visual_disease = vision_probs.argmax().item()   # from EfficientNet directly

    # Override PPO when vision is highly confident, compensating for PPO
    # not generalizing well from mock one-hot training to real image distributions.
    top_prob = vision_probs.max().item()
    if top_prob > 0.75:
        if visual_disease == 2:    # clearly healthy
            action = 0             # do_nothing
        elif visual_disease == 1:  # clearly fungal
            action = 2             # fungicide
        elif visual_disease == 0:  # clearly pest
            action = 3             # pesticide

    irrigation_ml = round((80.0 - soil_moisture) * 10) if action == 1 else 0
    irrigation_ml = max(0, irrigation_ml)

    return {
        "action":         ACTION_NAMES[action],
        "action_id":      action,
        "action_probs":   action_probs.tolist(),
        "irrigation_ml":  irrigation_ml,
        "disease":        STATE_NAMES[visual_disease],
        "disease_id":     visual_disease,
        "vision_probs":   vision_probs.tolist(),
    }

@app.post("/diagnose")
async def diagnose(image: UploadFile = File(...)):
    backbone = app.state.backbone

    img = Image.open(io.BytesIO(await image.read())).convert('RGB')
    img_tensor = transform(img).unsqueeze(0)
    with torch.no_grad():
        vision_probs = backbone(img_tensor).squeeze(0)   # (5,)

    top_id = vision_probs.argmax().item()
    return {
        "state":        STATE_NAMES[top_id],
        "state_id":     top_id,
        "confidence":   round(vision_probs[top_id].item(), 4),
        "vision_probs": {STATE_NAMES[i]: round(p, 4) for i, p in enumerate(vision_probs.tolist())},
    }

@app.delete("/session/{device_id}")
def reset_session(device_id: str):
    sessions.pop(device_id, None)
    return {"reset": device_id}