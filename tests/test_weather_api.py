from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

MOCK_WEATHER_RESPONSE = {
    "name": "London",
    "sys": {"country": "GB"},
    "id": 2643743,
    "coord": {"lat": 51.5085, "lon": -0.1257},
    "weather": [{"main": "Clouds", "description": "overcast clouds"}],
    "main": {
        "temp": 12.3,
        "feels_like": 10.8,
        "temp_min": 11.0,
        "temp_max": 13.5,
        "humidity": 78,
    },
    "wind": {"speed": 4.1, "deg": 220},
    "visibility": 10000,
    "clouds": {"all": 90},
}


@pytest.fixture(autouse=True)
def set_api_key(monkeypatch):
    monkeypatch.setenv("OPENWEATHER_API_KEY", "test-key-123")
    import main

    monkeypatch.setattr(main, "API_KEY", "test-key-123")


class TestGetWeatherByCityName:
    def test_returns_formatted_weather(self):
        """Test that /weather/city/{city_name} returns correct formatted response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_WEATHER_RESPONSE

        with patch("main.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            response = client.get("/weather/city/London")

        assert response.status_code == 200
        data = response.json()
        assert data["city"] == "London"
        assert data["country"] == "GB"
        assert data["temperature"]["current"] == 12.3
        assert data["humidity_percent"] == 78
        assert data["weather"]["condition"] == "Clouds"

    def test_returns_404_for_unknown_city(self):
        """Test that /weather/city/{city_name} returns 404 for an unknown city."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("main.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            response = client.get("/weather/city/Atlantis")

        assert response.status_code == 404
        assert "Atlantis" in response.json()["detail"]
