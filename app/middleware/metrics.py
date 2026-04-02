import time

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# ---------------------------------------------------------------------------
# Counters
# ---------------------------------------------------------------------------

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total number of HTTP requests received",
    ["method", "endpoint", "status_code"],
)

WEATHER_API_CALLS_TOTAL = Counter(
    "weather_api_calls_total",
    "Total calls to weather endpoints by lookup type and outcome",
    ["city_type", "status"],
    # city_type : 'by_name' | 'by_id'
    # status    : 'success' | 'not_found' | 'error'
)

JWT_AUTH_ATTEMPTS_TOTAL = Counter(
    "jwt_auth_attempts_total",
    "Total JWT login attempts via POST /auth/token",
    ["outcome"],
    # outcome : 'success' | 'failure'
)

# ---------------------------------------------------------------------------
# Gauges
# ---------------------------------------------------------------------------

ACTIVE_HTTP_REQUESTS = Gauge(
    "active_http_requests",
    "Number of HTTP requests currently being processed",
)

# ---------------------------------------------------------------------------
# Histograms
# ---------------------------------------------------------------------------

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "End-to-end HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

WEATHER_EXTERNAL_API_DURATION_SECONDS = Histogram(
    "weather_external_api_duration_seconds",
    "Latency of outbound calls to the OpenWeatherMap API in seconds",
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0],
)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Attach request counters, active-request gauge, and latency histograms."""

    _SKIP_PATHS = frozenset({"/metrics"})

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        method = request.method

        if path in self._SKIP_PATHS:
            return await call_next(request)

        ACTIVE_HTTP_REQUESTS.inc()
        start = time.perf_counter()
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            HTTP_REQUESTS_TOTAL.labels(
                method=method, endpoint=path, status_code=500
            ).inc()
            ACTIVE_HTTP_REQUESTS.dec()
            raise
        finally:
            HTTP_REQUEST_DURATION_SECONDS.labels(method=method, endpoint=path).observe(
                time.perf_counter() - start
            )

        ACTIVE_HTTP_REQUESTS.dec()
        HTTP_REQUESTS_TOTAL.labels(
            method=method, endpoint=path, status_code=status_code
        ).inc()
        return response


def metrics_response() -> Response:
    """Prometheus text exposition — mount at GET /metrics."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
