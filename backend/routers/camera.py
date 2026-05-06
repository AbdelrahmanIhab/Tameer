"""
Tameer — Camera Router
=======================
POST /camera/upload/{location}        — ESP32-CAM pushes a JPEG for a specific location
GET  /camera/latest/{location}.jpg    — serve the most recently uploaded image for a location
GET  /camera/debug                    — last 20 raw InfluxDB records (sensor + camera + irrigation)
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


def _local_path(location: str) -> str:
    return f"latest_{location}.jpg"


@router.post("/upload/{location}")
async def upload_image(location: str, image: UploadFile = File(...)):
    """Accept a JPEG from the ESP32-CAM for the given location, save locally, and push to Cloudinary."""
    contents = await image.read()
    ts = datetime.now(timezone.utc)
    local_path = _local_path(location)

    with open(local_path, "wb") as f:
        f.write(contents)

    try:
        result = cloudinary.uploader.upload(
            contents,
            folder="tameer",
            public_id=f"{location}_{ts.strftime('%Y%m%d_%H%M%S')}",
            resource_type="image",
        )
        image_url = result.get("secure_url", "")
        influx_service.write_camera_data(image_url=image_url, location=location, timestamp=ts)
        return {"status": "received", "location": location, "image_url": image_url, "timestamp": str(ts)}
    except Exception as exc:
        return {"status": "received_locally", "location": location, "error": str(exc)}


@router.get("/latest/{location}.jpg")
def latest_image(location: str):
    """Serve the most recently uploaded plant image for a location."""
    path = _local_path(location)
    if os.path.exists(path):
        return FileResponse(path, media_type="image/jpeg")
    return HTMLResponse(f"<h2>No image uploaded yet for location '{location}'</h2>", status_code=404)


@router.get("/debug")
def debug_influx():
    """Return the last 20 raw InfluxDB records across sensor, camera, and irrigation measurements."""
    rows = influx_service.query_debug_records(limit=20)
    return {"count": len(rows), "records": rows}
