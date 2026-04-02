import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging_config import request_id_ctx

logger = logging.getLogger(__name__)

# Paths that produce too much noise if logged on every scrape / health-poll
_SILENT_PATHS = frozenset({"/metrics", "/health"})


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Structured HTTP access log middleware.

    - Assigns a correlation ID to every request (honours X-Request-ID if
      supplied by an upstream gateway, otherwise generates a UUID).
    - Stores the ID in request_id_ctx so all downstream loggers include it
      automatically.
    - Echoes the ID back in the X-Request-ID response header.
    - Emits one INFO log on success, one WARNING on 4xx, one ERROR on 5xx /
      unhandled exceptions.
    - Skips access-log lines for /metrics and /health to avoid noise.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        ctx_token = request_id_ctx.set(request_id)

        path = request.url.path
        method = request.method
        client_ip = request.client.host if request.client else "-"

        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            if path not in _SILENT_PATHS:
                logger.error(
                    "http_request",
                    extra={
                        "method": method,
                        "path": path,
                        "status_code": 500,
                        "duration_ms": round((time.perf_counter() - start) * 1000, 2),
                        "client_ip": client_ip,
                        "user_agent": request.headers.get("user-agent", "-"),
                    },
                )
            raise
        finally:
            request_id_ctx.reset(ctx_token)

        if path not in _SILENT_PATHS:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            log_fn = (
                logger.error
                if status_code >= 500
                else logger.warning
                if status_code >= 400
                else logger.info
            )
            log_fn(
                "http_request",
                extra={
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                    "client_ip": client_ip,
                    "user_agent": request.headers.get("user-agent", "-"),
                },
            )

        response.headers["X-Request-ID"] = request_id
        return response
