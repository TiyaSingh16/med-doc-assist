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


# ---- fakes for external services -------------------------------------------

@pytest.fixture
def fake_embeddings(monkeypatch, tmp_path):
    """Deterministic hash-based embeddings and a throwaway Chroma directory.

    Not semantic, so tests check wiring (pages, sources, rebuilds), not
    retrieval quality.
    """
    from langchain_core.embeddings import DeterministicFakeEmbedding

    from app.ai import embedder
    from app.config import settings

    monkeypatch.setattr(settings, "chroma_path", str(tmp_path / "chroma"))
    fake = DeterministicFakeEmbedding(size=32)
    monkeypatch.setattr(embedder, "get_embeddings", lambda: fake)
    return fake


@pytest.fixture
def fake_llm(monkeypatch):
    """Replaces Gemini. Records the prompts it was given."""
    from langchain_core.language_models.fake_chat_models import FakeListChatModel

    from app.ai import chains

    calls = {"prompts": [], "responses": ["Your hemoglobin is 13.5 g/dL [p. 2]."]}

    class RecordingLLM(FakeListChatModel):
        def invoke(self, prompt, *args, **kwargs):
            calls["prompts"].append(prompt)
            return super().invoke(prompt, *args, **kwargs)

        async def astream(self, prompt, *args, **kwargs):
            calls["prompts"].append(prompt)
            async for chunk in super().astream(prompt, *args, **kwargs):
                yield chunk

    monkeypatch.setattr(chains, "get_llm", lambda **kw: RecordingLLM(responses=list(calls["responses"])))
    return calls


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    from app.utils.rate_limit import llm_limiter

    llm_limiter.reset()
    yield


@pytest.fixture
def fake_storage(monkeypatch):
    """Records Cloudinary uploads instead of sending them."""
    from app.services import pdf_service

    uploads = []

    def fake_upload(file_path, **kwargs):
        uploads.append(kwargs)
        return {"public_id": kwargs["public_id"], "secure_url": "https://example.invalid/should-not-be-used"}

    monkeypatch.setattr(pdf_service.cloudinary.uploader, "upload", fake_upload)
    return uploads


def make_pdf(pages: list[str]) -> bytes:
    """A real PDF with one text page per string."""
    import fitz

    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        page.insert_text((72, 72), text, fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data
