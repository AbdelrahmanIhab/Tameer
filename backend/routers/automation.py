"""
Tameer — Automation Router
===========================
GET  /automation/events          — log of all recent automation commands
POST /automation/command         — manual actuator override from the engineer dashboard
"""

from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Literal

from backend.services import influx_service
from backend.services.mqtt_service import publish_command

router = APIRouter(prefix="/automation", tags=["Automation"])


class ManualCommandRequest(BaseModel):
    target_node: int
    actuator: Literal[
        "irrigation_valve", "fertilizer_pump",
        "fan", "heater", "grow_light", "shade", "spray_nozzle",
    ]
    action: Literal["on", "off"]


@router.get("/events")
async def get_automation_events(hours: int = 24):
    """Return the automation event log."""
    events = influx_service.query_automation_events(hours=hours)
    return {"status": "ok", "count": len(events), "events": events}


@router.post("/command")
async def send_manual_command(body: ManualCommandRequest):
    """
    Engineer dashboard: manually override an actuator.
    The command is published to MQTT and logged in InfluxDB.
    """
    cmd = {
        "command_id":     "manual",
        "target_node":    body.target_node,
        "actuator":       body.actuator,
        "action":         body.action,
        "trigger_reason": "manual override from engineer dashboard",
        "timestamp":      datetime.now(timezone.utc).isoformat(),
    }
    publish_command(cmd)
    influx_service.write_automation_event(
        node_id=body.target_node,
        actuator=body.actuator,
        action=body.action,
        trigger_reason=cmd["trigger_reason"],
    )
    return {"status": "ok", "command": cmd}