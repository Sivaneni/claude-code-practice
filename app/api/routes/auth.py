import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from app.core.security import authenticate_user, create_access_token
from app.middleware.metrics import JWT_AUTH_ATTEMPTS_TOTAL

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str


@router.post("/token", response_model=TokenResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Exchange username + password for a Bearer JWT."""
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        JWT_AUTH_ATTEMPTS_TOTAL.labels(outcome="failure").inc()
        logger.warning("auth_failure", extra={"username": form_data.username})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    JWT_AUTH_ATTEMPTS_TOTAL.labels(outcome="success").inc()
    logger.info("auth_success", extra={"username": user["username"]})
    token = create_access_token({"sub": user["username"]})
    return TokenResponse(access_token=token, token_type="bearer")
