# Weather API Documentation

A FastAPI-based REST API that fetches current weather data from OpenWeatherMap by city name or city ID.
All weather endpoints are protected by JWT Bearer authentication.

---

## Base URL

```
http://localhost:8000
```

---

## Project Structure

```
app/
├── core/
│   ├── config.py        # Settings loaded from environment variables
│   └── security.py      # JWT encoding/decoding, bcrypt password hashing
├── middleware/
│   └── metrics.py       # Prometheus counters, gauges, histograms + middleware
├── services/
│   └── weather.py       # OpenWeatherMap HTTP calls and response formatting
└── api/
    └── routes/
        ├── auth.py      # POST /auth/token
        ├── weather.py   # GET /weather/city/{name}, GET /weather/id/{id}
        └── ops.py       # GET /health, GET /metrics
tests/
├── conftest.py          # Shared fixtures (client, api key, auth override)
├── test_auth.py         # JWT authentication tests
└── test_weather.py      # Weather endpoint tests
main.py                  # Uvicorn entry point
```

---

## Environment Variables

| Variable                    | Required | Default                               | Description                          |
|-----------------------------|----------|---------------------------------------|--------------------------------------|
| `OPENWEATHER_API_KEY`       | Yes      | —                                     | OpenWeatherMap API key               |
| `JWT_SECRET_KEY`            | No       | `change-me-in-production-...`         | Secret used to sign JWTs             |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No     | `30`                                  | JWT validity window in minutes       |

Set these in a `.env` file at the project root:

```env
OPENWEATHER_API_KEY=your_openweather_key_here
JWT_SECRET_KEY=your-strong-random-secret
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

---

## Authentication

All `/weather/*` endpoints require a Bearer JWT in the `Authorization` header.

### Obtaining a token

```bash
curl -X POST "http://localhost:8000/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=secret"
```

**Response** `200 OK`

```json
{
  "access_token": "<jwt-token>",
  "token_type": "bearer"
}
```

### Using the token

Pass the token in the `Authorization` header on every weather request:

```bash
curl -X GET "http://localhost:8000/weather/city/London" \
  -H "Authorization: Bearer <jwt-token>"
```

### Built-in demo users

| Username | Password   |
|----------|------------|
| `admin`  | `secret`   |
| `user`   | `password` |

> Replace the in-memory `USERS_DB` in `app/core/security.py` with a real database before going to production.

---

## TypeScript Types

```typescript
interface TokenResponse {
  access_token: string;
  token_type: "bearer";
}

interface Coordinates {
  lat: number;
  lon: number;
}

interface WeatherCondition {
  condition: string;      // e.g. "Clouds", "Rain"
  description: string;    // e.g. "overcast clouds"
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

### POST `/auth/token`

Exchange credentials for a JWT Bearer token.

**Request** — `application/x-www-form-urlencoded`

| Field      | Type   | Required | Description       |
|------------|--------|----------|-------------------|
| `username` | string | Yes      | Account username  |
| `password` | string | Yes      | Account password  |

**Example Request**

```bash
curl -X POST "http://localhost:8000/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=secret"
```

**Example Response** `200 OK`

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Error Responses**

| Status | Scenario                         |
|--------|----------------------------------|
| `401`  | Incorrect username or password   |

---

### GET `/weather/city/{city_name}`

Get current weather by city name. **Requires Bearer token.**

**Path Parameters**

| Parameter   | Type   | Required | Description      |
|-------------|--------|----------|------------------|
| `city_name` | string | Yes      | Name of the city |

**Query Parameters**

| Parameter | Type   | Required | Default  | Description                                   |
|-----------|--------|----------|----------|-----------------------------------------------|
| `units`   | string | No       | `metric` | Unit system: `metric`, `imperial`, `standard` |

**Example Request**

```bash
curl -X GET "http://localhost:8000/weather/city/London?units=metric" \
  -H "Authorization: Bearer <jwt-token>"
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

Get current weather by OpenWeatherMap city ID. **Requires Bearer token.**

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
curl -X GET "http://localhost:8000/weather/id/2643743?units=imperial" \
  -H "Authorization: Bearer <jwt-token>"
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

Health check. No authentication required.

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

### GET `/metrics`

Prometheus metrics scrape endpoint. No authentication required.
Returns metrics in the [Prometheus text exposition format](https://prometheus.io/docs/instrumenting/exposition_formats/).

**Example Request**

```bash
curl -X GET "http://localhost:8000/metrics"
```

**Example Response** `200 OK` (`text/plain; version=0.0.4`)

```
# HELP http_requests_total Total number of HTTP requests received
# TYPE http_requests_total counter
http_requests_total{endpoint="/weather/city/{city_name}",method="GET",status_code="200"} 5.0

# HELP http_request_duration_seconds End-to-end HTTP request latency in seconds
# TYPE http_request_duration_seconds histogram
http_request_duration_seconds_bucket{endpoint="/weather/city/{city_name}",le="0.1",method="GET"} 3.0
...

# HELP active_http_requests Number of HTTP requests currently being processed
# TYPE active_http_requests gauge
active_http_requests 1.0
```

---

## Prometheus Metrics Reference

| Metric name                              | Type      | Labels                              | Alert use case                              |
|------------------------------------------|-----------|-------------------------------------|---------------------------------------------|
| `http_requests_total`                    | Counter   | `method`, `endpoint`, `status_code` | Error rate spike, traffic anomalies         |
| `http_request_duration_seconds`          | Histogram | `method`, `endpoint`                | p95 / p99 latency SLO breaches              |
| `active_http_requests`                   | Gauge     | —                                   | In-flight request overload                  |
| `weather_api_calls_total`                | Counter   | `city_type`, `status`               | High `not_found` or `error` rate            |
| `weather_external_api_duration_seconds`  | Histogram | —                                   | OpenWeatherMap upstream latency degradation |
| `jwt_auth_attempts_total`                | Counter   | `outcome`                           | Brute-force / credential-stuffing detection |

### Example AlertManager rules

```yaml
groups:
  - name: weather-api
    rules:
      - alert: HighErrorRate
        expr: |
          rate(http_requests_total{status_code=~"5.."}[5m]) /
          rate(http_requests_total[5m]) > 0.05
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "Error rate above 5% for 2 minutes"

      - alert: SlowRequests
        expr: |
          histogram_quantile(0.95,
            rate(http_request_duration_seconds_bucket[5m])
          ) > 1.0
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "p95 latency above 1s for 5 minutes"

      - alert: UpstreamWeatherApiSlow
        expr: |
          histogram_quantile(0.95,
            rate(weather_external_api_duration_seconds_bucket[5m])
          ) > 3.0
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "OpenWeatherMap p95 response time above 3s"

      - alert: AuthBruteForce
        expr: |
          rate(jwt_auth_attempts_total{outcome="failure"}[5m]) > 10
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "More than 10 failed login attempts per second"
```

---

## Error Responses

| Status | Scenario                                           |
|--------|----------------------------------------------------|
| `401`  | Missing, expired, or invalid Bearer token          |
| `401`  | Wrong username or password on `/auth/token`        |
| `404`  | City name or city ID not found                     |
| `503`  | `OPENWEATHER_API_KEY` not configured               |
| Other  | Upstream OpenWeatherMap API error                  |

**Example Error**

```json
{
  "detail": "City 'Atlantis' not found."
}
```

---

## Running Locally

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env          # then fill in OPENWEATHER_API_KEY and JWT_SECRET_KEY

# 3. Start the server
uvicorn main:app --reload
```

Interactive docs (Swagger UI): `http://localhost:8000/docs`
Alternative docs (ReDoc): `http://localhost:8000/redoc`

### Prometheus scrape config

Add this to your `prometheus.yml` to start scraping:

```yaml
scrape_configs:
  - job_name: weather-api
    static_configs:
      - targets: ["localhost:8000"]
```
