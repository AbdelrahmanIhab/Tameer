"""
Tameer — Data Models & Validation
==================================
Pydantic models that mirror the exact JSON payloads published by the
ESP32 leader node. Invalid / out-of-range readings
are rejected before they ever reach InfluxDB.
"""

from __future__ import annotations
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator


# ── Soil metrics ──────────────────────────────────────────────────────────────
class SoilMetrics(BaseModel):
    moisture:    float = Field(..., ge=0,   le=100,  description="Soil moisture %")
    soil_temp:   float = Field(..., ge=-10, le=60,   description="Soil temperature °C")
    ec:          float = Field(..., ge=0,   le=10,   description="Electrical conductivity mS/cm")
    ph:          float = Field(..., ge=3,   le=10,   description="Soil pH")
    nitrogen:    float = Field(..., ge=0,   le=1000, description="Nitrogen mg/kg")
    phosphorus:  float = Field(..., ge=0,   le=500,  description="Phosphorus mg/kg")
    potassium:   float = Field(..., ge=0,   le=1000, description="Potassium mg/kg")


# ── Air / weather metrics ─────────────────────────────────────────────────────
class AirMetrics(BaseModel):
    air_temp:       float = Field(..., ge=-20, le=60,   description="Air temperature °C")
    air_humidity:   float = Field(..., ge=0,   le=100,  description="Relative humidity %")
    pressure:       float = Field(..., ge=800, le=1200, description="Air pressure hPa")
    light:          float = Field(..., ge=0,   le=1023, description="Light level (ADC 0-1023)")
    rain:           int   = Field(..., ge=0,   le=1,    description="Rain detected (0/1)")
    wind_speed:     float = Field(..., ge=0,   le=50,   description="Wind speed m/s")
    wind_direction: float = Field(..., ge=0,   le=360,  description="Wind direction degrees")
    uv_index:       float = Field(..., ge=0,   le=11,   description="UV index")
    air_quality:    float = Field(..., ge=0,   le=1000, description="MQ135 ppm")


# ── Generic node payload (what the leader publishes) ─────────────────────────
class SoilPayload(BaseModel):
    leader_id:  Optional[int]
    node_id:    int
    node_type:  Literal["soil"]
    is_leader:  bool
    timestamp:  datetime
    metrics:    SoilMetrics


class WeatherPayload(BaseModel):
    leader_id:  Optional[int]
    node_id:    int
    node_type:  Literal["weather"]
    is_leader:  bool
    timestamp:  datetime
    metrics:    AirMetrics


# ── Automation command (backend → MQTT → ESP32) ───────────────────────────────
class AutomationCommand(BaseModel):
    command_id:    str
    target_node:   int
    actuator:      Literal[
        "irrigation_valve",
        "fertilizer_pump",
        "fan",
        "heater",
        "grow_light",
        "shade",
        "spray_nozzle",
    ]
    action:        Literal["on", "off"]
    trigger_reason: str
    timestamp:     datetime


# ── API response schemas ──────────────────────────────────────────────────────
class LatestReadingsResponse(BaseModel):
    node_id:    int
    node_type:  str
    timestamp:  datetime
    metrics:    dict


class AutomationEvent(BaseModel):
    timestamp:      datetime
    actuator:       str
    action:         str
    trigger_reason: str
    node_id:        int
