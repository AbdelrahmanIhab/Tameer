# Tameer — Backend + Simulator

## Project structure

```
tameer/
├── simulator/
│   └── simulator.py        ← mimics ESP32 nodes publishing to HiveMQ
├── backend/
│   ├── main.py             ← FastAPI entry point
│   ├── models/
│   │   └── schemas.py      ← Pydantic payload models + validation
│   ├── services/
│   │   ├── mqtt_service.py ← MQTT subscriber + publisher
│   │   ├── influx_service.py ← InfluxDB reads & writes
│   │   └── automation.py   ← decision engine (thresholds → commands)
│   └── routers/
│       ├── sensors.py      ← REST endpoints for sensor data
│       └── automation.py   ← REST endpoints for events & manual override
├── requirements.txt
└── .env.example
```

---

## 1. Setup

```bash
# Clone / open the project, then:
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Copy env template and fill in your credentials
cp .env.example .env
```

Fill in `.env`:
- **HiveMQ Cloud** — create a free cluster at hivemq.com, copy host / username / password
- **InfluxDB Cloud** — create a free org at cloud2.influxdata.com, create a bucket called `tameer`, generate an API token

---

## 2. Run the backend

```bash
# From the tameer/ directory:
uvicorn backend.main:app --reload --port 8000
```

Open **http://localhost:8000/docs** — full interactive Swagger UI.

---

## 3. Run the simulator (in a second terminal)

```bash
# Normal mode — realistic radish readings
python simulator/simulator.py

# Inject a fault scenario to test automation triggers
python simulator/simulator.py --scenario drought
python simulator/simulator.py --scenario overwater
python simulator/simulator.py --scenario heat
python simulator/simulator.py --scenario npk_deficient

# Faster publishing for quick testing
python simulator/simulator.py --interval 3
```

---

## 4. REST API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Health check |
| GET | `/docs` | Swagger UI |
| GET | `/sensors/soil/latest` | Latest soil reading (all nodes) |
| GET | `/sensors/soil/latest/{node_id}` | Latest soil reading (one node) |
| GET | `/sensors/air/latest` | Latest air reading (all nodes) |
| GET | `/sensors/air/latest/{node_id}` | Latest air reading (one node) |
| GET | `/sensors/history/{node_id}?measurement=soil_readings&hours=24` | Time-series history |
| GET | `/automation/events?hours=24` | Automation event log |
| POST | `/automation/command` | Manual actuator override |

---

## 5. How data flows

```
simulator.py
  └─ publishes JSON → HiveMQ (smartplant/soilnode1, smartplant/weathernode1)
       └─ mqtt_service.py subscribes
            ├─ validates with Pydantic schemas
            ├─ influx_service.py writes to InfluxDB
            └─ automation.py evaluates thresholds
                 ├─ logs event to InfluxDB
                 └─ publishes command → HiveMQ (smartplant/commands/<node_id>)
                      └─ (ESP32 will subscribe here when hardware arrives)
```

---

## 6. Testing the automation engine

Run with the drought scenario and watch the backend log:

```
python simulator/simulator.py --scenario drought --interval 3
```

You should see the backend log lines like:
```
10:42:15  INFO  tameer.mqtt — ✅ Soil  node=1  moisture=18.3%  pH=6.51  temp=35.1°C
10:42:15  INFO  tameer.automation — 🤖 AUTOMATION  irrigation_valve → on [a3f1b2c4]  reason: moisture=18.3% < 40.0%
```
