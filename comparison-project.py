from fastapi import FastAPI, UploadFile, File, Query
from fastapi.responses import HTMLResponse, FileResponse
import os
import json
import asyncio
import ssl
from datetime import datetime, timezone
from contextlib import asynccontextmanager

import cloudinary
import cloudinary.uploader
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import aiomqtt

# ================== Configuration ==================
INFLUXDB_URL    = os.environ.get("INFLUXDB_URL")
INFLUXDB_TOKEN  = os.environ.get("INFLUXDB_TOKEN")
INFLUXDB_ORG    = os.environ.get("INFLUXDB_ORG")
INFLUXDB_BUCKET = os.environ.get("INFLUXDB_BUCKET")

cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET"),
)

MQTT_BROKER = os.environ.get("MQTT_BROKER")
MQTT_PORT   = int(os.environ.get("MQTT_PORT", "8883"))
MQTT_USER   = os.environ.get("MQTT_USER")
MQTT_PASS   = os.environ.get("MQTT_PASS")
MQTT_TOPIC  = os.environ.get("MQTT_TOPIC", "smartplant/#")

SYNC_WINDOW = 30

# ================== Clients ==================
influx_client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
write_api     = influx_client.write_api(write_options=SYNCHRONOUS)
query_api     = influx_client.query_api()

# ================== Shared weather cache ==================
# Holds the latest weather metrics, shared across all locations
weather_cache: dict = {}


# ================== Helpers ==================
def get_time_window():
    now     = datetime.now(timezone.utc)
    rounded = now.second - (now.second % SYNC_WINDOW)
    return now.replace(second=rounded, microsecond=0)


def write_sensor_data(node_id, node_type, metrics, time_window, location):
    point = Point("sensor_data") \
        .tag("node_id",   str(node_id)) \
        .tag("node_type", node_type) \
        .tag("location",  location) \
        .time(time_window)

    if node_type == "soil":
        moisture  = float(metrics.get("v1", 0))
        soil_temp = float(metrics.get("v2", 0))
        point.field("soil_moisture",    moisture)
        point.field("soil_temperature", soil_temp)
        # Derived dryness level
        if moisture >= 70:
            point.field("dryness_level", "wet")
        elif moisture >= 40:
            point.field("dryness_level", "moderate")
        else:
            point.field("dryness_level", "dry")

    elif node_type == "weather":
        point.field("air_temperature", float(metrics.get("v1", 0)))
        point.field("humidity",        float(metrics.get("v2", 0)))
        point.field("light",           float(metrics.get("v3", 0)))
        point.field("air_quality",     float(metrics.get("v4", 0)))

    write_api.write(bucket=INFLUXDB_BUCKET, record=point)


# ================== Irrigation Recommendation ==================
def compute_irrigation_minutes(soil_metrics: dict, weather_metrics: dict) -> float:
    moisture = float(soil_metrics.get("v1", 50.0))
    air_temp = float(weather_metrics.get("v1", 25.0))
    humidity = float(weather_metrics.get("v2", 50.0))
    light    = float(weather_metrics.get("v3", 50.0))

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
    if air_temp > 35:   et += 0.3
    elif air_temp > 30: et += 0.15
    if humidity < 30:   et += 0.2
    elif humidity < 50: et += 0.1
    if light > 70:      et += 0.1

    return round(base * et, 1)


# ================== MQTT Subscriber ==================
async def mqtt_subscriber():
    tls_ctx = ssl.create_default_context()
    tls_ctx.check_hostname = False
    tls_ctx.verify_mode    = ssl.CERT_NONE
    while True:
        try:
            async with aiomqtt.Client(
                hostname=MQTT_BROKER, port=MQTT_PORT,
                username=MQTT_USER,   password=MQTT_PASS,
                tls_context=tls_ctx,
            ) as mqtt_client:
                await mqtt_client.subscribe(MQTT_TOPIC)
                print(f"MQTT: Subscribed to {MQTT_TOPIC}")

                async for message in mqtt_client.messages:
                    try:
                        topic        = str(message.topic)       # e.g. "smartplant/location1"
                        parts        = topic.split("/")         # ["smartplant", "location1"]
                        if len(parts) < 2:
                            continue
                        location_key = parts[1]                 # "location1", "location2", "weather"

                        # Skip actuator echo messages
                        if "actuator" in topic:
                            continue

                        payload = json.loads(message.payload.decode())
                        tw      = get_time_window()

                        if location_key == "weather":
                            # Shared weather node — store once, cache for all locations
                            for node in payload.get("nodes", []):
                                if node.get("node_type") == "weather":
                                    write_sensor_data(
                                        node_id=node.get("node_id"),
                                        node_type="weather",
                                        metrics=node.get("metrics", {}),
                                        time_window=tw,
                                        location="shared",
                                    )
                                    weather_cache.update(node.get("metrics", {}))
                            print(f"MQTT: Weather data stored (shared)")

                        else:
                            # Location-specific data (location1, location2, etc.)
                            location     = location_key
                            soil_metrics = {}

                            for node in payload.get("nodes", []):
                                write_sensor_data(
                                    node_id=node.get("node_id"),
                                    node_type=node.get("node_type"),
                                    metrics=node.get("metrics", {}),
                                    time_window=tw,
                                    location=location,
                                )
                                if node.get("node_type") == "soil":
                                    soil_metrics = node.get("metrics", {})

                            print(f"MQTT: Stored {len(payload.get('nodes', []))} nodes for {location} at {tw}")

                            # Compute irrigation using this location's soil + shared weather
                            minutes = compute_irrigation_minutes(soil_metrics, weather_cache)

                            # Store irrigation recommendation in InfluxDB
                            irr_point = Point("irrigation") \
                                .tag("location", location) \
                                .field("irrigation_minutes", minutes) \
                                .time(tw)
                            write_api.write(bucket=INFLUXDB_BUCKET, record=irr_point)

                            # Send actuator command to location-specific topic
                            if minutes > 0:
                                cmd = json.dumps({"action": "irrigate", "minutes": minutes})
                                await mqtt_client.publish(
                                    f"smartplant/actuator/{location}", cmd, qos=1
                                )
                                print(f"MQTT: Irrigation command → smartplant/actuator/{location} — {minutes} min")

                    except Exception as e:
                        print(f"MQTT: Processing error: {e}")

        except Exception as e:
            print(f"MQTT: Connection error: {e}, retrying in 5s...")
            await asyncio.sleep(5)


# ================== Lifespan ==================
@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(mqtt_subscriber())
    yield
    task.cancel()


app = FastAPI(lifespan=lifespan)


# ================== Dashboard ==================
@app.get("/")
def dashboard():
    return HTMLResponse("""
    <html>
      <head>
        <title>Smart Planting Dashboard</title>
        <style>
          * { box-sizing: border-box; margin: 0; padding: 0; }
          body { font-family: 'Segoe UI', Arial, sans-serif; background: #0d1117; color: #e6edf3; padding: 24px; }
          h1 { text-align: center; color: #58a6ff; margin-bottom: 8px; }
          #status { text-align: center; color: #8b949e; font-size: 14px; margin-bottom: 16px; }
          .loc-tabs { display: flex; justify-content: center; gap: 12px; margin-bottom: 20px; }
          .loc-tab { padding: 8px 24px; border-radius: 8px; border: 1px solid #30363d; background: #161b22; color: #8b949e; cursor: pointer; font-size: 14px; }
          .loc-tab.active { background: #1f6feb; border-color: #1f6feb; color: #fff; }
          .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; max-width: 1100px; margin: 0 auto; }
          .card { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 20px; }
          .card h3 { color: #3fb950; margin-bottom: 14px; font-size: 16px; }
          img { width: 100%; border-radius: 8px; border: 2px solid #30363d; }
          .metric { display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #21262d; }
          .metric:last-child { border-bottom: none; }
          .label { color: #8b949e; }
          .value { color: #58a6ff; font-weight: 600; }
          .health { text-align: center; padding: 12px; border-radius: 8px; margin-top: 14px; font-size: 18px; font-weight: 600; }
          .healthy { background: #0d2818; color: #3fb950; border: 1px solid #238636; }
          .diseased { background: #3d1114; color: #f85149; border: 1px solid #da3633; }
          .unknown { background: #1c1f24; color: #8b949e; border: 1px solid #30363d; }
          @media (max-width: 768px) { .grid { grid-template-columns: 1fr; } }
        </style>
      </head>
      <body>
        <h1>Smart Planting Dashboard</h1>
        <div class="loc-tabs">
          <button class="loc-tab active" onclick="switchLocation('location1')">Location 1</button>
          <button class="loc-tab"        onclick="switchLocation('location2')">Location 2</button>
        </div>
        <p id="status">Connecting...</p>
        <div class="grid">
          <div class="card">
            <h3>Live Camera Feed</h3>
            <img id="feed" src="/latest/location1.jpg">
            <div id="health" class="health unknown">Waiting for AI analysis...</div>
          </div>
          <div>
            <div class="card" style="margin-bottom:20px;">
              <h3>Soil Sensors</h3>
              <div class="metric"><span class="label">Moisture</span><span class="value" id="soil_moisture">--</span></div>
              <div class="metric"><span class="label">Temperature</span><span class="value" id="soil_temperature">--</span></div>
              <div class="metric"><span class="label">Dryness Level</span><span class="value" id="dryness_level">--</span></div>
              <div class="metric"><span class="label">Irrigation Needed</span><span class="value" id="irrigation_minutes">--</span></div>
            </div>
            <div class="card">
              <h3>Weather Station (Shared)</h3>
              <div class="metric"><span class="label">Air Temperature</span><span class="value" id="air_temperature">--</span></div>
              <div class="metric"><span class="label">Humidity</span><span class="value" id="humidity">--</span></div>
              <div class="metric"><span class="label">Light</span><span class="value" id="light">--</span></div>
              <div class="metric"><span class="label">Air Quality</span><span class="value" id="air_quality">--</span></div>
            </div>
          </div>
        </div>
        <script>
          let currentLocation = 'location1';
          function switchLocation(loc) {
            currentLocation = loc;
            document.querySelectorAll('.loc-tab').forEach((t, i) =>
              t.classList.toggle('active', i === (loc === 'location1' ? 0 : 1)));
            ['soil_moisture','soil_temperature','dryness_level','irrigation_minutes',
             'air_temperature','humidity','light','air_quality'].forEach(id => {
              const el = document.getElementById(id); if (el) el.textContent = '--';
            });
            document.getElementById('feed').src = '/latest/' + loc + '.jpg?t=' + Date.now();
          }
          function refreshImage() {
            const img  = document.getElementById('feed');
            const next = new Image();
            next.onload  = () => { img.src = next.src; setTimeout(refreshImage, 5000); };
            next.onerror = () => { setTimeout(refreshImage, 5000); };
            next.src = '/latest/' + currentLocation + '.jpg?t=' + Date.now();
          }
          function refreshData() {
            fetch('/api/latest?location=' + currentLocation).then(r => r.json()).then(data => {
              document.getElementById('status').textContent = 'Last update: ' + (data.timestamp || 'N/A') + '  |  ' + currentLocation;
              if (data.soil) Object.keys(data.soil).forEach(k => {
                const el = document.getElementById(k); if (el) el.textContent = data.soil[k];
              });
              if (data.weather) Object.keys(data.weather).forEach(k => {
                const el = document.getElementById(k); if (el) el.textContent = data.weather[k];
              });
              const irr = document.getElementById('irrigation_minutes');
              if (irr) irr.textContent = data.irrigation_minutes != null ? data.irrigation_minutes + ' min' : '--';
              if (data.health_status) {
                const h = document.getElementById('health');
                h.textContent = data.health_status + (data.confidence ? ' (' + data.confidence + '%)' : '');
                h.className   = 'health ' + (data.health_status.toLowerCase().includes('healthy') ? 'healthy' : 'diseased');
              }
            }).catch(() => {});
            setTimeout(refreshData, 2000);
          }
          refreshImage();
          refreshData();
        </script>
      </body>
    </html>
    """)


# ================== Image Upload (dynamic location) ==================
@app.post("/upload/{location}")
async def upload_image(location: str, image: UploadFile = File(...)):
    contents   = await image.read()
    tw         = get_time_window()
    local_path = f"latest_{location}.jpg"

    with open(local_path, "wb") as f:
        f.write(contents)

    try:
        result = cloudinary.uploader.upload(
            contents,
            folder="smart_planting",
            public_id=f"{location}_{tw.strftime('%Y%m%d_%H%M%S')}",
            resource_type="image",
        )
        image_url = result.get("secure_url", "")

        point = Point("camera_data") \
            .tag("node_type", "camera") \
            .tag("location",  location) \
            .field("image_url", image_url) \
            .time(tw)
        write_api.write(bucket=INFLUXDB_BUCKET, record=point)

        return {"status": "received", "location": location, "image_url": image_url, "timestamp": str(tw)}
    except Exception as e:
        print(f"Cloudinary/InfluxDB error: {e}")
        return {"status": "received_locally", "error": str(e)}


# ================== Serve Latest Image (dynamic location) ==================
@app.get("/latest/{location}.jpg")
def latest_image(location: str):
    path = f"latest_{location}.jpg"
    if os.path.exists(path):
        return FileResponse(path, media_type="image/jpeg")
    return HTMLResponse("<h2>No image yet for this location</h2>")


# ================== API: Latest Readings ==================
@app.get("/api/latest")
def get_latest_data(location: str = Query(default="location1")):
    try:
        soil_data     = {}
        weather_data  = {}
        timestamp     = None
        image_url     = None
        health_status = None
        confidence    = None

        soil_query = f'''
        from(bucket: "{INFLUXDB_BUCKET}")
          |> range(start: -1h)
          |> filter(fn: (r) => r._measurement == "sensor_data")
          |> filter(fn: (r) => r.node_type == "soil")
          |> filter(fn: (r) => r.location == "{location}")
          |> last()
        '''
        for table in query_api.query(soil_query):
            for record in table.records:
                val = record.get_value()
                soil_data[record.get_field()] = round(val, 2) if isinstance(val, (int, float)) else val
                timestamp = str(record.get_time())

        weather_query = f'''
        from(bucket: "{INFLUXDB_BUCKET}")
          |> range(start: -1h)
          |> filter(fn: (r) => r._measurement == "sensor_data")
          |> filter(fn: (r) => r.node_type == "weather")
          |> filter(fn: (r) => r.location == "shared")
          |> last()
        '''
        for table in query_api.query(weather_query):
            for record in table.records:
                val = record.get_value()
                weather_data[record.get_field()] = round(val, 2) if isinstance(val, (int, float)) else val

        image_query = f'''
        from(bucket: "{INFLUXDB_BUCKET}")
          |> range(start: -24h)
          |> filter(fn: (r) => r._measurement == "camera_data")
          |> filter(fn: (r) => r.location == "{location}")
          |> last()
        '''
        for table in query_api.query(image_query):
            for record in table.records:
                field = record.get_field()
                if field == "image_url":
                    image_url = record.get_value()
                elif field == "health_status":
                    health_status = record.get_value()
                elif field == "confidence":
                    confidence = record.get_value()

        irrigation_minutes = None
        irrigation_query = f'''
        from(bucket: "{INFLUXDB_BUCKET}")
          |> range(start: -1h)
          |> filter(fn: (r) => r._measurement == "irrigation")
          |> filter(fn: (r) => r.location == "{location}")
          |> last()
        '''
        for table in query_api.query(irrigation_query):
            for record in table.records:
                irrigation_minutes = record.get_value()

        return {
            "timestamp":          timestamp,
            "location":           location,
            "soil":               soil_data,
            "weather":            weather_data,
            "image_url":          image_url,
            "health_status":      health_status,
            "confidence":         confidence,
            "irrigation_minutes": irrigation_minutes,
        }
    except Exception as e:
        return {"error": str(e)}


# ================== Debug ==================
@app.get("/debug")
def debug_influx():
    try:
        debug_query = f'''
        from(bucket: "{INFLUXDB_BUCKET}")
          |> range(start: -24h)
          |> filter(fn: (r) => r._measurement == "sensor_data"
                            or r._measurement == "camera_data"
                            or r._measurement == "irrigation")
          |> tail(n: 20)
        '''
        rows = []
        for table in query_api.query(debug_query):
            for record in table.records:
                rows.append({
                    "measurement": record.get_measurement(),
                    "time":        str(record.get_time()),
                    "field":       record.get_field(),
                    "value":       record.get_value(),
                    "tags":        dict(record.values),
                })
        return {"count": len(rows), "records": rows}
    except Exception as e:
        return {"error": str(e)}