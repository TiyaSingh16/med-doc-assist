from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Medical Document Assistant"
    app_version: str = "1.0.0"
    environment: str = "development"
    secret_key: str = "dev-secret-key"
    database_url: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""

    # JWT settings
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 30

    # Cloudinary settings
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""
    frontend_url: str = "http://localhost:5173"
    class Config:
        env_file = ".env"


settings = Settings()
