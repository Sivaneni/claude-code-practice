from fastapi import FastAPI

from app.api import api_router
from app.core.logging_config import setup_logging
from app.middleware.logging import LoggingMiddleware
from app.middleware.metrics import PrometheusMiddleware


def create_app() -> FastAPI:
    setup_logging()

    application = FastAPI(
        title="Weather API",
        description="Get weather details by city name or city ID",
    )

    # Middleware is applied in reverse-registration order (LIFO).
    # PrometheusMiddleware registered first → inner layer (runs after logging).
    # LoggingMiddleware registered second → outer layer (runs first, sets request_id_ctx).
    application.add_middleware(PrometheusMiddleware)
    application.add_middleware(LoggingMiddleware)

    application.include_router(api_router)
    return application


app = create_app()
