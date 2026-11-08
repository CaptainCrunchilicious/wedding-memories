from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Validated application settings loaded from environment and backend/.env."""

    app_name: str = "Wedding Memories"
    app_env: str = "development"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"
    mongodb_uri: str = ""
    mongodb_database: str = Field(default="wedding_memories", min_length=1)
    jwt_secret: SecretStr = SecretStr("")
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = Field(default=30, gt=0, le=1440)
    frontend_origins: str = "http://localhost:5173"
    photo_storage_provider: str = "local"
    photo_storage_local_path: Path = BACKEND_ROOT / "storage-data"
    google_drive_client_id: str = ""
    google_drive_client_secret: SecretStr = SecretStr("")
    google_drive_redirect_uri: str = "http://localhost:8011/api/v1/integrations/google-drive/callback"
    google_drive_token_encryption_key: SecretStr = SecretStr("")
    google_drive_token_encryption_key_previous: SecretStr = SecretStr("")
    google_drive_folder_id: str = ""
    upload_session_minutes: int = Field(default=30, gt=0, le=180)
    upload_max_file_bytes: int = Field(default=12 * 1024 * 1024, gt=0)
    upload_max_request_bytes: int = Field(default=55 * 1024 * 1024, gt=0)
    upload_max_files_per_request: int = Field(default=10, gt=0, le=50)
    upload_max_files_per_session: int = Field(default=30, gt=0)
    upload_max_bytes_per_session: int = Field(default=100 * 1024 * 1024, gt=0)
    upload_sessions_per_ip_per_hour: int = Field(default=20, gt=0)
    upload_requests_per_ip_per_hour: int = Field(default=30, gt=0)

    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("mongodb_database")
    @classmethod
    def validate_database_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("MONGODB_DATABASE must not be empty")
        return normalized

    @field_validator("jwt_algorithm")
    @classmethod
    def validate_jwt_algorithm(cls, value: str) -> str:
        if value not in {"HS256", "HS384", "HS512"}:
            raise ValueError("JWT_ALGORITHM must be one of HS256, HS384, or HS512")
        return value

    @field_validator("frontend_origins")
    @classmethod
    def validate_frontend_origins(cls, value: str) -> str:
        origins = [origin.strip() for origin in value.split(",") if origin.strip()]
        if not origins or "*" in origins:
            raise ValueError("FRONTEND_ORIGINS must contain explicit origins and cannot use a wildcard")
        return ",".join(origins)

    @field_validator("photo_storage_provider")
    @classmethod
    def validate_storage_provider(cls, value: str) -> str:
        provider = value.strip().lower()
        if provider not in {"local", "google_drive"}:
            raise ValueError("PHOTO_STORAGE_PROVIDER must be local or google_drive")
        return provider

    @field_validator("google_drive_redirect_uri")
    @classmethod
    def validate_google_drive_redirect_uri(cls, value: str) -> str:
        redirect_uri = value.strip()
        parsed = urlsplit(redirect_uri)
        if not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
            raise ValueError("GOOGLE_DRIVE_REDIRECT_URI must be an absolute callback URL")
        loopback_hosts = {"localhost", "127.0.0.1", "::1"}
        if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname.lower() in loopback_hosts):
            raise ValueError("GOOGLE_DRIVE_REDIRECT_URI must use HTTPS except for localhost development")
        return redirect_uri



@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return one validated settings object for this process."""
    return Settings()
