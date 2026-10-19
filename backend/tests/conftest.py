"""Test fixtures.

Every test runs against a throwaway SQLite file in a temporary directory.
DATABASE_PATH is set before the app is imported, so the application builds
its engine against that file and the development cafe.db is never touched.
"""

import os
import tempfile
from pathlib import Path

import pytest

TEST_DB_PATH = Path(tempfile.mkdtemp(prefix="cms-tests-")) / "test.db"
os.environ["DATABASE_PATH"] = str(TEST_DB_PATH)

from fastapi.testclient import TestClient  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402

# Fail loudly rather than risk writing to the real database.
assert settings.database_file == TEST_DB_PATH, (
    f"tests are pointed at {settings.database_file}, not the temporary database"
)


@pytest.fixture
def client() -> TestClient:
    """A client backed by an empty database, rebuilt for every test."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def valid_item() -> dict:
    return {"name": "Cappuccino", "category": "Beverages", "price": "180.50"}
