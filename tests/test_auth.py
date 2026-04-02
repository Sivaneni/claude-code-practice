from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app

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


class TestJWTAuth:
    def test_login_success_returns_token(self):
        """Valid credentials return a Bearer token."""
        response = client.post(
            "/auth/token", data={"username": "admin", "password": "secret"}
        )
        assert response.status_code == 200
        body = response.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"

    def test_login_wrong_password_returns_401(self):
        """Wrong password must be rejected with 401."""
        response = client.post(
            "/auth/token", data={"username": "admin", "password": "wrong"}
        )
        assert response.status_code == 401

    def test_login_unknown_user_returns_401(self):
        """Unknown username must be rejected with 401."""
        response = client.post(
            "/auth/token", data={"username": "nobody", "password": "secret"}
        )
        assert response.status_code == 401

    def test_weather_without_token_returns_401(self):
        """Requests with no token must be rejected by the protected endpoint."""
        response = client.get("/weather/city/London")
        assert response.status_code == 401

    def test_weather_with_valid_token_returns_200(self):
        """A valid JWT grants access to the weather endpoint."""
        token_response = client.post(
            "/auth/token", data={"username": "admin", "password": "secret"}
        )
        token = token_response.json()["access_token"]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_WEATHER_RESPONSE

        with patch("app.services.weather.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            response = client.get(
                "/weather/city/London",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 200
        assert response.json()["city"] == "London"
