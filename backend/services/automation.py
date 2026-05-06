"""
Tameer — Automation Decision Engine
=====================================
Evaluates incoming sensor readings against thresholds and publishes
MQTT control commands back to the ESP32 leader node.

Threshold table (radish-optimised):
┌─────────────────────────────┬───────────────────────────────┬────────────────────┐
│ Condition                   │ Action                        │ Actuator           │
├─────────────────────────────┼───────────────────────────────┼────────────────────┤
│ moisture < 40%              │ Turn ON irrigation valve      │ irrigation_valve   │
│ moisture > 85%              │ Turn OFF irrigation valve     │ irrigation_valve   │
│ rain == 1                   │ Lock irrigation (force OFF)   │ irrigation_valve   │
│ N/P/K any below min         │ Turn ON fertilizer pump       │ fertilizer_pump    │
│ air_temp > 35°C             │ Turn ON fan                   │ fan                │
│ air_temp < 10°C             │ Turn ON heater                │ heater             │
│ light < 200 (ADC)           │ Turn ON grow light            │ grow_light         │
│ uv_index > 8                │ Deploy shade                  │ shade              │
│ wind_speed > 15 m/s         │ Deploy shade/windbreak        │ shade              │
└─────────────────────────────┴───────────────────────────────┴────────────────────┘
"""

from __future__ import annotations
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Callable

log = logging.getLogger("tameer.automation")

# ── Thresholds ────────────────────────────────────────────────────────────────
THRESHOLDS = {
    "moisture_low":    40.0,   # % — start irrigation
    "moisture_high":   85.0,   # % — stop irrigation
    "air_temp_hot":    35.0,   # °C — turn on fan
    "air_temp_cold":   10.0,   # °C — turn on heater
    "light_low":       200.0,  # ADC — turn on grow light
    "uv_high":         8.0,    # UV index — deploy shade
    "wind_high":       15.0,   # m/s — deploy shade
    "nitrogen_min":    80.0,   # mg/kg
    "phosphorus_min":  20.0,   # mg/kg
    "potassium_min":   80.0,   # mg/kg
}


def compute_irrigation_minutes(
    moisture: float,
    air_temp: float = 25.0,
    humidity: float = 50.0,
    light: float = 50.0,
) -> float:
    """
    ET-adjusted irrigation duration in minutes.
    Returns 0.0 when the soil is wet enough (moisture >= 70%).
    """
    if moisture >= 70:
        return 0.0
    elif moisture >= 50:
        base = 5.0
    elif moisture >= 30:
        base = 10.0
    elif moisture >= 15:
        base = 20.0
    else:
        base = 30.0

    et = 1.0
    if air_temp > 35:
        et += 0.3
    elif air_temp > 30:
        et += 0.15
    if humidity < 30:
        et += 0.2
    elif humidity < 50:
        et += 0.1
    if light > 700:
        et += 0.1

    return round(base * et, 1)


def evaluate_soil(
    metrics: dict,
    node_id: int,
    publish_fn: Callable[[dict], None],
    write_event_fn: Callable[..., None],
) -> list[dict]:
    """
    Evaluate soil metrics and fire actuator commands as needed.
    Returns list of commands issued.
    """
    commands = []
    m = metrics

    # ── Irrigation ────────────────────────────────────────────────────────────
    if m["moisture"] < THRESHOLDS["moisture_low"]:
        minutes = compute_irrigation_minutes(moisture=m["moisture"])
        cmd = _make_command(node_id, "irrigation_valve", "irrigate",
                            f"moisture={m['moisture']}% < {THRESHOLDS['moisture_low']}% — {minutes} min")
        cmd["minutes"] = minutes
        _fire(cmd, publish_fn, write_event_fn)
        commands.append(cmd)

    elif m["moisture"] > THRESHOLDS["moisture_high"]:
        cmd = _make_command(node_id, "irrigation_valve", "off",
                            f"moisture={m['moisture']}% > {THRESHOLDS['moisture_high']}%")
        _fire(cmd, publish_fn, write_event_fn)
        commands.append(cmd)

    # ── Fertilizer ────────────────────────────────────────────────────────────
    deficiencies = []
    if m["nitrogen"]   < THRESHOLDS["nitrogen_min"]:
        deficiencies.append(f"N={m['nitrogen']}")
    if m["phosphorus"] < THRESHOLDS["phosphorus_min"]:
        deficiencies.append(f"P={m['phosphorus']}")
    if m["potassium"]  < THRESHOLDS["potassium_min"]:
        deficiencies.append(f"K={m['potassium']}")
    if deficiencies:
        cmd = _make_command(node_id, "fertilizer_pump", "on",
                            "NPK deficiency: " + ", ".join(deficiencies))
        _fire(cmd, publish_fn, write_event_fn)
        commands.append(cmd)

    return commands


def evaluate_weather(
    metrics: dict,
    node_id: int,
    publish_fn: Callable[[dict], None],
    write_event_fn: Callable[..., None],
) -> list[dict]:
    """
    Evaluate air/weather metrics and fire actuator commands as needed.
    Returns list of commands issued.
    """
    commands = []
    m = metrics

    # ── Rain → lock irrigation ────────────────────────────────────────────────
    if m["rain"] == 1:
        cmd = _make_command(node_id, "irrigation_valve", "off",
                            "Rain detected — locking irrigation")
        _fire(cmd, publish_fn, write_event_fn)
        commands.append(cmd)

    # ── Temperature ───────────────────────────────────────────────────────────
    if m["air_temp"] > THRESHOLDS["air_temp_hot"]:
        cmd = _make_command(node_id, "fan", "on",
                            f"air_temp={m['air_temp']}°C > {THRESHOLDS['air_temp_hot']}°C")
        _fire(cmd, publish_fn, write_event_fn)
        commands.append(cmd)

    if m["air_temp"] < THRESHOLDS["air_temp_cold"]:
        cmd = _make_command(node_id, "heater", "on",
                            f"air_temp={m['air_temp']}°C < {THRESHOLDS['air_temp_cold']}°C")
        _fire(cmd, publish_fn, write_event_fn)
        commands.append(cmd)

    # ── Light ──────────────────────────────────────────────────────────────────
    if m["light"] < THRESHOLDS["light_low"]:
        cmd = _make_command(node_id, "grow_light", "on",
                            f"light={m['light']} ADC < {THRESHOLDS['light_low']}")
        _fire(cmd, publish_fn, write_event_fn)
        commands.append(cmd)

    # ── UV / Wind → shade ──────────────────────────────────────────────────────
    if m["uv_index"] > THRESHOLDS["uv_high"]:
        cmd = _make_command(node_id, "shade", "on",
                            f"uv_index={m['uv_index']} > {THRESHOLDS['uv_high']}")
        _fire(cmd, publish_fn, write_event_fn)
        commands.append(cmd)

    elif m["wind_speed"] > THRESHOLDS["wind_high"]:
        cmd = _make_command(node_id, "shade", "on",
                            f"wind_speed={m['wind_speed']} m/s > {THRESHOLDS['wind_high']} m/s")
        _fire(cmd, publish_fn, write_event_fn)
        commands.append(cmd)

    return commands


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_command(
    node_id: int,
    actuator: str,
    action: str,
    reason: str,
) -> dict:
    return {
        "command_id":    str(uuid.uuid4())[:8],
        "target_node":   node_id,
        "actuator":      actuator,
        "action":        action,
        "trigger_reason": reason,
        "timestamp":     datetime.now(timezone.utc).isoformat(),
    }


def _fire(
    cmd: dict,
    publish_fn: Callable[[dict], None],
    write_event_fn: Callable[..., None],
) -> None:
    log.info("🤖 AUTOMATION  %s → %s [%s]  reason: %s",
             cmd["actuator"], cmd["action"], cmd["command_id"], cmd["trigger_reason"])
    publish_fn(cmd)
    write_event_fn(
        node_id=cmd["target_node"],
        actuator=cmd["actuator"],
        action=cmd["action"],
        trigger_reason=cmd["trigger_reason"],
    )
