"""
Tameer — Inference Router
==========================
POST /inference/disease               — classify a plant image
POST /inference/recommend/{zone_id}   — PPO action recommendation
"""

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from backend.ml.inference_service import inference_service

router = APIRouter(prefix="/inference", tags=["Inference"])


@router.post("/disease")
async def classify_disease(image: UploadFile = File(...)):
    """Run EfficientNet-B0 on a plant image and return the disease prediction."""
    if not inference_service.ready:
        raise HTTPException(status_code=503, detail="ML models not loaded")
    contents = await image.read()
    return inference_service.classify_image(contents)


@router.post("/recommend/{zone_id}")
async def recommend_action(
    zone_id: int,
    image: UploadFile = File(...),
    temp: float = Form(...),
    humidity: float = Form(...),
    soil_moisture: float = Form(...),
):
    """
    Run the full PPO pipeline: EfficientNet vision + Fusion LSTM + actor.
    Maintains a 5-timestep sliding window per zone on the server.
    """
    if not inference_service.ready:
        raise HTTPException(status_code=503, detail="ML models not loaded")
    contents = await image.read()
    return inference_service.recommend_action(
        zone_id=zone_id,
        image_bytes=contents,
        temp=temp,
        humidity=humidity,
        soil_moisture=soil_moisture,
    )
