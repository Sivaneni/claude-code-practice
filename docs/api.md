# Weather API Documentation

A FastAPI-based REST API that fetches current weather data from OpenWeatherMap by city name or city ID.

---

## Base URL

```
http://localhost:8000
```

---

## Authentication

Set the `OPENWEATHER_API_KEY` environment variable in your `.env` file:

```env
OPENWEATHER_API_KEY=your_api_key_here
```

If the key is missing or unconfigured, all weather endpoints return `503 Service Unavailable`.

---

## TypeScript Types

```typescript
interface Coordinates {
  lat: number;
  lon: number;
}

interface WeatherCondition {
  condition: string;       // e.g. "Clouds", "Rain"
  description: string;     // e.g. "overcast clouds"
}

interface Temperature {
  current: number;
  feels_like: number;
  min: number;
  max: number;
}

interface Wind {
  speed_mps: number;
  direction_deg: number | null;
}

interface WeatherResponse {
  city: string;
  country: string;
  city_id: number;
  coordinates: Coordinates;
  weather: WeatherCondition;
  temperature: Temperature;
  humidity_percent: number;
  wind: Wind;
  visibility_m: number | null;
  cloudiness_percent: number;
}

interface HealthResponse {
  status: "ok";
}

interface ErrorResponse {
  detail: string;
}
```

---

## Endpoints

### GET `/weather/city/{city_name}`

Get current weather by city name.

**Path Parameters**

| Parameter   | Type   | Required | Description              |
|-------------|--------|----------|--------------------------|
| `city_name` | string | Yes      | Name of the city         |

**Query Parameters**

| Parameter | Type   | Required | Default  | Description                                  |
|-----------|--------|----------|----------|----------------------------------------------|
| `units`   | string | No       | `metric` | Unit system: `metric`, `imperial`, `standard` |

**Example Request**

```bash
curl -X GET "http://localhost:8000/weather/city/London?units=metric"
```

**Example Response** `200 OK`

```json
{
  "city": "London",
  "country": "GB",
  "city_id": 2643743,
  "coordinates": {
    "lat": 51.5085,
    "lon": -0.1257
  },
  "weather": {
    "condition": "Clouds",
    "description": "overcast clouds"
  },
  "temperature": {
    "current": 12.3,
    "feels_like": 10.8,
    "min": 11.0,
    "max": 13.5
  },
  "humidity_percent": 78,
  "wind": {
    "speed_mps": 4.1,
    "direction_deg": 220
  },
  "visibility_m": 10000,
  "cloudiness_percent": 90
}
```

---

### GET `/weather/id/{city_id}`

Get current weather by OpenWeatherMap city ID.

**Path Parameters**

| Parameter | Type    | Required | Description                    |
|-----------|---------|----------|--------------------------------|
| `city_id` | integer | Yes      | OpenWeatherMap numeric city ID |

**Query Parameters**

| Parameter | Type   | Required | Default  | Description                                   |
|-----------|--------|----------|----------|-----------------------------------------------|
| `units`   | string | No       | `metric` | Unit system: `metric`, `imperial`, `standard` |

**Example Request**

```bash
curl -X GET "http://localhost:8000/weather/id/2643743?units=imperial"
```

**Example Response** `200 OK`

```json
{
  "city": "London",
  "country": "GB",
  "city_id": 2643743,
  "coordinates": {
    "lat": 51.5085,
    "lon": -0.1257
  },
  "weather": {
    "condition": "Clouds",
    "description": "overcast clouds"
  },
  "temperature": {
    "current": 54.1,
    "feels_like": 51.4,
    "min": 51.8,
    "max": 56.3
  },
  "humidity_percent": 78,
  "wind": {
    "speed_mps": 9.17,
    "direction_deg": 220
  },
  "visibility_m": 10000,
  "cloudiness_percent": 90
}
```

---

### GET `/health`

Health check endpoint.

**Example Request**

```bash
curl -X GET "http://localhost:8000/health"
```

**Example Response** `200 OK`

```json
{
  "status": "ok"
}
```

---

## Error Responses

| Status Code | Scenario                                      |
|-------------|-----------------------------------------------|
| `404`       | City name or city ID not found                |
| `503`       | OpenWeather API key not configured            |
| Other       | Upstream OpenWeatherMap API error             |

**Example Error**

```json
{
  "detail": "City 'Atlantis' not found."
}
```

---

## Running Locally

```bash
pip install fastapi uvicorn httpx python-dotenv
uvicorn main:app --reload
```

Interactive docs available at: `http://localhost:8000/docs`
