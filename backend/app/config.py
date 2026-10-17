from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Medical Document Assistant"
    app_version: str = "1.1.0"
    environment: str = "development"

    # Signs every login token. There is deliberately no default: with a
    # well-known default, anyone could forge a token for any user if the
    # variable were ever missing in production. The app refuses to start
    # without it.
    secret_key: str = Field(min_length=16)

    database_url: str = ""
    google_api_key: str = ""

    # JWT settings
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 30

    # Cloudinary settings
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""
    frontend_url: str = "http://localhost:5173"

    # Path to the tesseract binary. Empty means "find it on PATH" (Linux, and
    # Windows if Tesseract's folder is on PATH).
    tesseract_cmd: str = ""

    # Where Chroma stores vectors. On hosts with an ephemeral disk this is
    # wiped on redeploy; the app rebuilds a document's vectors from its saved
    # text when that happens (see app/ai/embedder.py).
    chroma_path: str = "chroma_db"

    # Per-user limit on the endpoints that call the LLM (chat, extract,
    # compare), to cap cost and abuse. In-memory, so it is per process.
    llm_requests_per_minute: int = 20

    max_upload_bytes: int = 10 * 1024 * 1024

    @field_validator("secret_key")
    @classmethod
    def reject_known_defaults(cls, value: str) -> str:
        if value in {"dev-secret-key", "changeme", "secret"}:
            raise ValueError("SECRET_KEY is set to a well-known placeholder; use a long random value")
        return value


settings = Settings()
