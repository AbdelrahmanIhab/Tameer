"""
Tameer — Sensor Data Router
============================
REST endpoints served to the dashboard.

GET /sensors/latest                   — unified snapshot for all zones
GET /sensors/latest?zone_id={id}      — unified snapshot for one zone
GET /sensors/soil/latest              — latest reading from all zones
GET /sensors/soil/latest/{zone_id}    — latest reading from a specific zone
GET /sensors/air/latest               — latest reading from all zones
GET /sensors/air/latest/{zone_id}     — latest reading from a specific zone
GET /sensors/history/{zone_id}        — time-series history (query params: measurement, hours)
"""

from fastapi import APIRouter, HTTPException, Query
from backend.services import influx_service

router = APIRouter(prefix="/sensors", tags=["Sensors"])


@router.get("/latest")
async def get_latest_all(
    zone_id: int | None = Query(None, description="Filter by zone ID"),
):
    """Unified snapshot: latest soil + weather + camera image + irrigation minutes."""
    return influx_service.query_latest_all(zone_id=zone_id)


@router.get("/soil/latest")
async def get_latest_soil_all():
    """Latest soil reading across all zones."""
    data = influx_service.query_latest_soil()
    if not data:
        raise HTTPException(status_code=404, detail="No soil data available yet.")
    return {"status": "ok", "data": data}


@router.get("/soil/latest/{zone_id}")
async def get_latest_soil(zone_id: int):
    """Latest soil reading for a specific zone."""
    data = influx_service.query_latest_soil(zone_id=zone_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"No data for soil zone {zone_id}.")
    return {"status": "ok", "zone_id": zone_id, "data": data[0]}


@router.get("/air/latest")
async def get_latest_air_all():
    """Latest air/weather reading across all zones."""
    data = influx_service.query_latest_air()
    if not data:
        raise HTTPException(status_code=404, detail="No air data available yet.")
    return {"status": "ok", "data": data}


@router.get("/air/latest/{zone_id}")
async def get_latest_air(zone_id: int):
    """Latest air/weather reading for a specific zone."""
    data = influx_service.query_latest_air(zone_id=zone_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"No data for air zone {zone_id}.")
    return {"status": "ok", "zone_id": zone_id, "data": data[0]}


@router.get("/history/{zone_id}")
async def get_history(
    zone_id: int,
    measurement: str = Query("soil_readings",
                             description="soil_readings | air_readings"),
    hours: int       = Query(24, ge=1, le=168,
                             description="How many hours back (max 168 = 7 days)"),
):
    """Time-series history for a zone."""
    if measurement not in ("soil_readings", "air_readings"):
        raise HTTPException(status_code=400,
                            detail="measurement must be soil_readings or air_readings")
    data = influx_service.query_history(measurement, zone_id, hours)
    return {
        "status":      "ok",
        "zone_id":     zone_id,
        "measurement": measurement,
        "hours":       hours,
        "count":       len(data),
        "data":        data,
    }
