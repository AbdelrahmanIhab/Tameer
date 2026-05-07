"""
Tameer — Camera Router
=======================
POST /camera/upload/zone/{zone_id}/camera/{instance}  — ESP32-CAM pushes a JPEG
GET  /camera/zone/{zone_id}/camera/{instance}/latest.jpg — serve most recent image
POST /camera/analyze                                  — manual plant photo → ML diagnose
DELETE /camera/session/{device_id}                   — reset TameerML LSTM session
GET  /camera/debug                                    — last 20 raw InfluxDB records
"""

import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv
from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from backend.services import influx_service, ml_service
from backend.services.mqtt_service import publish_command

load_dotenv()

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
)

router = APIRouter(prefix="/camera", tags=["Camera"])
log = logging.getLogger("tameer.camera")

_CAIRO = ZoneInfo("Africa/Cairo")


def _local_path(zone_id: int, instance: int) -> str:
    return f"latest_zone{zone_id}_cam{instance}.jpg"


@router.post("/upload/zone/{zone_id}/camera/{instance}")
async def upload_image(
    zone_id: int,
    instance: int,
    background_tasks: BackgroundTasks,
    image: UploadFile = File(...),
):
    """Accept a JPEG from the ESP32-CAM; triggers ML analysis in the background."""
    contents   = await image.read()
    ts         = datetime.now(_CAIRO)
    local_path = _local_path(zone_id, instance)
    filename   = image.filename or f"zone{zone_id}_cam{instance}.jpg"

    with open(local_path, "wb") as f:
        f.write(contents)

    image_url = ""
    try:
        result = cloudinary.uploader.upload(
            contents,
            folder="tameer",
            public_id=f"zone{zone_id}_cam{instance}_{ts.strftime('%Y%m%d_%H%M%S')}",
            resource_type="image",
        )
        image_url = result.get("secure_url", "")
        influx_service.write_camera_data(
            zone_id=zone_id,
            cam_instance=instance,
            image_url=image_url,
            timestamp=ts,
        )
    except Exception as exc:
        log.warning("Cloudinary upload failed: %s", exc)

    background_tasks.add_task(
        _run_ml_pipeline,
        zone_id=zone_id,
        cam_instance=instance,
        device_id=f"zone{zone_id}_cam{instance}",
        image_bytes=contents,
        filename=filename,
        image_url=image_url,
        ts=ts,
    )

    response: dict = {"status": "received", "zone_id": zone_id, "instance": instance,
                      "timestamp": str(ts)}
    if image_url:
        response["image_url"] = image_url
    return response


async def _run_ml_pipeline(
    zone_id: int,
    cam_instance: int,
    device_id: str,
    image_bytes: bytes,
    filename: str,
    image_url: str,
    ts: datetime,
) -> None:
    """Background task: run TameerML predict, persist results, publish actuator commands."""
    soil_rows = influx_service.query_latest_soil(zone_id=zone_id)
    air_rows  = influx_service.query_latest_air(zone_id=zone_id)

    soil_moisture = float(soil_rows[0].get("moisture",     50.0)) if soil_rows else 50.0
    temperature   = float(air_rows[0].get("air_temp",      25.0)) if air_rows  else 25.0
    humidity      = float(air_rows[0].get("air_humidity",  50.0)) if air_rows  else 50.0

    try:
        result = await ml_service.predict(
            image_bytes=image_bytes,
            filename=filename,
            temperature=temperature,
            humidity=humidity,
            soil_moisture=soil_moisture,
            device_id=device_id,
        )
    except Exception as exc:
        log.warning("ML predict failed for zone=%s cam=%s: %s", zone_id, cam_instance, exc)
        return

    action    = result["action"]
    disease   = result["disease"]
    disease_id = result["disease_id"]
    v_probs   = result["vision_probs"]   # list[float], positional

    confidence   = float(v_probs[disease_id]) if disease_id < len(v_probs) else 0.0
    health_score = 1.0 if disease == "healthy" else max(0.0, 1.0 - confidence)

    # Write camera_data with full fields (same timestamp → InfluxDB merges with initial write)
    influx_service.write_camera_data(
        zone_id=zone_id,
        cam_instance=cam_instance,
        image_url=image_url,
        health_status=disease,
        confidence=confidence,
        timestamp=ts,
    )

    influx_service.write_plant_health(
        zone_id=zone_id,
        cam_instance=cam_instance,
        disease_class=disease,
        confidence=confidence,
        health_score=health_score,
        timestamp=ts,
    )

    log.info("ML pipeline zone=%d cam=%d: action=%s disease=%s conf=%.3f",
             zone_id, cam_instance, action, disease, confidence)

    if action == "irrigate":
        cmd = {
            "command_id":     f"ml_{device_id}",
            "zone_id":        zone_id,
            "actuator":       "irrigation_valve",
            "action":         "on",
            "trigger_reason": f"TameerML: {disease} (conf={confidence:.2f}) → irrigate",
            "timestamp":      ts.isoformat(),
        }
        publish_command(cmd)
        influx_service.write_automation_event(
            zone_id=zone_id,
            actuator="irrigation_valve",
            action="on",
            trigger_reason=cmd["trigger_reason"],
            timestamp=ts,
        )

    elif action in ("fungicide", "pesticide"):
        cmd = {
            "command_id":     f"ml_{device_id}",
            "zone_id":        zone_id,
            "actuator":       "spray_nozzle",
            "action":         "on",
            "trigger_reason": f"TameerML: {disease} (conf={confidence:.2f}) → {action}",
            "timestamp":      ts.isoformat(),
        }
        publish_command(cmd)
        influx_service.write_automation_event(
            zone_id=zone_id,
            actuator="spray_nozzle",
            action="on",
            trigger_reason=cmd["trigger_reason"],
            timestamp=ts,
        )


@router.get("/zone/{zone_id}/camera/{instance}/latest.jpg")
def latest_image(zone_id: int, instance: int):
    """Serve the most recently uploaded plant image for a zone/camera."""
    path = _local_path(zone_id, instance)
    if os.path.exists(path):
        return FileResponse(path, media_type="image/jpeg")
    return HTMLResponse(
        f"<h2>No image uploaded yet for zone {zone_id} camera {instance}</h2>",
        status_code=404,
    )


@router.post("/analyze")
async def analyze_image(image: UploadFile = File(...)):
    """
    Analyze an uploaded plant photo using TameerML vision-only inference.
    Returns disease class, confidence, and per-class probabilities.
    """
    contents = await image.read()
    filename = image.filename or "upload.jpg"
    try:
        result = await ml_service.diagnose(image_bytes=contents, filename=filename)
        return {
            "disease_class": result["state"],
            "disease_id":    result["state_id"],
            "confidence":    result["confidence"],
            "vision_probs":  result["vision_probs"],
            "stub":          False,
        }
    except Exception as exc:
        log.warning("ML diagnose failed: %s", exc)
        raise HTTPException(status_code=503, detail=f"ML service unavailable: {exc}")


@router.delete("/session/{device_id}")
async def reset_ml_session(device_id: str):
    """Reset the TameerML LSTM rolling window for a given device (e.g. zone1_cam0)."""
    try:
        result = await ml_service.reset_session(device_id)
        return {"status": "ok", "reset": result}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/debug")
def debug_influx():
    """Return the last 20 raw InfluxDB records across all measurements."""
    rows = influx_service.query_debug_records(limit=20)
    return {"count": len(rows), "records": rows}
