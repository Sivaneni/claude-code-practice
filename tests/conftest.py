import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import get_current_user
from app.main import app


@pytest.fixture(autouse=True)
def set_api_key(monkeypatch):
    """Inject a dummy API key so weather routes pass the key-presence check."""
    monkeypatch.setattr(settings, "openweather_api_key", "test-key-123")


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def auth_override():
    """Bypass JWT validation — apply to test classes that don't test auth itself."""
    app.dependency_overrides[get_current_user] = lambda: "test_user"
    yield
    app.dependency_overrides.clear()
