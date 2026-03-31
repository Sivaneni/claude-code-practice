from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv
import httpx
import os

load_dotenv()

app = FastAPI(title="Weather API", description="Get weather details by city name or city ID")

OPENWEATHER_BASE_URL = "https://api.openweathermap.org/data/2.5/weather"
API_KEY = os.getenv("OPENWEATHER_API_KEY")


def _check_api_key():
    if not API_KEY or API_KEY == "your_api_key_here":
        raise HTTPException(
            status_code=503,
            detail="OpenWeather API key not configured. Set OPENWEATHER_API_KEY in .env file.",
        )


@app.get("/weather/city/{city_name}")
async def get_weather_by_city_name(city_name: str, units: str = "metric"):
    """Get weather details by city name."""
    _check_api_key()
    params = {"q": city_name, "appid": API_KEY, "units": units}
    async with httpx.AsyncClient() as client:
        response = await client.get(OPENWEATHER_BASE_URL, params=params)
    if response.status_code == 404:
        raise HTTPException(status_code=404, detail=f"City '{city_name}' not found.")
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Weather API error.")
    return _format_weather(response.json())


@app.get("/weather/id/{city_id}")
async def get_weather_by_city_id(city_id: int, units: str = "metric"):
    """Get weather details by OpenWeatherMap city ID."""
    _check_api_key()
    params = {"id": city_id, "appid": API_KEY, "units": units}
    async with httpx.AsyncClient() as client:
        response = await client.get(OPENWEATHER_BASE_URL, params=params)
    if response.status_code == 404:
        raise HTTPException(status_code=404, detail=f"City ID '{city_id}' not found.")
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Weather API error.")
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


@app.get("/health")
async def health():
    return {"status": "ok"}
