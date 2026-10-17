"""Shared test setup.

Tests run against a real PostgreSQL database (the models use Postgres types
such as UUID and JSONB), given by DATABASE_URL. The schema is created with the
real Alembic migrations once per session, and every test starts from empty
tables. External services are never called: Cloudinary, the embedding model
and Gemini are replaced in the fixtures below.
"""
import os
import uuid

os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("GOOGLE_API_KEY", "test-key")

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    if not os.getenv("DATABASE_URL"):
        pytest.exit("Set DATABASE_URL to a disposable PostgreSQL database to run the tests.", returncode=2)
    cfg = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(BACKEND_DIR, "alembic"))
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def clean_tables():
    from app.database import engine

    with engine.begin() as conn:
        conn.execute(text("TRUNCATE chat_messages, documents, users RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app)


def register_and_login(client, email=None, password="password123"):
    email = email or f"user-{uuid.uuid4().hex[:8]}@example.com"
    assert client.post("/auth/register", json={"email": email, "password": password}).status_code == 201
    token = client.post("/auth/login", json={"email": email, "password": password}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers(client):
    return register_and_login(client)
