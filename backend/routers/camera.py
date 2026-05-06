"""
Tameer — Camera Router
=======================
POST /camera/upload     — ESP32-CAM pushes a JPEG; stored locally + uploaded to Cloudinary
GET  /camera/latest.jpg — serve the most recently uploaded image
GET  /camera/debug      — last 20 raw InfluxDB records (sensor + camera data)
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

UPLOAD_PATH = "latest.jpg"

router = APIRouter(prefix="/camera", tags=["Camera"])


@router.post("/upload")
async def upload_image(image: UploadFile = File(...)):
    """Accept a JPEG from the ESP32-CAM, save locally, and push to Cloudinary."""
    contents = await image.read()
    ts = datetime.now(timezone.utc)

    with open(UPLOAD_PATH, "wb") as f:
        f.write(contents)

    try:
        result = cloudinary.uploader.upload(
            contents,
            folder="tameer",
            public_id=f"plant_{ts.strftime('%Y%m%d_%H%M%S')}",
            resource_type="image",
        )
        image_url = result.get("secure_url", "")
        influx_service.write_camera_data(image_url=image_url, timestamp=ts)
        return {"status": "received", "image_url": image_url, "timestamp": str(ts)}
    except Exception as exc:
        return {"status": "received_locally", "error": str(exc)}


@router.get("/latest.jpg")
def latest_image():
    """Serve the most recently uploaded plant image."""
    if os.path.exists(UPLOAD_PATH):
        return FileResponse(UPLOAD_PATH, media_type="image/jpeg")
    return HTMLResponse("<h2>No image uploaded yet</h2>", status_code=404)


@router.get("/debug")
def debug_influx():
    """Return the last 20 raw InfluxDB records across sensor and camera measurements."""
    rows = influx_service.query_debug_records(limit=20)
    return {"count": len(rows), "records": rows}
