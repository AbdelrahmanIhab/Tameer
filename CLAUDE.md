# CLAUDE.md — Tameer Smart Planting System

This file gives Claude Code persistent context about the Tameer project.
Read this before making any changes.

---

## What this project is

Tameer (تعمير) is a low-cost IoT agricultural monitoring and automation system
targeting Egyptian farmers. It monitors crop conditions in real-time, automates
irrigation and environmental control, detects plant diseases, and presents data
through a bilingual (Arabic/English) dashboard.

Test crop: **radish** (short growth cycle, ideal for fast iteration).
This is a senior thesis project at AUC (American University in Cairo).

---

## Current implementation status

### ✅ Done (Thesis 1)
- System architecture fully designed
- ESP32 prototype nodes built (soil node, air/weather node)
- ESP-NOW mesh + leader election working
- EfficientNetB0 disease detection model trained (99% accuracy, 5 radish classes)
- Basic dashboard prototype

### ✅ Done (Thesis 2 — software)
- FastAPI backend (`backend/`)
- MQTT subscriber + publisher (`backend/services/mqtt_service.py`)
- InfluxDB reads/writes (`backend/services/influx_service.py`)
- Automation decision engine (`backend/services/automation.py`)
- REST API endpoints for sensors and automation (`backend/routers/`)
- Pydantic validation models (`backend/models/schemas.py`)

### 🔄 In progress (Thesis 2 — hardware integration)
- Real ESP32 nodes connected (replacing simulator)

### ⏳ Not yet started
- React + Vite PWA dashboard (farmer view + engineer view)
- Random Forest ML model training (needs real sensor data)
- EfficientNetB0 inference endpoint integration
- ESP32 firmware refinement (Arduino/PlatformIO)

---

## Zone architecture

Each **zone** = one plot of land, containing:
- 1 soil node  (ESP32 with capacitive moisture + DS18B20 temp sensor)
- 1 actuator node  (ESP32 controlling the irrigation valve)
- 1 camera node  (ESP32-CAM, uploads directly over HTTPS)

One **weather node** (DHT22 + LDR + MQ135) is shared across the whole plot (zone_id = 0).

All soil + weather nodes form a single ESP-NOW mesh (channel 11, broadcast). One node wins the leader election each cycle and publishes aggregated data to HiveMQ Cloud over WiFi.

## Project structure

```
tameer/
├── CLAUDE.md                        ← you are here
├── README.md                        ← human-readable setup guide
├── .env                             ← credentials (never commit)
├── .gitignore
├── requirements.txt
├── firmware/
│   ├── SoilNode/SoilNode.ino        ← ZONE_ID + NODE_INSTANCE defines at top
│   ├── WeatherNode/WeatherNode.ino  ← ZONE_ID=0 (common), NODE_INSTANCE=1
│   ├── ActuatorNode/ActuatorNode.ino← ZONE_ID define at top
│   └── CamNode/CamNode.ino         ← ZONE_ID + CAM_INSTANCE defines at top
├── scripts/
│   └── purge_simulator_data.py      ← one-time InfluxDB cleanup (already run)
└── backend/
    ├── __init__.py
    ├── main.py                      ← FastAPI entry point
    ├── models/
    │   ├── __init__.py
    │   └── schemas.py               ← Pydantic payload validation models
    ├── services/
    │   ├── __init__.py
    │   ├── mqtt_service.py          ← MQTT subscriber + command publisher
    │   ├── influx_service.py        ← InfluxDB reads and writes
    │   └── automation.py            ← decision engine (thresholds → commands)
    └── routers/
        ├── __init__.py
        ├── sensors.py               ← REST endpoints for sensor data
        ├── automation.py            ← REST endpoints for events + manual override
        └── camera.py               ← image upload + serve endpoints
```

---

## Technology stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Microcontroller | ESP32 | Hardware nodes connected and publishing |
| Local wireless | ESP-NOW | Leader election built and tested in Thesis 1 |
| Cloud messaging | MQTT / HiveMQ Cloud | TLS on port 8883 |
| Backend | FastAPI + Python | Deployed on Railway in production |
| Database | InfluxDB Cloud | Time-series, 4 measurements |
| Visual ML | EfficientNetB0 | Trained, not yet integrated into backend |
| Numerical ML | Random Forest | Architecture defined, training pending data |
| Frontend | React + Vite + PWA | Not yet built |

---

## Credentials and environment

All credentials live in `.env` — never hardcode them. The `.env` file is
gitignored. Use `.env.example` as the template when setting up a new environment.

Key env variable names (must match exactly):
```
MQTT_BROKER
MQTT_PORT                  (8883 for HiveMQ Cloud TLS)
MQTT_USERNAME_BACKEND      (used by FastAPI backend)
MQTT_PASSWORD_BACKEND
INFLUXDB_URL
INFLUXDB_TOKEN
INFLUXDB_ORG               (case-sensitive: "Tameer")
INFLUXDB_BUCKET            ("tameer")
API_HOST
API_PORT
DEBUG
```

---

## MQTT topic structure

| Topic | Direction | Publisher | Subscriber |
|-------|-----------|-----------|------------|
| `smartplant/zone/{zone_id}/data` | ESP32 → cloud | ESP32 leader | FastAPI backend |
| `smartplant/zone/{zone_id}/actuator/cmd` | cloud → ESP32 | FastAPI backend | Actuator node |
| `smartplant/zone/{zone_id}/actuator/ack` | ESP32 → cloud | Actuator node | FastAPI backend |

The backend subscribes to `smartplant/zone/+/data` (single-level wildcard).
The backend uses `MQTT_USERNAME_BACKEND` credentials.

### MQTT payload format (published by the elected leader)

```json
{
  "zone_id": 1,
  "leader_instance": 1,
  "nodes": [
    { "node_type": "soil",    "instance": 1, "metrics": { "moisture": 45.2, "soil_temp": 22.1 } },
    { "node_type": "weather", "instance": 1, "metrics": { "air_temp": 28.3, "air_humidity": 65.4, "light": 72.0, "air_quality": 35.0 } }
  ]
}
```

---

## InfluxDB measurements

All measurements share the tags `zone_id`, `node_type`, `node_instance`.

| Measurement | Extra tags | Fields |
|-------------|-----------|--------|
| `soil_readings` | — | moisture, soil_temp, dryness_level |
| `air_readings` | — | air_temp, air_humidity, light, air_quality |
| `automation_events` | actuator, action | trigger_reason |
| `irrigation` | — | irrigation_minutes |
| `camera_data` | — | image_url, health_status (Phase 4), confidence (Phase 4) |
| `plant_health` | — | disease_class, confidence, health_score (Phase 4) |

---

## Automation thresholds (radish-optimised, based on connected sensors)

| Trigger | Threshold | Actuator | Action |
|---------|-----------|----------|--------|
| moisture | < 40% | irrigation_valve | irrigate (ET-adjusted minutes) |
| moisture | > 85% | irrigation_valve | off |
| air_temp | > 35°C | fan | on |
| air_temp | < 10°C | heater | on |
| light | < 20% | grow_light | on |

Commands are routed per zone: `smartplant/zone/{zone_id}/actuator/cmd`.

---

## How to run

```bash
# Install dependencies (inside venv)
pip install -r requirements.txt

# Start the backend
uvicorn backend.main:app --reload

# API docs (once backend is running)
open http://localhost:8000/docs
```

---

## Coding conventions

- Python 3.11+
- All env vars read via `os.getenv()` after `load_dotenv()`
- Pydantic v2 for all data models (`model_dump()` not `.dict()`)
- `snake_case` for all variable and function names
- All MQTT callbacks use `paho-mqtt` v2 API (`CallbackAPIVersion.VERSION2`)
- InfluxDB writes use `WritePrecision.SECONDS`
- FastAPI routers use `prefix` and `tags` for clean Swagger docs
- No hardcoded credentials anywhere — ever

---

## Firmware flashing checklist

When flashing a new node, set these defines at the top of the sketch:

| Node | File | Defines to set |
|------|------|----------------|
| Soil node (zone 1) | SoilNode.ino | `ZONE_ID 1`, `NODE_INSTANCE 1` |
| Soil node (zone 2) | SoilNode.ino | `ZONE_ID 2`, `NODE_INSTANCE 1` |
| Weather node | WeatherNode.ino | `ZONE_ID 0`, `NODE_INSTANCE 1` |
| Actuator (zone 1) | ActuatorNode.ino | `ZONE_ID 1` |
| Camera (zone 1) | CamNode.ino | `ZONE_ID 1`, `CAM_INSTANCE 1` |

---

## What NOT to change without discussion

- The MQTT topic structure (`smartplant/zone/...`) — the ESP32 firmware depends on it
- The InfluxDB measurement names and field names — the dashboard queries depend on this
- The `.env` variable names — all services depend on exact spelling
- The Pydantic schema field names in `schemas.py` — they must match what the ESP32 publishes
- The ESP-NOW channel (11) and packet struct layout — all nodes must agree
