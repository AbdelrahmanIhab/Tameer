"""
Tameer — Voice Query Router
============================
POST /voice/query — accepts a spoken question (pre-transcribed by the frontend),
fetches live farm data, and returns a plain-language answer via Gemini 1.5 Flash.
"""

import io
import logging
import os

import edge_tts
from groq import AsyncGroq
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel

from backend.services import influx_service

log = logging.getLogger("tameer.voice")

router = APIRouter(prefix="/voice", tags=["Voice"])

_groq_client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY", ""))

_SYSTEM_AR = """أنت مساعد زراعي لمزارعين مصريين .
أجب دائماً بالعربية البسيطة الواضحة. لا تستخدم مصطلحات تقنية.
استخدم كلمات بسيطة مثل "التربة رطبة" أو "التربة جافة" و"الطقس حار" أو "الطقس بارد".
أجب في جملة أو جملتين فقط.
البيانات الحالية للمزرعة:
{context}"""

_SYSTEM_EN = """You are an agricultural assistant helping Egyptian farmers growing radish.
Always reply in simple, clear English. Avoid technical jargon.
Use plain words like "the soil is wet/dry" and "it is hot/cold outside".
Reply in one or two sentences only.
Current farm data:
{context}"""


class VoiceQuery(BaseModel):
    question: str
    zone_id: int
    language: str = "ar"  # "ar" or "en"


class VoiceResponse(BaseModel):
    answer: str


def _build_context(zone_id: int) -> str:
    snapshot = influx_service.query_latest_all(zone_id=zone_id)
    events = influx_service.query_automation_events(hours=1)

    parts: list[str] = []

    soil = snapshot.get("soil") or {}
    if soil:
        moisture = soil.get("moisture")
        soil_temp = soil.get("soil_temp")
        dryness = soil.get("dryness_level", "")
        if moisture is not None:
            parts.append(f"Soil moisture: {float(moisture):.1f}% ({dryness})")
        if soil_temp is not None:
            parts.append(f"Soil temperature: {float(soil_temp):.1f}°C")

    weather = snapshot.get("weather") or {}
    if weather:
        air_temp = weather.get("air_temp")
        humidity = weather.get("air_humidity")
        light = weather.get("light")
        if air_temp is not None:
            parts.append(f"Air temperature: {float(air_temp):.1f}°C")
        if humidity is not None:
            parts.append(f"Air humidity: {float(humidity):.1f}%")
        if light is not None:
            parts.append(f"Light level: {float(light):.1f}%")

    irr_min = snapshot.get("irrigation_minutes")
    if irr_min is not None:
        parts.append(f"Last irrigation: {float(irr_min):.1f} minutes")

    health = snapshot.get("health_status")
    if health:
        parts.append(f"Plant health: {health}")

    recent = [e for e in events[:3] if str(e.get("zone_id", "")) == str(zone_id)]
    if recent:
        actions = [f"{e.get('actuator')} {e.get('action')}" for e in recent]
        parts.append(f"Recent automation actions: {', '.join(actions)}")

    return "\n".join(parts) if parts else "No sensor data available yet."


@router.post("/query", response_model=VoiceResponse)
async def voice_query(body: VoiceQuery) -> VoiceResponse:
    context = _build_context(body.zone_id)
    template = _SYSTEM_AR if body.language == "ar" else _SYSTEM_EN
    system_prompt = template.format(context=context)

    try:
        completion = await _groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": body.question},
            ],
            max_tokens=150,
        )
        answer = completion.choices[0].message.content.strip()
    except Exception as exc:
        log.error("Groq call failed: %s", exc)
        raise HTTPException(status_code=502, detail="AI service unavailable")

    return VoiceResponse(answer=answer)


@router.get("/tts")
async def text_to_speech(
    text: str = Query(..., max_length=500),
    lang: str = Query("ar"),
) -> Response:
    voice = "ar-EG-SalmaNeural" if lang == "ar" else "en-US-AriaNeural"
    for attempt in range(3):
        try:
            buf = io.BytesIO()
            communicate = edge_tts.Communicate(text, voice)
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    buf.write(chunk["data"])
            if buf.tell() > 0:
                return Response(content=buf.getvalue(), media_type="audio/mpeg")
        except Exception as exc:
            log.warning("TTS attempt %d/3 failed: %s", attempt + 1, exc)
    raise HTTPException(status_code=502, detail="TTS service unavailable")
