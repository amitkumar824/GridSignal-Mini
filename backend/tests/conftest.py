import os
import sys
import tempfile
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional
import pytest

# Ensure backend root is on Python module search path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import app
import app.config as config
from app.database import get_connection, init_db
from app.main import (
    app as fastapi_app,
    health,
    list_incidents,
    list_alerts,
    get_summary,
    import_seed_data,
    import_replay_data
)

class MockResponse:
    def __init__(self, status_code: int, data: Any):
        self.status_code = status_code
        self._data = data

    def json(self):
        return self._data

class DirectApiClient:
    """
    Lightweight, deterministic test client for GridSignal API endpoints.
    Dispatches directly to route handlers with Pydantic serialization, avoiding
    platform-specific anyio/starlette background thread portal issues on Python 3.13.
    """
    def __init__(self, app_instance):
        self.app = app_instance

    def get(self, path: str, params: Optional[Dict[str, Any]] = None):
        # Parse query params if embedded in path
        if "?" in path:
            path_part, query_part = path.split("?", 1)
            params = params or {}
            for q in query_part.split("&"):
                if "=" in q:
                    k, v = q.split("=", 1)
                    params[k] = v
            path = path_part

        if path == "/health":
            return MockResponse(200, health().model_dump())
        elif path == "/incidents":
            utility = (params or {}).get("utility_type")
            items = list_incidents(utility_type=utility)
            return MockResponse(200, [item.model_dump() for item in items])
        elif path == "/alerts":
            items = list_alerts()
            return MockResponse(200, [item.model_dump() for item in items])
        elif path == "/summary":
            return MockResponse(200, get_summary().model_dump())
        raise ValueError(f"Unknown GET path: {path}")

    def post(self, path: str):
        if path == "/api/import/seed":
            return MockResponse(200, import_seed_data().model_dump())
        elif path == "/api/import/replay":
            return MockResponse(200, import_replay_data().model_dump())
        raise ValueError(f"Unknown POST path: {path}")

@pytest.fixture
def temp_db(monkeypatch):
    """Create an isolated temporary SQLite database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        temp_path = Path(f.name)

    monkeypatch.setattr(config, "DATABASE_PATH", temp_path)
    init_db(temp_path)

    yield temp_path

    if temp_path.exists():
        try:
            temp_path.unlink()
        except Exception:
            pass

@pytest.fixture
def test_client(temp_db):
    """API client bound to the isolated temporary test database."""
    return DirectApiClient(fastapi_app)

@pytest.fixture
def db_conn(temp_db):
    """Active sqlite3 connection to the temporary test database."""
    conn = get_connection(temp_db)
    yield conn
    conn.close()
