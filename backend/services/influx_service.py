"""
Tameer — InfluxDB Service
==========================
All reads and writes to InfluxDB Cloud go through this module.

Measurements:
  soil_readings     — per zone / per soil node instance
  air_readings      — per zone / per weather node instance
  automation_events — every actuator command with reason
  irrigation        — computed irrigation minutes per zone
  camera_data       — image URLs per zone / per camera instance

Tags on every measurement: zone_id, node_type, node_instance
"""

from __future__ import annotations
import logging
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Any

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from dotenv import load_dotenv

from backend.services import debug_bus

log = logging.getLogger("tameer.influx")

load_dotenv()

_URL    = os.getenv("INFLUXDB_URL",    "http://localhost:8086")
_TOKEN  = os.getenv("INFLUXDB_TOKEN", "")
_ORG    = os.getenv("INFLUXDB_ORG",   "Tameer")
_BUCKET = os.getenv("INFLUXDB_BUCKET","tameer")

_CAIRO = ZoneInfo("Africa/Cairo")

_client    = InfluxDBClient(url=_URL, token=_TOKEN, org=_ORG)
_write_api = _client.write_api(write_options=SYNCHRONOUS)
_query_api = _client.query_api()


# ── Debug helper ─────────────────────────────────────────────────────────────

def _dbg(trace_id: str, zone_id: int, node_type: str, node_instance: int,
         measurement: str, status: str, exc: Exception | None = None) -> None:
    try:
        detail = (f"{measurement} written ✓" if status == "ok"
                  else f"{measurement} FAILED ✗: {exc}")
        debug_bus.emit({
            "trace_id":      trace_id,
            "ts":            datetime.now(timezone.utc).isoformat(),
            "stage":         "influx_write",
            "zone_id":       zone_id,
            "node_type":     node_type,
            "node_instance": node_instance,
            "status":        status,
            "detail":        detail,
            "extra":         {} if exc is None else {"error": str(exc)},
        })
    except Exception:
        pass


# ── Writes ────────────────────────────────────────────────────────────────────

def write_soil_reading(
    zone_id: int,
    node_instance: int,
    metrics: dict,
    timestamp: datetime,
    trace_id: str = "",
) -> None:
    moisture = metrics.get("moisture", 50.0)
    dryness  = "wet" if moisture >= 70 else ("moderate" if moisture >= 40 else "dry")

    point = (
        Point("soil_readings")
        .tag("zone_id",       str(zone_id))
        .tag("node_type",     "soil")
        .tag("node_instance", str(node_instance))
        .field("dryness_level", dryness)
        .time(timestamp, WritePrecision.S)
    )
    for field, value in metrics.items():
        point = point.field(field, float(value))
    try:
        _write_api.write(bucket=_BUCKET, record=point)
        log.debug("Wrote soil_readings zone=%s instance=%s", zone_id, node_instance)
        _dbg(trace_id, zone_id, "soil", node_instance, "soil_readings", "ok")
    except Exception as exc:
        log.error("InfluxDB write failed (soil): %s", exc)
        _dbg(trace_id, zone_id, "soil", node_instance, "soil_readings", "error", exc)


def write_air_reading(
    zone_id: int,
    node_instance: int,
    metrics: dict,
    timestamp: datetime,
    trace_id: str = "",
) -> None:
    point = (
        Point("air_readings")
        .tag("zone_id",       str(zone_id))
        .tag("node_type",     "weather")
        .tag("node_instance", str(node_instance))
        .time(timestamp, WritePrecision.S)
    )
    for field, value in metrics.items():
        point = point.field(field, float(value))
    try:
        _write_api.write(bucket=_BUCKET, record=point)
        log.debug("Wrote air_readings zone=%s instance=%s", zone_id, node_instance)
        _dbg(trace_id, zone_id, "weather", node_instance, "air_readings", "ok")
    except Exception as exc:
        log.error("InfluxDB write failed (air): %s", exc)
        _dbg(trace_id, zone_id, "weather", node_instance, "air_readings", "error", exc)


def write_automation_event(
    zone_id: int,
    actuator: str,
    action: str,
    trigger_reason: str,
    timestamp: datetime | None = None,
    trace_id: str = "",
) -> None:
    ts = timestamp or datetime.now(_CAIRO)
    point = (
        Point("automation_events")
        .tag("zone_id",  str(zone_id))
        .tag("actuator", actuator)
        .tag("action",   action)
        .field("trigger_reason", trigger_reason)
        .field("dummy", 1)
        .time(ts, WritePrecision.S)
    )
    try:
        _write_api.write(bucket=_BUCKET, record=point)
        _dbg(trace_id, zone_id, "automation", 0, "automation_events", "ok")
    except Exception as exc:
        log.error("InfluxDB write failed (automation_event): %s", exc)
        _dbg(trace_id, zone_id, "automation", 0, "automation_events", "error", exc)


def write_irrigation_reading(
    zone_id: int,
    node_instance: int,
    minutes: float,
    timestamp: datetime | None = None,
    trace_id: str = "",
) -> None:
    ts = timestamp or datetime.now(_CAIRO)
    point = (
        Point("irrigation")
        .tag("zone_id",       str(zone_id))
        .tag("node_type",     "soil")
        .tag("node_instance", str(node_instance))
        .field("irrigation_minutes", float(minutes))
        .time(ts, WritePrecision.S)
    )
    try:
        _write_api.write(bucket=_BUCKET, record=point)
        log.debug("Wrote irrigation zone=%s instance=%s: %.1f min", zone_id, node_instance, minutes)
        _dbg(trace_id, zone_id, "soil", node_instance, f"irrigation ({minutes:.1f} min)", "ok")
    except Exception as exc:
        log.error("InfluxDB write failed (irrigation): %s", exc)
        _dbg(trace_id, zone_id, "soil", node_instance, "irrigation", "error", exc)


def write_camera_data(
    zone_id: int,
    cam_instance: int,
    image_url: str,
    health_status: str | None = None,
    confidence: float | None = None,
    timestamp: datetime | None = None,
    trace_id: str = "",
) -> None:
    ts = timestamp or datetime.now(_CAIRO)
    point = (
        Point("camera_data")
        .tag("zone_id",       str(zone_id))
        .tag("node_type",     "camera")
        .tag("node_instance", str(cam_instance))
        .field("image_url", image_url)
        .time(ts, WritePrecision.S)
    )
    if health_status is not None:
        point = point.field("health_status", health_status)
    if confidence is not None:
        point = point.field("confidence", float(confidence))
    try:
        _write_api.write(bucket=_BUCKET, record=point)
        log.debug("Wrote camera_data zone=%s instance=%s", zone_id, cam_instance)
        _dbg(trace_id, zone_id, "camera", cam_instance, "camera_data", "ok")
    except Exception as exc:
        log.error("InfluxDB write failed (camera): %s", exc)
        _dbg(trace_id, zone_id, "camera", cam_instance, "camera_data", "error", exc)


# ── Reads ─────────────────────────────────────────────────────────────────────

def query_latest_soil(zone_id: int | None = None) -> list[dict]:
    filter_clause = f'|> filter(fn: (r) => r["zone_id"] == "{zone_id}")' if zone_id is not None else ""
    flux = f"""
from(bucket: "{_BUCKET}")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "soil_readings")
  {filter_clause}
  |> last()
  |> pivot(rowKey:["_time","zone_id","node_instance"], columnKey: ["_field"], valueColumn: "_value")
"""
    return _run_query(flux)


def query_latest_air(zone_id: int | None = None) -> list[dict]:
    filter_clause = f'|> filter(fn: (r) => r["zone_id"] == "{zone_id}")' if zone_id is not None else ""
    flux = f"""
from(bucket: "{_BUCKET}")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "air_readings")
  {filter_clause}
  |> last()
  |> pivot(rowKey:["_time","zone_id","node_instance"], columnKey: ["_field"], valueColumn: "_value")
"""
    return _run_query(flux)


def query_history(measurement: str, zone_id: int, hours: int = 24) -> list[dict]:
    flux = f"""
from(bucket: "{_BUCKET}")
  |> range(start: -{hours}h)
  |> filter(fn: (r) => r["_measurement"] == "{measurement}")
  |> filter(fn: (r) => r["zone_id"] == "{zone_id}")
  |> pivot(rowKey:["_time","zone_id","node_instance"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"])
"""
    return _run_query(flux)


def query_automation_events(hours: int = 24) -> list[dict]:
    flux = f"""
from(bucket: "{_BUCKET}")
  |> range(start: -{hours}h)
  |> filter(fn: (r) => r["_measurement"] == "automation_events")
  |> pivot(rowKey:["_time","zone_id","actuator","action"],
           columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"], desc: true)
"""
    return _run_query(flux)


def query_latest_irrigation(zone_id: int | None = None) -> list[dict]:
    filter_clause = f'|> filter(fn: (r) => r["zone_id"] == "{zone_id}")' if zone_id is not None else ""
    flux = f"""
from(bucket: "{_BUCKET}")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "irrigation")
  {filter_clause}
  |> last()
  |> pivot(rowKey:["_time","zone_id","node_instance"], columnKey: ["_field"], valueColumn: "_value")
"""
    return _run_query(flux)


def query_latest_all(zone_id: int | None = None) -> dict:
    soil_rows = query_latest_soil(zone_id=zone_id)
    air_rows  = query_latest_air()

    zone_filter = f'|> filter(fn: (r) => r["zone_id"] == "{zone_id}")' if zone_id is not None else ""
    camera_flux = f"""
from(bucket: "{_BUCKET}")
  |> range(start: -24h)
  |> filter(fn: (r) => r["_measurement"] == "camera_data")
  {zone_filter}
  |> last()
  |> pivot(rowKey:["_time","zone_id","node_instance"], columnKey: ["_field"], valueColumn: "_value")
"""
    camera_rows = _run_query(camera_flux)
    irr_rows    = query_latest_irrigation(zone_id=zone_id)

    camera = camera_rows[0] if camera_rows else {}
    return {
        "timestamp":          str(soil_rows[0].get("_time", "")) if soil_rows else None,
        "soil":               soil_rows[0] if soil_rows else None,
        "weather":            air_rows[0]  if air_rows  else None,
        "image_url":          camera.get("image_url"),
        "health_status":      camera.get("health_status"),
        "confidence":         camera.get("confidence"),
        "irrigation_minutes": irr_rows[0].get("irrigation_minutes") if irr_rows else None,
    }


def query_debug_records(limit: int = 20) -> list[dict]:
    flux = f"""
from(bucket: "{_BUCKET}")
  |> range(start: -24h)
  |> filter(fn: (r) => r["_measurement"] == "soil_readings"
         or r["_measurement"] == "air_readings"
         or r["_measurement"] == "camera_data"
         or r["_measurement"] == "irrigation")
  |> tail(n: {limit})
"""
    rows = []
    tables = _query_api.query(flux, org=_ORG)
    for table in tables:
        for record in table.records:
            rows.append({
                "measurement": record.get_measurement(),
                "time":        str(record.get_time()),
                "field":       record.get_field(),
                "value":       record.get_value(),
                "tags":        {k: v for k, v in record.values.items()
                                if k not in ("_start", "_stop", "_time", "_value", "_field", "_measurement")},
            })
    return rows


def _run_query(flux: str) -> list[dict]:
    try:
        tables = _query_api.query(flux, org=_ORG)
        rows = []
        for table in tables:
            for record in table.records:
                rows.append(record.values)
        return rows
    except Exception as exc:
        log.error("InfluxDB query failed: %s", exc)
        return []
