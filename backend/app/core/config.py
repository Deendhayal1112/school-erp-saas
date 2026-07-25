import json
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables and .env files.
    Uses Pydantic Settings v2 for robust validation and type coercion.
    """
    model_config = SettingsConfigDict(
        # Supports reading .env from backend/ directory or root directory
        env_file=(".env", "../.env", "backend/.env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    # ==========================================
    # 1. Application Settings
    # ==========================================
    PROJECT_NAME: str = "School ERP SaaS"
    ENV: Literal["development", "staging", "production", "testing"] = "development"
    API_V1_STR: str = "/api/v1"
    PORT: int = 3000

    # ==========================================
    # 2. Database Settings
    # ==========================================
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "password"
    DB_NAME: str = "school_erp"
    DATABASE_URL: str | None = None

    @property
    def async_database_url(self) -> str:
        """Asynchronous database connection string for SQLAlchemy & asyncpg."""
        if self.DATABASE_URL:
            if self.DATABASE_URL.startswith("postgresql://"):
                return self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
            return self.DATABASE_URL
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def sync_database_url(self) -> str:
        """Synchronous database connection string (e.g., for Alembic migrations)."""
        if self.DATABASE_URL:
            if self.DATABASE_URL.startswith("postgresql+asyncpg://"):
                return self.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)
            return self.DATABASE_URL
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    # ==========================================
    # 3. Authentication & JWT Settings
    # ==========================================
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRES_IN: str = "7d"  # Used to parse tokens (e.g., "7d", "1d", "30m")

    # Core Security Settings loaded from environment variables
    SECRET_KEY: str = "supersecretkeyplaceholderchangeinproduction"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ==========================================
    # 4. Redis Settings
    # ==========================================
    REDIS_URL: str = "redis://localhost:6379/0"

    # ==========================================
    # 5. Middleware Feature Flags
    # ==========================================
    ENABLE_AUDIT_LOG: bool = True
    ENABLE_SECURITY_HEADERS: bool = True
    ENABLE_AUTHORIZATION_MIDDLEWARE: bool = True

    # ==========================================
    # Password Management Settings
    # ==========================================
    PASSWORD_HISTORY_LENGTH: int = 5          # How many previous passwords to remember
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30  # Reset link TTL
    PASSWORD_EXPIRE_DAYS: int = 0             # 0 = never expires
    ACCOUNT_LOCKOUT_THRESHOLD: int = 5        # Failed attempts before lockout
    ACCOUNT_LOCKOUT_MINUTES: int = 15         # Lockout duration

    # ==========================================
    # 6. Celery Settings
    # ==========================================
    CELERY_BROKER_URL: str | None = None
    CELERY_RESULT_BACKEND: str | None = None

    @property
    def resolved_celery_broker(self) -> str:
        """Defaults Celery broker to Redis URL if not explicitly configured."""
        return self.CELERY_BROKER_URL or self.REDIS_URL

    @property
    def resolved_celery_backend(self) -> str:
        """Defaults Celery result backend to Redis URL if not explicitly configured."""
        return self.CELERY_RESULT_BACKEND or self.REDIS_URL

    # ==========================================
    # 6. Email Settings (SMTP)
    # ==========================================
    SMTP_HOST: str | None = None
    SMTP_PORT: int | None = None
    SMTP_USER: str | None = None
    SMTP_PASS: str | None = None
    SMTP_FROM: str | None = None

    # ==========================================
    # Email Verification & Account Recovery
    # ==========================================
    EMAIL_PROVIDER: str = "console"           # console, smtp, mock
    EMAIL_VERIFICATION_EXPIRE_MINUTES: int = 1440  # 24 hours
    EMAIL_SENDER: str = "noreply@schoolerpsaas.com"
    BASE_URL: str = "http://localhost:3000"   # Base URL for verification/reset links
    EMAIL_RATE_LIMIT_SECONDS: int = 60        # Rate limit between resend requests


    # ==========================================
    # 7. CORS Settings
    # ==========================================
    CORS_ORIGINS: list[str] = ["*"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str]:
        """Assembles list of origins from comma-separated string or JSON array."""
        if isinstance(v, str):
            if not v.strip():
                return ["*"]
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return ["*"]

    # ==========================================
    # 8. Logging Settings
    # ==========================================
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # ==========================================
    # 9. Enterprise Validation
    # ==========================================
    @model_validator(mode="after")
    def validate_production_safety(self) -> "Settings":
        """
        Safety check to prevent running production/staging environments
        with weak default credentials or development configurations.
        """
        if self.ENV in ("production", "staging"):
            if self.JWT_SECRET == "supersecretjwtkeychangeinproduction":
                raise ValueError(
                    "Security Breach Risk: JWT_SECRET must be customized in production/staging!"
                )
            if self.SECRET_KEY == "supersecretkeyplaceholderchangeinproduction":
                raise ValueError(
                    "Security Breach Risk: SECRET_KEY must be customized in production/staging!"
                )
            if self.DB_PASSWORD == "password":
                raise ValueError(
                    "Security Breach Risk: Default database password 'password' is not allowed in production/staging!"
                )
        return self


# Global singleton instance of Settings
settings = Settings()
