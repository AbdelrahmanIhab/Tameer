"""
Tameer — Camera Router
=======================
POST /camera/upload/zone/{zone_id}/camera/{instance}  — ESP32-CAM pushes a JPEG
GET  /camera/zone/{zone_id}/camera/{instance}/latest.jpg — serve most recent image
GET  /camera/debug                                    — last 20 raw InfluxDB records
"""

import os
from datetime import datetime, timezone

import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv
from fastapi import APIRouter, File, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from backend.services import influx_service

load_dotenv()

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
)

router = APIRouter(prefix="/camera", tags=["Camera"])


def _local_path(zone_id: int, instance: int) -> str:
    return f"latest_zone{zone_id}_cam{instance}.jpg"


@router.post("/upload/zone/{zone_id}/camera/{instance}")
async def upload_image(zone_id: int, instance: int, image: UploadFile = File(...)):
    """Accept a JPEG from the ESP32-CAM for the given zone and camera instance."""
    contents  = await image.read()
    ts        = datetime.now(timezone.utc)
    local_path = _local_path(zone_id, instance)

    with open(local_path, "wb") as f:
        f.write(contents)

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
        return {
            "status":    "received",
            "zone_id":   zone_id,
            "instance":  instance,
            "image_url": image_url,
            "timestamp": str(ts),
        }
    except Exception as exc:
        return {
            "status":   "received_locally",
            "zone_id":  zone_id,
            "instance": instance,
            "error":    str(exc),
        }


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


@router.get("/debug")
def debug_influx():
    """Return the last 20 raw InfluxDB records across all measurements."""
    rows = influx_service.query_debug_records(limit=20)
    return {"count": len(rows), "records": rows}
