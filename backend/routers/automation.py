"""
Tameer — Automation Router
===========================
GET  /automation/events          — log of all recent automation commands
POST /automation/command         — manual actuator override from the engineer dashboard
"""

from datetime import datetime, timezone
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Literal

from backend.services import influx_service
from backend.services.mqtt_service import publish_command

router = APIRouter(prefix="/automation", tags=["Automation"])


class ManualCommandRequest(BaseModel):
    target_node: int
    actuator: Literal["irrigation_valve"]
    action: Literal["on", "off"]


def _format_event(row: dict) -> dict:
    t = row.get("_time", "")
    return {
        "timestamp":      t.isoformat() if hasattr(t, "isoformat") else str(t),
        "zone_id":        int(row.get("zone_id", 0)),
        "actuator":       row.get("actuator", ""),
        "action":         row.get("action", ""),
        "trigger_reason": row.get("trigger_reason", ""),
    }


@router.get("/events")
async def get_automation_events(hours: int = 24):
    """Return the automation event log."""
    raw = influx_service.query_automation_events(hours=hours)
    events = [_format_event(r) for r in raw]
    return {"status": "ok", "count": len(events), "events": events}


@router.post("/command")
async def send_manual_command(body: ManualCommandRequest):
    """
    Engineer dashboard: manually override the irrigation valve.
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
        zone_id=body.target_node,
        actuator=body.actuator,
        action=body.action,
        trigger_reason=cmd["trigger_reason"],
    )
    return {"status": "ok", "command": cmd}
