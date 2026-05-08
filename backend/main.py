"""
Tameer — FastAPI Backend
=========================
Entry point.  Start with:
  uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

Or let the env drive it:
  python -m backend.main

Swagger UI: http://localhost:8000/docs
"""

import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import automation, camera, debug, sensors, voice
from backend.services import mqtt_service

load_dotenv()

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if os.getenv("DEBUG", "False") == "True" else logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)

# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    mqtt_service.start()
    yield
    mqtt_service.stop()


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Tameer — Smart Planting API",
    description=(
        "IoT backend for the Tameer agricultural monitoring system. "
        "Receives sensor data from ESP32 nodes via MQTT, stores it in InfluxDB, "
        "and runs automated irrigation/climate control decisions."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sensors.router)
app.include_router(automation.router)
app.include_router(camera.router)
app.include_router(debug.router)
app.include_router(voice.router)


@app.get("/", tags=["Health"])
async def root():
    return {
        "service": "Tameer API",
        "status":  "running",
        "docs":    "/docs",
    }


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}


# ── Run directly ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", "8000")),
        reload=os.getenv("DEBUG", "False") == "True",
    )
