from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    SECRET_KEY: str = "dev-secret-change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    ENVIRONMENT: str = "development"

    # --- MongoDB ---
    # Full connection string, e.g.:
    #   mongodb://localhost:27017                (local)
    #   mongodb+srv://user:pass@cluster.mongodb.net  (Atlas)
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "safeher"

    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "SafeHer AI <no-reply@safeher.ai>"

    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = ""

    ANTHROPIC_API_KEY: str = ""

    GOOGLE_DRIVE_CLIENT_JSON: str = ""
    GOOGLE_DRIVE_TOKEN_JSON: str = ""

    MEDIA_ROOT: str = "app/media"
    PUBLIC_BASE_URL: str = "http://localhost:8000"

    CORS_ORIGINS: list[str] = ["*"]


settings = Settings()
