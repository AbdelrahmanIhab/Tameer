"""
Tameer — MQTT Service
======================
• Subscribes to smartplant/# on HiveMQ Cloud
• Parses and validates every incoming payload (Pydantic)
• Writes clean readings to InfluxDB
• Passes metrics to the automation engine
• Publishes actuator commands back on smartplant/commands/<node_id>
"""

from __future__ import annotations
import json
import logging
import os
import ssl
from datetime import timezone

import paho.mqtt.client as mqtt
from pydantic import ValidationError
from dotenv import load_dotenv

from backend.models.schemas import SoilPayload, WeatherPayload
from backend.services import influx_service, automation

load_dotenv()

log = logging.getLogger("tameer.mqtt")

BROKER   = os.getenv("MQTT_BROKER",           "broker.hivemq.com")
PORT     = int(os.getenv("MQTT_PORT",         "1883"))
USERNAME = os.getenv("MQTT_USERNAME_BACKEND", "")
PASSWORD = os.getenv("MQTT_PASSWORD_BACKEND", "")

SUBSCRIBE_TOPIC  = "smartplant/#"
COMMAND_TOPIC    = "smartplant/commands/{node_id}"

_mqtt_client: mqtt.Client | None = None

# Latest weather metrics cached in memory so irrigation can use them without a DB round-trip
_weather_cache: dict = {}


# ── Publish helper (called by automation engine) ──────────────────────────────
def publish_command(cmd: dict) -> None:
    if _mqtt_client is None:
        log.warning("MQTT client not ready — command not sent: %s", cmd)
        return
    topic = COMMAND_TOPIC.format(node_id=cmd["target_node"])
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

    node_type = raw.get("node_type")

    if node_type == "soil":
        _handle_soil(raw)
    elif node_type == "weather":
        _handle_weather(raw)
    else:
        log.debug("Unknown node_type '%s' on %s — skipped", node_type, topic)


def _handle_soil(raw: dict) -> None:
    try:
        payload = SoilPayload(**raw)
    except ValidationError as exc:
        log.warning("Soil payload validation failed:\n%s", exc)
        return

    ts = payload.timestamp.replace(tzinfo=timezone.utc) if payload.timestamp.tzinfo is None \
        else payload.timestamp

    metrics = payload.metrics.model_dump()
    influx_service.write_soil_reading(
        node_id=payload.node_id,
        metrics=metrics,
        timestamp=ts,
    )
    log.info("✅ Soil  node=%d  moisture=%.1f%%  pH=%.2f  temp=%.1f°C",
             payload.node_id,
             payload.metrics.moisture,
             payload.metrics.ph,
             payload.metrics.soil_temp)

    automation.evaluate_soil(
        metrics=metrics,
        node_id=payload.node_id,
        publish_fn=publish_command,
        write_event_fn=influx_service.write_automation_event,
    )

    irr_minutes = automation.compute_irrigation_minutes(
        moisture=metrics["moisture"],
        air_temp=_weather_cache.get("air_temp", 25.0),
        humidity=_weather_cache.get("air_humidity", 50.0),
        light=_weather_cache.get("light", 500.0),
    )
    influx_service.write_irrigation_reading(
        node_id=payload.node_id,
        minutes=irr_minutes,
        timestamp=ts,
    )


def _handle_weather(raw: dict) -> None:
    try:
        payload = WeatherPayload(**raw)
    except ValidationError as exc:
        log.warning("Weather payload validation failed:\n%s", exc)
        return

    ts = payload.timestamp.replace(tzinfo=timezone.utc) if payload.timestamp.tzinfo is None \
        else payload.timestamp

    air_metrics = payload.metrics.model_dump()
    _weather_cache.update(air_metrics)

    influx_service.write_air_reading(
        node_id=payload.node_id,
        metrics=air_metrics,
        timestamp=ts,
    )
    log.info("✅ Air   node=%d  temp=%.1f°C  hum=%.1f%%  UV=%.1f",
             payload.node_id,
             payload.metrics.air_temp,
             payload.metrics.air_humidity,
             payload.metrics.uv_index)

    automation.evaluate_weather(
        metrics=air_metrics,
        node_id=payload.node_id,
        publish_fn=publish_command,
        write_event_fn=influx_service.write_automation_event,
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
