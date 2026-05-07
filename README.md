# Tameer — IoT Agricultural Monitoring System

Tameer (تعمير) is a low-cost IoT system for Egyptian farmers. ESP32 sensor nodes monitor soil and air conditions, a FastAPI backend processes data and drives automation, and a bilingual (Arabic/English) React PWA presents the dashboard.

---

## Project structure

```
tameer/
├── Procfile                    ← Railway backend start command
├── runtime.txt                 ← Python 3.12 pin
├── requirements.txt
├── firmware/                   ← Arduino sketches for ESP32 nodes
│   ├── SoilNode/
│   ├── WeatherNode/
│   ├── ActuatorNode/
│   └── CamNode/
├── backend/
│   ├── main.py                 ← FastAPI entry point
│   ├── models/schemas.py       ← Pydantic payload models + validation
│   ├── services/
│   │   ├── mqtt_service.py     ← MQTT subscriber + publisher
│   │   ├── influx_service.py   ← InfluxDB reads & writes
│   │   ├── automation.py       ← decision engine (thresholds → commands)
│   │   └── debug_bus.py        ← in-memory SSE event bus
│   └── routers/
│       ├── sensors.py          ← REST endpoints for sensor data
│       ├── automation.py       ← REST endpoints for events & manual override
│       ├── camera.py           ← image upload + serve endpoints
│       └── debug.py            ← developer debug dashboard (HTML + SSE)
├── tameer-pwa/                 ← React + Vite PWA (separate Railway service)
│   ├── railway.json
│   ├── src/
│   │   ├── pages/              ← FarmerView, EngineerView
│   │   ├── components/         ← farmer/, engineer/, shared/
│   │   ├── hooks/              ← React Query data-fetching hooks
│   │   ├── api/                ← axios client + typed endpoint helpers
│   │   ├── i18n/               ← ar.json + en.json translations
│   │   └── types/api.ts        ← TypeScript types
│   └── dist/                   ← production build output
└── .env.example
```

---

## 1. Backend setup

```bash
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env   # fill in credentials
```

Fill in `.env`:
- **HiveMQ Cloud** — host / username / password from hivemq.com
- **InfluxDB Cloud** — URL, token, org (`Tameer`), bucket (`tameer`)

---

## 2. Run the backend

```bash
uvicorn backend.main:app --reload --port 8000
```

- Swagger UI: **http://localhost:8000/docs**
- Debug dashboard: **http://localhost:8000/debug** (live SSE event stream)

---

## 3. Frontend PWA setup

```bash
cd tameer-pwa
cp .env.example .env          # set VITE_API_URL to the backend URL
npm install
npm run dev                   # dev server → http://localhost:5173
npm run build                 # production build → dist/
```

---

## 4. REST API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Health check |
| GET | `/docs` | Swagger UI |
| GET | `/sensors/soil/latest` | Latest soil reading (all zones) |
| GET | `/sensors/soil/latest/{zone_id}` | Latest soil reading (one zone) |
| GET | `/sensors/air/latest` | Latest air reading (all zones) |
| GET | `/sensors/air/latest/{zone_id}` | Latest air reading (one zone) |
| GET | `/sensors/history/{zone_id}?measurement=soil_readings&hours=24` | Time-series history |
| GET | `/automation/events?hours=24` | Automation event log |
| POST | `/automation/command` | Manual actuator override |
| POST | `/camera/upload` | Upload image from ESP32-CAM |
| GET | `/camera/image/{filename}` | Serve stored image |
| GET | `/debug` | Developer debug dashboard (HTML) |
| GET | `/debug/stream` | SSE stream of pipeline events |

---

## 5. How data flows

```
ESP32 leader node
  └─ publishes JSON → HiveMQ (smartplant/zone/{zone_id}/data)
       └─ mqtt_service.py subscribes
            ├─ validates with Pydantic schemas
            ├─ influx_service.py writes to InfluxDB
            └─ automation.py evaluates thresholds
                 ├─ logs event to InfluxDB
                 └─ publishes command → HiveMQ (smartplant/zone/{zone_id}/actuator/cmd)
                      └─ Actuator node subscribes and actuates
```

---

## 6. Deployment (Railway)

**Backend service** — root of repo, uses `Procfile`:
```
web: uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

**Frontend service** — `tameer-pwa/` subdirectory, uses `railway.json`:
- Build: `npm install --include=dev && npm run build`
- Start: `serve -s dist -l $PORT`

Set `VITE_API_URL` in the frontend Railway service's environment variables to point at the deployed backend URL.
