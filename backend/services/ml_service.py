"""
Tameer — TameerML Client Service
==================================
Async HTTP client for the hosted TameerML inference service.

Environment variables:
  ML_API_URL          — base URL of the TameerML FastAPI service
                        e.g. https://your-space.hf.space
                        Defaults to http://localhost:7860 for local dev.
  ML_TIMEOUT_SECONDS  — request timeout in seconds (default: 30)
                        HuggingFace free-tier cold starts can take 30-60 s.
"""

from __future__ import annotations
import logging
import os

import httpx
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger("tameer.ml_service")

_BASE_URL = os.getenv("ML_API_URL", "http://localhost:7860")
_TIMEOUT  = float(os.getenv("ML_TIMEOUT_SECONDS", "30"))


async def diagnose(image_bytes: bytes, filename: str) -> dict:
    """
    Call TameerML POST /diagnose (vision-only classification).

    Returns: { state, state_id, confidence, vision_probs }
    Raises httpx.HTTPError / httpx.TimeoutException on failure.
    """
    async with httpx.AsyncClient(base_url=_BASE_URL, timeout=_TIMEOUT) as client:
        response = await client.post(
            "/diagnose",
            files={"image": (filename, image_bytes, "image/jpeg")},
        )
        response.raise_for_status()
        return response.json()


async def predict(
    image_bytes: bytes,
    filename: str,
    temperature: float,
    humidity: float,
    soil_moisture: float,
    device_id: str = "node_1",
) -> dict:
    """
    Call TameerML POST /predict (full fusion pipeline).

    Returns: { action, action_id, action_probs, irrigation_ml,
               disease, disease_id, vision_probs }
    Raises httpx.HTTPError / httpx.TimeoutException on failure.
    """
    async with httpx.AsyncClient(base_url=_BASE_URL, timeout=_TIMEOUT) as client:
        response = await client.post(
            "/predict",
            data={
                "temperature":   str(temperature),
                "humidity":      str(humidity),
                "soil_moisture": str(soil_moisture),
                "device_id":     device_id,
            },
            files={"image": (filename, image_bytes, "image/jpeg")},
        )
        response.raise_for_status()
        return response.json()


async def reset_session(device_id: str) -> dict:
    """
    Call TameerML DELETE /session/{device_id} to clear the LSTM rolling window.

    Returns: { reset: device_id }
    Raises httpx.HTTPError on failure.
    """
    async with httpx.AsyncClient(base_url=_BASE_URL, timeout=_TIMEOUT) as client:
        response = await client.delete(f"/session/{device_id}")
        response.raise_for_status()
        return response.json()
