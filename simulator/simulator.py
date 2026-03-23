"""
Tameer — Sensor Data Simulator
===============================
Mimics the Leader ESP32 node publishing aggregated sensor data to HiveMQ.

Two virtual nodes are simulated:
  • smartplant/soilnode1    — soil moisture, temperature, EC, pH, NPK
  • smartplant/weathernode1 — air temp, humidity, pressure, light, rain,
                               wind speed, wind direction, UV, air quality

Values drift slowly and realistically around radish-optimal ranges.
A "scenario" mode can inject fault conditions (drought, overwater, heat stress)
to let you verify the backend automation engine reacts correctly.

Usage:
  python simulator.py                    # normal mode
  python simulator.py --scenario drought
  python simulator.py --scenario overwater
  python simulator.py --scenario heat
  python simulator.py --interval 5       # publish every 5 s (default 10)
"""

import argparse
import json
import math
import random
import ssl
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import paho.mqtt.client as mqtt
from dotenv import load_dotenv
import os

load_dotenv(Path(__file__).parent.parent / ".env")

# ── MQTT config ───────────────────────────────────────────────────────────────
BROKER   = os.getenv("MQTT_BROKER",        "broker.hivemq.com")
PORT     = int(os.getenv("MQTT_PORT",      "1883"))
USERNAME = os.getenv("MQTT_USERNAME_ESP32","")
PASSWORD = os.getenv("MQTT_PASSWORD_ESP32","")

TOPICS = {
    "soil":    "smartplant/soilnode1",
    "weather": "smartplant/weathernode1",
}

# ── Radish-optimal sensor ranges ─────────────────────────────────────────────
#   Each entry: (center, half_range, min_clip, max_clip)
NORMAL_RANGES = {
    # Soil node
    "moisture":        (55.0,  8.0,  0.0, 100.0),  # %
    "soil_temp":       (22.0,  3.0, 10.0,  40.0),  # °C
    "ec":              (1.4,   0.3,  0.0,   5.0),  # mS/cm
    "ph":              (6.5,   0.4,  4.0,   9.0),  # pH
    "nitrogen":        (180.0, 20.0, 0.0, 500.0),  # mg/kg
    "phosphorus":      (45.0,  8.0,  0.0, 200.0),  # mg/kg
    "potassium":       (200.0, 25.0, 0.0, 600.0),  # mg/kg
    # Air/Weather node
    "air_temp":        (25.0,  4.0, -10.0, 50.0),  # °C
    "air_humidity":    (65.0, 10.0,   0.0,100.0),  # %
    "pressure":        (1013.0, 5.0, 900.0,1100.0),# hPa
    "light":           (600.0,150.0,  0.0,1023.0), # lux (0-1023 ADC)
    "rain":            (0.0,   0.0,   0.0,   1.0), # binary (mostly 0)
    "wind_speed":      (2.5,   1.5,   0.0,  30.0), # m/s
    "wind_direction":  (180.0, 90.0,  0.0, 360.0), # degrees
    "uv_index":        (3.0,   1.5,   0.0,  11.0), # UV index
    "air_quality":     (120.0, 30.0,  0.0, 500.0), # MQ135 ppm
}

# ── Scenario overrides ────────────────────────────────────────────────────────
SCENARIOS = {
    "drought": {
        "moisture":   (20.0, 5.0, 0.0, 100.0),  # critically dry
        "air_temp":   (35.0, 2.0, 10.0, 50.0),  # hot day
        "uv_index":   (8.0,  1.0,  0.0, 11.0),  # high UV
    },
    "overwater": {
        "moisture":   (92.0, 3.0, 0.0, 100.0),  # waterlogged
        "rain":       (1.0,  0.0, 0.0,  1.0),   # raining
        "ph":         (7.8,  0.3, 4.0,  9.0),   # slightly alkaline drift
    },
    "heat": {
        "air_temp":   (42.0, 2.0, 10.0, 50.0),  # heat stress
        "air_humidity":(30.0, 5.0,  0.0,100.0),  # dry air
        "uv_index":   (9.5,  0.5,  0.0, 11.0),
    },
    "npk_deficient": {
        "nitrogen":   (40.0, 10.0, 0.0, 500.0),
        "phosphorus": (10.0,  3.0, 0.0, 200.0),
        "potassium":  (35.0, 10.0, 0.0, 600.0),
    },
}

# ── Internal drift state ──────────────────────────────────────────────────────
_drift: dict[str, float] = {}

def _init_drift(ranges: dict) -> None:
    for key, (center, _, lo, hi) in ranges.items():
        _drift[key] = center

def _next_value(key: str, ranges: dict) -> float:
    """Slowly walk the current drift value within the allowed range."""
    center, half, lo, hi = ranges[key]
    # Small random step, biased back toward center (mean-reversion)
    step = random.gauss(0, half * 0.06)
    revert = (center - _drift[key]) * 0.04
    _drift[key] = max(lo, min(hi, _drift[key] + step + revert))
    # Add tiny noise on top
    noise = random.gauss(0, half * 0.01)
    return round(max(lo, min(hi, _drift[key] + noise)), 2)


def build_soil_payload(node_id: int, is_leader: bool, ranges: dict) -> dict:
    return {
        "leader_id":   node_id if is_leader else None,
        "node_id":     node_id,
        "node_type":   "soil",
        "is_leader":   is_leader,
        "timestamp":   datetime.now(timezone.utc).isoformat(),
        "metrics": {
            "moisture":   _next_value("moisture",   ranges),
            "soil_temp":  _next_value("soil_temp",  ranges),
            "ec":         _next_value("ec",         ranges),
            "ph":         _next_value("ph",         ranges),
            "nitrogen":   _next_value("nitrogen",   ranges),
            "phosphorus": _next_value("phosphorus", ranges),
            "potassium":  _next_value("potassium",  ranges),
        },
    }


def build_weather_payload(node_id: int, is_leader: bool, ranges: dict) -> dict:
    return {
        "leader_id":   None,
        "node_id":     node_id,
        "node_type":   "weather",
        "is_leader":   is_leader,
        "timestamp":   datetime.now(timezone.utc).isoformat(),
        "metrics": {
            "air_temp":       _next_value("air_temp",       ranges),
            "air_humidity":   _next_value("air_humidity",   ranges),
            "pressure":       _next_value("pressure",       ranges),
            "light":          _next_value("light",          ranges),
            "rain":           1 if _drift.get("rain", 0) > 0.5 else 0,
            "wind_speed":     _next_value("wind_speed",     ranges),
            "wind_direction": _next_value("wind_direction", ranges),
            "uv_index":       _next_value("uv_index",       ranges),
            "air_quality":    _next_value("air_quality",    ranges),
        },
    }


# ── MQTT callbacks ─────────────────────────────────────────────────────────────
def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0:
        print("✅  Connected to MQTT broker")
    else:
        print(f"❌  Connection failed — reason code {reason_code}")
        sys.exit(1)

def on_publish(client, userdata, mid, reason_code=None, properties=None):
    pass  # silent ack


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Tameer sensor simulator")
    parser.add_argument("--scenario", choices=list(SCENARIOS.keys()),
                        default=None, help="Inject a fault scenario")
    parser.add_argument("--interval", type=float, default=10.0,
                        help="Publish interval in seconds (default 10)")
    args = parser.parse_args()

    # Merge scenario overrides into ranges
    ranges = dict(NORMAL_RANGES)
    if args.scenario:
        ranges.update(SCENARIOS[args.scenario])
        print(f"⚠️   Running scenario: {args.scenario.upper()}")

    _init_drift(ranges)

    # Build MQTT client
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         client_id="tameer-simulator")
    client.on_connect = on_connect
    client.on_publish = on_publish

    if USERNAME:
        client.username_pw_set(USERNAME, PASSWORD)
    if PORT == 8883:
        client.tls_set(tls_version=ssl.PROTOCOL_TLS_CLIENT)

    print(f"🔌  Connecting to {BROKER}:{PORT} …")
    client.connect(BROKER, PORT, keepalive=60)
    client.loop_start()
    time.sleep(1.5)  # wait for on_connect

    cycle = 0
    print(f"📡  Publishing every {args.interval}s  (Ctrl+C to stop)\n")
    try:
        while True:
            cycle += 1
            # Node 2 is the leader (higher ID wins election)
            soil_payload    = build_soil_payload(1, is_leader=False, ranges=ranges)
            weather_payload = build_weather_payload(2, is_leader=True, ranges=ranges)

            for topic, payload in [
                (TOPICS["soil"],    soil_payload),
                (TOPICS["weather"], weather_payload),
            ]:
                msg = json.dumps(payload)
                result = client.publish(topic, msg, qos=1)
                status = "✓" if result.rc == 0 else "✗"
                print(f"  [{cycle:04d}] {status} {topic}")
                print(f"          {msg[:120]}{'…' if len(msg) > 120 else ''}")

            print()
            time.sleep(args.interval)

    except KeyboardInterrupt:
        print("\n🛑  Simulator stopped.")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
