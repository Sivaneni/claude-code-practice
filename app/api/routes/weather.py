from fastapi import APIRouter, Depends, HTTPException

from app.core.config import settings
from app.core.security import get_current_user
from app.services.weather import fetch_weather

router = APIRouter(prefix="/weather", tags=["weather"])


def _check_api_key() -> None:
    if (
        not settings.openweather_api_key
        or settings.openweather_api_key == "your_api_key_here"
    ):
        raise HTTPException(
            status_code=503,
            detail="OpenWeather API key not configured. Set OPENWEATHER_API_KEY in .env file.",
        )


@router.get("/city/{city_name}")
async def get_weather_by_city_name(
    city_name: str,
    units: str = "metric",
    current_user: str = Depends(get_current_user),
):
    """Get weather details by city name."""
    _check_api_key()
    params = {"q": city_name, "appid": settings.openweather_api_key, "units": units}
    return await fetch_weather(
        params, city_type="by_name", not_found_detail=f"City '{city_name}' not found."
    )


@router.get("/id/{city_id}")
async def get_weather_by_city_id(
    city_id: int,
    units: str = "metric",
    current_user: str = Depends(get_current_user),
):
    """Get weather details by OpenWeatherMap city ID."""
    _check_api_key()
    params = {"id": city_id, "appid": settings.openweather_api_key, "units": units}
    return await fetch_weather(
        params, city_type="by_id", not_found_detail=f"City ID '{city_id}' not found."
    )
