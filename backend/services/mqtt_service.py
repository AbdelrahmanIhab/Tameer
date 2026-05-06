"""
Tameer — MQTT Service
======================
• Subscribes to smartplant/zone/+/data on HiveMQ Cloud
• Parses the zone aggregate payload (ZonePayload)
• Fans out each node reading to InfluxDB
• Runs the automation engine per soil and weather reading
• Publishes actuator commands to smartplant/zone/{zone_id}/actuator/cmd
"""

from __future__ import annotations
import json
import logging
import os
import ssl
import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import paho.mqtt.client as mqtt
from pydantic import ValidationError
from dotenv import load_dotenv

from backend.models.schemas import ZonePayload, SoilMetrics, AirMetrics
from backend.services import influx_service, automation, debug_bus

load_dotenv()

log = logging.getLogger("tameer.mqtt")

BROKER   = os.getenv("MQTT_BROKER",           "broker.hivemq.com")
PORT     = int(os.getenv("MQTT_PORT",         "1883"))
USERNAME = os.getenv("MQTT_USERNAME_BACKEND", "")
PASSWORD = os.getenv("MQTT_PASSWORD_BACKEND", "")

SUBSCRIBE_TOPIC = "smartplant/zone/+/data"
COMMAND_TOPIC   = "smartplant/zone/{zone_id}/actuator/cmd"

_mqtt_client: mqtt.Client | None = None
_CAIRO = ZoneInfo("Africa/Cairo")

# Latest weather metrics cached in memory for irrigation ET adjustment
_weather_cache: dict = {}


# ── Publish helper (called by automation engine) ──────────────────────────────
def publish_command(cmd: dict) -> None:
    if _mqtt_client is None:
        log.warning("MQTT client not ready — command not sent: %s", cmd)
        return
    topic = COMMAND_TOPIC.format(zone_id=cmd["zone_id"])
    _mqtt_client.publish(topic, json.dumps(cmd), qos=1)
    log.debug("Published command → %s : %s", topic, cmd)


# ── Message handler ───────────────────────────────────────────────────────────
def _on_message(client, userdata, msg: mqtt.MQTTMessage) -> None:
    topic = msg.topic
    try:
        raw = json.loads(msg.payload.decode())
    except json.JSONDecodeError:
        log.warning("Non-JSON payload on %s — ignored", topic)
        return

    # Skip our own command and ack topics echoed back
    if "actuator" in topic:
        return

    try:
        payload = ZonePayload(**raw)
    except ValidationError as exc:
        log.warning("ZonePayload validation failed on %s:\n%s", topic, exc)
        return

    ts = datetime.now(_CAIRO)
    zone_id = payload.zone_id
    trace_id = uuid.uuid4().hex[:8]

    try:
        debug_bus.emit({
            "trace_id": trace_id,
            "ts": ts.isoformat(),
            "stage": "mqtt_received",
            "zone_id": zone_id,
            "node_type": "zone",
            "node_instance": payload.leader_instance,
            "status": "ok",
            "detail": (f"zone={zone_id} leader={payload.leader_instance} "
                       f"nodes={len(payload.nodes)}: "
                       f"{', '.join(f'{n.node_type}#{n.instance}' for n in payload.nodes)}"),
            "extra": {"nodes": [{"type": n.node_type, "instance": n.instance} for n in payload.nodes]},
        })
    except Exception:
        pass

    for node in payload.nodes:
        if node.node_type == "soil":
            _handle_soil(node, zone_id, ts, trace_id)
        elif node.node_type == "weather":
            _handle_weather(node, zone_id, ts, trace_id)


def _handle_soil(node, zone_id: int, ts: datetime, trace_id: str = "") -> None:
    metrics: SoilMetrics = node.metrics
    m = metrics.model_dump()

    try:
        debug_bus.emit({
            "trace_id": trace_id,
            "ts": ts.isoformat(),
            "stage": "processing",
            "zone_id": zone_id,
            "node_type": "soil",
            "node_instance": node.instance,
            "status": "ok",
            "detail": f"moisture={metrics.moisture:.1f}%  soil_temp={metrics.soil_temp:.1f}°C",
            "extra": m,
        })
    except Exception:
        pass

    influx_service.write_soil_reading(
        zone_id=zone_id,
        node_instance=node.instance,
        metrics=m,
        timestamp=ts,
        trace_id=trace_id,
    )
    log.info("✅ Soil  zone=%d inst=%d  moisture=%.1f%%  temp=%.1f°C",
             zone_id, node.instance, metrics.moisture, metrics.soil_temp)

    automation.evaluate_soil(
        metrics=m,
        zone_id=zone_id,
        publish_fn=publish_command,
        write_event_fn=influx_service.write_automation_event,
        trace_id=trace_id,
    )

    irr_minutes = automation.compute_irrigation_minutes(
        moisture=m["moisture"],
        air_temp=_weather_cache.get("air_temp",    25.0),
        humidity=_weather_cache.get("air_humidity", 50.0),
        light=_weather_cache.get("light",           50.0),
    )
    influx_service.write_irrigation_reading(
        zone_id=zone_id,
        node_instance=node.instance,
        minutes=irr_minutes,
        timestamp=ts,
        trace_id=trace_id,
    )


def _handle_weather(node, zone_id: int, ts: datetime, trace_id: str = "") -> None:
    metrics: AirMetrics = node.metrics
    m = metrics.model_dump()
    _weather_cache.update(m)

    try:
        debug_bus.emit({
            "trace_id": trace_id,
            "ts": ts.isoformat(),
            "stage": "processing",
            "zone_id": zone_id,
            "node_type": "weather",
            "node_instance": node.instance,
            "status": "ok",
            "detail": (f"air_temp={metrics.air_temp:.1f}°C  "
                       f"humidity={metrics.air_humidity:.1f}%  "
                       f"light={metrics.light:.1f}%"),
            "extra": m,
        })
    except Exception:
        pass

    influx_service.write_air_reading(
        zone_id=zone_id,
        node_instance=node.instance,
        metrics=m,
        timestamp=ts,
        trace_id=trace_id,
    )
    log.info("✅ Air   zone=%d inst=%d  temp=%.1f°C  hum=%.1f%%  light=%.1f%%",
             zone_id, node.instance, metrics.air_temp, metrics.air_humidity, metrics.light)

    automation.evaluate_weather(
        metrics=m,
        zone_id=zone_id,
        publish_fn=publish_command,
        write_event_fn=influx_service.write_automation_event,
        trace_id=trace_id,
    )


# ── Connection callbacks ──────────────────────────────────────────────────────
def _on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0:
        client.subscribe(SUBSCRIBE_TOPIC, qos=1)
        log.info("Connected to MQTT broker, subscribed to %s", SUBSCRIBE_TOPIC)
    else:
        log.error("MQTT connection failed — reason code %s", reason_code)


def _on_disconnect(client, userdata, flags, reason_code, properties=None):
    if reason_code != 0:
        log.warning("Unexpected MQTT disconnect (rc=%s) — will auto-reconnect", reason_code)


# ── Lifecycle ─────────────────────────────────────────────────────────────────
def start() -> None:
    global _mqtt_client
    _mqtt_client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id="tameer-backend",
    )
    _mqtt_client.on_connect    = _on_connect
    _mqtt_client.on_disconnect = _on_disconnect
    _mqtt_client.on_message    = _on_message

    if USERNAME:
        _mqtt_client.username_pw_set(USERNAME, PASSWORD)
    if PORT == 8883:
        _mqtt_client.tls_set(tls_version=ssl.PROTOCOL_TLS_CLIENT)

    _mqtt_client.connect_async(BROKER, PORT, keepalive=60)
    _mqtt_client.loop_start()
    log.info("MQTT service started — connecting to %s:%d", BROKER, PORT)


def stop() -> None:
    if _mqtt_client:
        _mqtt_client.loop_stop()
        _mqtt_client.disconnect()
        log.info("MQTT service stopped.")
