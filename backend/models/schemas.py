"""
Tameer — Data Models & Validation
==================================
Pydantic models that mirror the exact JSON payloads published by the
ESP32 leader node. Invalid / out-of-range readings are rejected before
they ever reach InfluxDB.
"""

from __future__ import annotations
from datetime import datetime
from typing import Literal, Union
from pydantic import BaseModel, Field, model_validator


# ── Soil metrics (only sensors physically present) ────────────────────────────
class SoilMetrics(BaseModel):
    moisture:  float = Field(..., ge=0,   le=100, description="Soil moisture %")
    soil_temp: float = Field(..., ge=-10, le=60,  description="Soil temperature °C")


# ── Air / weather metrics (only sensors physically present) ───────────────────
class AirMetrics(BaseModel):
    air_temp:    float = Field(..., ge=-20, le=60,  description="Air temperature °C")
    air_humidity:float = Field(..., ge=0,   le=100, description="Relative humidity %")
    light:       float = Field(..., ge=0,   le=100, description="LDR light level %")
    air_quality: float = Field(..., ge=0,   le=100, description="MQ135 air quality %")


# ── Per-node reading inside a zone payload ────────────────────────────────────
class NodeReading(BaseModel):
    node_type: Literal["soil", "weather"]
    instance:  int
    metrics:   Union[SoilMetrics, AirMetrics]

    @model_validator(mode="before")
    @classmethod
    def coerce_metrics(cls, data: dict) -> dict:
        nt      = data.get("node_type")
        metrics = data.get("metrics", {})
        if isinstance(metrics, dict):
            if nt == "soil":
                data["metrics"] = SoilMetrics(**metrics)
            elif nt == "weather":
                data["metrics"] = AirMetrics(**metrics)
        return data


# ── Zone aggregate payload (what the leader publishes to MQTT) ────────────────
class ZonePayload(BaseModel):
    zone_id:         int
    leader_instance: int
    nodes:           list[NodeReading]


# ── Automation command (backend → MQTT → ESP32 actuator) ─────────────────────
class AutomationCommand(BaseModel):
    command_id:     str
    zone_id:        int
    actuator:       Literal[
        "irrigation_valve",
        "fertilizer_pump",
        "fan",
        "heater",
        "grow_light",
        "shade",
        "spray_nozzle",
    ]
    action:         Literal["on", "off"]
    trigger_reason: str
    timestamp:      datetime


# ── API response schemas ──────────────────────────────────────────────────────
class LatestReadingsResponse(BaseModel):
    zone_id:       int
    node_type:     str
    node_instance: int
    timestamp:     datetime
    metrics:       dict


class AutomationEvent(BaseModel):
    timestamp:      datetime
    actuator:       str
    action:         str
    trigger_reason: str
    zone_id:        int


# ── ML service response schemas ───────────────────────────────────────────────

class DiagnoseResponse(BaseModel):
    """Response from TameerML POST /diagnose (vision-only)."""
    state:        str
    state_id:     int
    confidence:   float
    vision_probs: dict[str, float]   # {"pest": 0.01, "fungal": 0.95, ...}


class PredictResponse(BaseModel):
    """Response from TameerML POST /predict (full fusion pipeline)."""
    action:        str
    action_id:     int
    action_probs:  list[float]       # [do_nothing, irrigate, fungicide, pesticide]
    irrigation_ml: int
    disease:       str
    disease_id:    int
    vision_probs:  list[float]       # [pest, fungal, healthy, drought, overwatered]
