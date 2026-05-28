from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Medical Document Assistant"
    app_version: str = "1.0.0"
    environment: str = "development"
    secret_key: str = "dev-secret-key"
    database_url: str = ""
    openai_api_key: str = ""
    
    # JWT settings
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 30

    class Config:
        env_file = ".env"


settings = Settings()