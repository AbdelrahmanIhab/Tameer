"""
Tameer — InfluxDB Service
==========================
All reads and writes to InfluxDB Cloud go through this module.

Measurements:
  soil_readings    — per soil node, per timestamp
  air_readings     — per weather node, per timestamp
  automation_events — every actuator command with reason
  plant_health     — ML inference results (Phase 4)
"""

from __future__ import annotations
import os
from datetime import datetime, timezone
from typing import Any

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from dotenv import load_dotenv

load_dotenv()

_URL    = os.getenv("INFLUXDB_URL",    "http://localhost:8086")
_TOKEN  = os.getenv("INFLUXDB_TOKEN", "")
_ORG    = os.getenv("INFLUXDB_ORG",   "Tameer")
_BUCKET = os.getenv("INFLUXDB_BUCKET","tameer")

_client    = InfluxDBClient(url=_URL, token=_TOKEN, org=_ORG)
_write_api = _client.write_api(write_options=SYNCHRONOUS)
_query_api = _client.query_api()


# ── Writes ────────────────────────────────────────────────────────────────────

def write_soil_reading(node_id: int, metrics: dict, timestamp: datetime) -> None:
    point = (
        Point("soil_readings")
        .tag("node_id", str(node_id))
        .time(timestamp, WritePrecision.S)
    )
    for field, value in metrics.items():
        point = point.field(field, float(value))
    _write_api.write(bucket=_BUCKET, record=point)


def write_air_reading(node_id: int, metrics: dict, timestamp: datetime) -> None:
    point = (
        Point("air_readings")
        .tag("node_id", str(node_id))
        .time(timestamp, WritePrecision.S)
    )
    for field, value in metrics.items():
        point = point.field(field, float(value))
    _write_api.write(bucket=_BUCKET, record=point)


def write_automation_event(
    node_id: int,
    actuator: str,
    action: str,
    trigger_reason: str,
    timestamp: datetime | None = None,
) -> None:
    ts = timestamp or datetime.now(timezone.utc)
    point = (
        Point("automation_events")
        .tag("node_id",  str(node_id))
        .tag("actuator", actuator)
        .tag("action",   action)
        .field("trigger_reason", trigger_reason)
        .field("dummy", 1)          # InfluxDB requires ≥1 field
        .time(ts, WritePrecision.S)
    )
    _write_api.write(bucket=_BUCKET, record=point)


# ── Reads ─────────────────────────────────────────────────────────────────────

def query_latest_soil(node_id: int | None = None) -> list[dict]:
    """Return the most recent soil reading per node."""
    filter_clause = f'|> filter(fn: (r) => r["node_id"] == "{node_id}")' if node_id else ""
    flux = f"""
from(bucket: "{_BUCKET}")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "soil_readings")
  {filter_clause}
  |> last()
  |> pivot(rowKey:["_time","node_id"], columnKey: ["_field"], valueColumn: "_value")
"""
    return _run_query(flux)


def query_latest_air(node_id: int | None = None) -> list[dict]:
    """Return the most recent air reading per node."""
    filter_clause = f'|> filter(fn: (r) => r["node_id"] == "{node_id}")' if node_id else ""
    flux = f"""
from(bucket: "{_BUCKET}")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "air_readings")
  {filter_clause}
  |> last()
  |> pivot(rowKey:["_time","node_id"], columnKey: ["_field"], valueColumn: "_value")
"""
    return _run_query(flux)


def query_history(measurement: str, node_id: int, hours: int = 24) -> list[dict]:
    """Return time-series history for a measurement + node."""
    flux = f"""
from(bucket: "{_BUCKET}")
  |> range(start: -{hours}h)
  |> filter(fn: (r) => r["_measurement"] == "{measurement}")
  |> filter(fn: (r) => r["node_id"] == "{node_id}")
  |> pivot(rowKey:["_time","node_id"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"])
"""
    return _run_query(flux)


def query_automation_events(hours: int = 24) -> list[dict]:
    flux = f"""
from(bucket: "{_BUCKET}")
  |> range(start: -{hours}h)
  |> filter(fn: (r) => r["_measurement"] == "automation_events")
  |> pivot(rowKey:["_time","node_id","actuator","action"],
           columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"], desc: true)
"""
    return _run_query(flux)


def _run_query(flux: str) -> list[dict]:
    tables = _query_api.query(flux, org=_ORG)
    rows = []
    for table in tables:
        for record in table.records:
            rows.append(record.values)
    return rows