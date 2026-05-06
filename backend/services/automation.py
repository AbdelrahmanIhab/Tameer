"""
Tameer — Automation Decision Engine
=====================================
Evaluates incoming sensor readings against thresholds and publishes
MQTT control commands to the actuator node in the same zone.

Threshold table (radish-optimised, based on connected sensors only):
┌──────────────────────────┬──────────────────────────────┬──────────────────────┐
│ Condition                │ Action                       │ Actuator             │
├──────────────────────────┼──────────────────────────────┼──────────────────────┤
│ moisture < 40%           │ Turn ON irrigation valve     │ irrigation_valve     │
│ moisture > 85%           │ Turn OFF irrigation valve    │ irrigation_valve     │
│ air_temp > 35°C          │ Turn ON fan                  │ fan                  │
│ air_temp < 10°C          │ Turn ON heater               │ heater               │
│ light < 20%              │ Turn ON grow light           │ grow_light           │
└──────────────────────────┴──────────────────────────────┴──────────────────────┘
"""

from __future__ import annotations
import logging
import uuid
from datetime import datetime, timezone
from typing import Callable

from backend.services import debug_bus

log = logging.getLogger("tameer.automation")

THRESHOLDS = {
    "moisture_low":  40.0,   # % — start irrigation
    "moisture_high": 85.0,   # % — stop irrigation
    "air_temp_hot":  35.0,   # °C — turn on fan
    "air_temp_cold": 10.0,   # °C — turn on heater
    "light_low":     20.0,   # % — turn on grow light
}


def compute_irrigation_minutes(
    moisture: float,
    air_temp: float = 25.0,
    humidity: float = 50.0,
    light: float    = 50.0,
) -> float:
    """ET-adjusted irrigation duration in minutes. Returns 0.0 when soil is wet enough."""
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
    if light > 70:
        et += 0.1

    return round(base * et, 1)


def evaluate_soil(
    metrics: dict,
    zone_id: int,
    publish_fn: Callable[[dict], None],
    write_event_fn: Callable[..., None],
    trace_id: str = "",
) -> list[dict]:
    commands = []
    m = metrics

    if m["moisture"] < THRESHOLDS["moisture_low"]:
        minutes = compute_irrigation_minutes(moisture=m["moisture"])
        cmd = _make_command(zone_id, "irrigation_valve", "irrigate",
                            f"moisture={m['moisture']}% < {THRESHOLDS['moisture_low']}% — {minutes} min")
        cmd["minutes"] = minutes
        _fire(cmd, publish_fn, write_event_fn, trace_id)
        commands.append(cmd)

    elif m["moisture"] > THRESHOLDS["moisture_high"]:
        cmd = _make_command(zone_id, "irrigation_valve", "off",
                            f"moisture={m['moisture']}% > {THRESHOLDS['moisture_high']}%")
        _fire(cmd, publish_fn, write_event_fn, trace_id)
        commands.append(cmd)

    return commands


def evaluate_weather(
    metrics: dict,
    zone_id: int,
    publish_fn: Callable[[dict], None],
    write_event_fn: Callable[..., None],
    trace_id: str = "",
) -> list[dict]:
    commands = []
    m = metrics

    if m["air_temp"] > THRESHOLDS["air_temp_hot"]:
        cmd = _make_command(zone_id, "fan", "on",
                            f"air_temp={m['air_temp']}°C > {THRESHOLDS['air_temp_hot']}°C")
        _fire(cmd, publish_fn, write_event_fn, trace_id)
        commands.append(cmd)

    if m["air_temp"] < THRESHOLDS["air_temp_cold"]:
        cmd = _make_command(zone_id, "heater", "on",
                            f"air_temp={m['air_temp']}°C < {THRESHOLDS['air_temp_cold']}°C")
        _fire(cmd, publish_fn, write_event_fn, trace_id)
        commands.append(cmd)

    if m["light"] < THRESHOLDS["light_low"]:
        cmd = _make_command(zone_id, "grow_light", "on",
                            f"light={m['light']}% < {THRESHOLDS['light_low']}%")
        _fire(cmd, publish_fn, write_event_fn, trace_id)
        commands.append(cmd)

    return commands


def evaluate_ppo_action(
    action: int,
    action_name: str,
    disease_name: str,
    confidence: float,
    zone_id: int,
    already_irrigating: bool,
    moisture: float,
    publish_fn: Callable[[dict], None],
    write_event_fn: Callable[..., None],
    trace_id: str = "",
) -> list[dict]:
    """
    Translates a PPO action into actuator commands.
    Skips irrigation if the threshold engine already triggered it.
    Adds fungicide/pesticide commands that the threshold engine never produces.
    """
    commands = []
    reason = f"PPO {confidence:.0%} conf [{disease_name}] → {action_name}"

    if action == 0:
        log.info("🤖 PPO  zone=%d  → Do nothing  [%s  %.0f%%]", zone_id, disease_name, confidence * 100)

    elif action == 1:  # irrigate
        if not already_irrigating:
            minutes = compute_irrigation_minutes(moisture=moisture)
            cmd = _make_command(zone_id, "irrigation_valve", "irrigate", reason)
            cmd["minutes"] = minutes
            _fire(cmd, publish_fn, write_event_fn, trace_id)
            commands.append(cmd)
        else:
            log.info("🤖 PPO  zone=%d  → Irrigate [skipped — threshold already triggered]", zone_id)

    elif action == 2:  # fungicide
        cmd = _make_command(zone_id, "fungicide_system", "apply", reason)
        _fire(cmd, publish_fn, write_event_fn, trace_id)
        commands.append(cmd)

    elif action == 3:  # pesticide
        cmd = _make_command(zone_id, "pesticide_system", "apply", reason)
        _fire(cmd, publish_fn, write_event_fn, trace_id)
        commands.append(cmd)

    return commands


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_command(zone_id: int, actuator: str, action: str, reason: str) -> dict:
    return {
        "command_id":    str(uuid.uuid4())[:8],
        "zone_id":       zone_id,
        "actuator":      actuator,
        "action":        action,
        "trigger_reason": reason,
        "timestamp":     datetime.now(timezone.utc).isoformat(),
    }


def _fire(
    cmd: dict,
    publish_fn: Callable[[dict], None],
    write_event_fn: Callable[..., None],
    trace_id: str = "",
) -> None:
    log.info("🤖 AUTOMATION  zone=%s  %s → %s [%s]  reason: %s",
             cmd["zone_id"], cmd["actuator"], cmd["action"],
             cmd["command_id"], cmd["trigger_reason"])
    try:
        debug_bus.emit({
            "trace_id":      trace_id,
            "ts":            datetime.now(timezone.utc).isoformat(),
            "stage":         "automation",
            "zone_id":       cmd["zone_id"],
            "node_type":     "—",
            "node_instance": 0,
            "status":        "ok",
            "detail":        f"{cmd['actuator']} → {cmd['action']}  ·  {cmd['trigger_reason']}",
            "extra": {
                "command_id": cmd["command_id"],
                "actuator":   cmd["actuator"],
                "action":     cmd["action"],
            },
        })
    except Exception:
        pass
    publish_fn(cmd)
    write_event_fn(
        zone_id=cmd["zone_id"],
        actuator=cmd["actuator"],
        action=cmd["action"],
        trigger_reason=cmd["trigger_reason"],
        trace_id=trace_id,
    )
