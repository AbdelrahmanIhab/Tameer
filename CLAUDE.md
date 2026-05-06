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

## Project structure

```
tameer/
├── CLAUDE.md                        ← you are here
├── README.md                        ← human-readable setup guide
├── .env                             ← credentials (never commit)
├── .gitignore
├── requirements.txt
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
        └── automation.py            ← REST endpoints for events + manual override
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
| `smartplant/soilnode1` | ESP32 → cloud | ESP32 leader | FastAPI backend |
| `smartplant/weathernode1` | ESP32 → cloud | ESP32 leader | FastAPI backend |
| `smartplant/commands/<node_id>` | cloud → ESP32 | FastAPI backend | ESP32 leader |

The backend uses `MQTT_USERNAME_BACKEND` credentials.

---

## InfluxDB measurements

| Measurement | Tags | Fields |
|-------------|------|--------|
| `soil_readings` | node_id | moisture, soil_temp, ec, ph, nitrogen, phosphorus, potassium |
| `air_readings` | node_id | air_temp, air_humidity, pressure, light, rain, wind_speed, wind_direction, uv_index, air_quality |
| `automation_events` | node_id, actuator, action | trigger_reason |
| `plant_health` | node_id | disease_class, confidence, health_score (Phase 4) |

---

## Automation thresholds (radish-optimised)

| Trigger | Threshold | Actuator | Action |
|---------|-----------|----------|--------|
| moisture | < 40% | irrigation_valve | on |
| moisture | > 85% | irrigation_valve | off |
| rain | == 1 | irrigation_valve | off |
| nitrogen | < 80 mg/kg | fertilizer_pump | on |
| phosphorus | < 20 mg/kg | fertilizer_pump | on |
| potassium | < 80 mg/kg | fertilizer_pump | on |
| air_temp | > 35°C | fan | on |
| air_temp | < 10°C | heater | on |
| light | < 200 ADC | grow_light | on |
| uv_index | > 8 | shade | on |
| wind_speed | > 15 m/s | shade | on |

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

## What NOT to change without discussion

- The MQTT topic structure (`smartplant/...`) — the ESP32 firmware will depend on this
- The InfluxDB measurement names and field names — the dashboard queries depend on this
- The `.env` variable names — all services depend on exact spelling
- The Pydantic schema field names — they must match what the ESP32 publishes
