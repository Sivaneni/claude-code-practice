from fastapi import APIRouter

from app.api.routes import auth, ops, weather

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(weather.router)
api_router.include_router(ops.router)
