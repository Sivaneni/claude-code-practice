import logging
import time

import httpx
from fastapi import HTTPException

from app.core.config import settings
from app.middleware.metrics import WEATHER_API_CALLS_TOTAL, WEATHER_EXTERNAL_API_DURATION_SECONDS

logger = logging.getLogger(__name__)


async def fetch_weather(params: dict, city_type: str, not_found_detail: str) -> dict:
    """Call OpenWeatherMap, record metrics + logs, and return a formatted response."""
    lookup = params.get("q") or params.get("id", "unknown")

    logger.info(
        "weather_api_call_start",
        extra={"city_type": city_type, "lookup": lookup},
    )

    start = time.perf_counter()
    async with httpx.AsyncClient() as client:
        response = await client.get(settings.openweather_base_url, params=params)
    duration_ms = round((time.perf_counter() - start) * 1000, 2)

    WEATHER_EXTERNAL_API_DURATION_SECONDS.observe(duration_ms / 1000)

    if response.status_code == 404:
        WEATHER_API_CALLS_TOTAL.labels(city_type=city_type, status="not_found").inc()
        logger.warning(
            "weather_api_not_found",
            extra={"city_type": city_type, "lookup": lookup, "duration_ms": duration_ms},
        )
        raise HTTPException(status_code=404, detail=not_found_detail)

    if response.status_code != 200:
        WEATHER_API_CALLS_TOTAL.labels(city_type=city_type, status="error").inc()
        logger.error(
            "weather_api_error",
            extra={
                "city_type": city_type,
                "lookup": lookup,
                "upstream_status": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        raise HTTPException(status_code=response.status_code, detail="Weather API error.")

    WEATHER_API_CALLS_TOTAL.labels(city_type=city_type, status="success").inc()
    logger.info(
        "weather_api_call_success",
        extra={"city_type": city_type, "lookup": lookup, "duration_ms": duration_ms},
    )
    return _format_weather(response.json())


def _format_weather(data: dict) -> dict:
    return {
        "city": data["name"],
        "country": data["sys"]["country"],
        "city_id": data["id"],
        "coordinates": {"lat": data["coord"]["lat"], "lon": data["coord"]["lon"]},
        "weather": {
            "condition": data["weather"][0]["main"],
            "description": data["weather"][0]["description"],
        },
        "temperature": {
            "current": data["main"]["temp"],
            "feels_like": data["main"]["feels_like"],
            "min": data["main"]["temp_min"],
            "max": data["main"]["temp_max"],
        },
        "humidity_percent": data["main"]["humidity"],
        "wind": {
            "speed_mps": data["wind"]["speed"],
            "direction_deg": data["wind"].get("deg"),
        },
        "visibility_m": data.get("visibility"),
        "cloudiness_percent": data["clouds"]["all"],
    }
