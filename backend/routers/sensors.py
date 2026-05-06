"""
Tameer — Sensor Data Router
============================
REST endpoints served to the dashboard.

GET /sensors/soil/latest              — latest reading from all soil nodes
GET /sensors/soil/latest/{node_id}    — latest reading from a specific node
GET /sensors/air/latest               — latest reading from all air nodes
GET /sensors/air/latest/{node_id}     — latest reading from a specific node
GET /sensors/history/{node_id}        — time-series history (query params: measurement, hours)
"""

from fastapi import APIRouter, HTTPException, Query
from backend.services import influx_service

router = APIRouter(prefix="/sensors", tags=["Sensors"])


@router.get("/latest")
async def get_latest_all(
    node_id: int | None = Query(None, description="Filter by node ID"),
):
    """Unified snapshot: latest soil + weather + camera image + plant health + irrigation minutes."""
    return influx_service.query_latest_all(node_id=node_id)


@router.get("/soil/latest")
async def get_latest_soil_all():
    """Latest soil reading across all nodes."""
    data = influx_service.query_latest_soil()
    if not data:
        raise HTTPException(status_code=404, detail="No soil data available yet.")
    return {"status": "ok", "data": data}


@router.get("/soil/latest/{node_id}")
async def get_latest_soil(node_id: int):
    """Latest soil reading for a specific node."""
    data = influx_service.query_latest_soil(node_id=node_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"No data for soil node {node_id}.")
    return {"status": "ok", "node_id": node_id, "data": data[0]}


@router.get("/air/latest")
async def get_latest_air_all():
    """Latest air/weather reading across all nodes."""
    data = influx_service.query_latest_air()
    if not data:
        raise HTTPException(status_code=404, detail="No air data available yet.")
    return {"status": "ok", "data": data}


@router.get("/air/latest/{node_id}")
async def get_latest_air(node_id: int):
    """Latest air/weather reading for a specific node."""
    data = influx_service.query_latest_air(node_id=node_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"No data for air node {node_id}.")
    return {"status": "ok", "node_id": node_id, "data": data[0]}


@router.get("/history/{node_id}")
async def get_history(
    node_id: int,
    measurement: str = Query("soil_readings",
                             description="soil_readings | air_readings"),
    hours: int       = Query(24, ge=1, le=168,
                             description="How many hours back (max 168 = 7 days)"),
):
    """Time-series history for a node."""
    if measurement not in ("soil_readings", "air_readings"):
        raise HTTPException(status_code=400,
                            detail="measurement must be soil_readings or air_readings")
    data = influx_service.query_history(measurement, node_id, hours)
    return {
        "status":      "ok",
        "node_id":     node_id,
        "measurement": measurement,
        "hours":       hours,
        "count":       len(data),
        "data":        data,
    }
