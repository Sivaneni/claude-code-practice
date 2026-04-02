from fastapi import APIRouter

from app.middleware.metrics import metrics_response

router = APIRouter(tags=["ops"])


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/metrics", include_in_schema=False)
async def metrics():
    """Prometheus scrape endpoint."""
    return metrics_response()
