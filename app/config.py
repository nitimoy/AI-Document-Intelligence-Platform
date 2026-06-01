"""Application configuration using pydantic-settings."""

from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.utils.exceptions import ConfigurationError


class Settings(BaseSettings):
    """Centralized environment-driven settings for the platform."""

    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")
    google_drive_folder_id: str = Field(
        default="", validation_alias="GOOGLE_DRIVE_FOLDER_ID"
    )
    google_service_account_file: str = Field(
        default="", validation_alias="GOOGLE_SERVICE_ACCOUNT_FILE"
    )
    download_dir: str = Field(default="downloads", validation_alias="DOWNLOAD_DIR")
    cache_dir: str = Field(default="cache", validation_alias="CACHE_DIR")
    drive_download_timeout_seconds: int = Field(
        default=600, validation_alias="DRIVE_DOWNLOAD_TIMEOUT_SECONDS"
    )
    drive_download_chunk_retries: int = Field(
        default=5, validation_alias="DRIVE_DOWNLOAD_CHUNK_RETRIES"
    )
    model_name: str = Field(default="gpt-4o", validation_alias="MODEL_NAME")
    openai_model: str = Field(default="gpt-4o", validation_alias="OPENAI_MODEL")
    summary_chunk_size: int = Field(default=1200, validation_alias="SUMMARY_CHUNK_SIZE")
    summary_chunk_overlap: int = Field(
        default=150, validation_alias="SUMMARY_CHUNK_OVERLAP"
    )
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    environment: str = Field(default="development", validation_alias="ENVIRONMENT")
    cors_allowed_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost",
            "http://localhost:3000",
            "http://127.0.0.1",
            "http://127.0.0.1:3000",
        ],
        validation_alias="CORS_ALLOWED_ORIGINS",
    )

    @field_validator("model_name")
    @classmethod
    def validate_model_name(cls, value: str) -> str:
        """Restrict model selection to approved values for this phase."""

        allowed = {"gpt-4o"}
        if value not in allowed:
            raise ValueError(f"MODEL_NAME must be one of {sorted(allowed)}")
        return value

    @field_validator("openai_model")
    @classmethod
    def validate_openai_model(cls, value: str) -> str:
        """Restrict OpenAI model selection to approved values for this phase."""

        allowed = {"gpt-4o"}
        if value not in allowed:
            raise ValueError(f"OPENAI_MODEL must be one of {sorted(allowed)}")
        return value

    @field_validator("summary_chunk_size")
    @classmethod
    def validate_chunk_size(cls, value: int) -> int:
        """Ensure chunk size is valid for token-aware summarization."""

        if value <= 0:
            raise ValueError("SUMMARY_CHUNK_SIZE must be greater than 0")
        return value

    @field_validator("summary_chunk_overlap")
    @classmethod
    def validate_chunk_overlap(cls, value: int) -> int:
        """Ensure chunk overlap is non-negative."""

        if value < 0:
            raise ValueError("SUMMARY_CHUNK_OVERLAP must be greater than or equal to 0")
        return value

    @field_validator("drive_download_timeout_seconds", "drive_download_chunk_retries")
    @classmethod
    def validate_drive_download_settings(cls, value: int) -> int:
        """Ensure Drive download tuning values stay positive."""

        if value <= 0:
            raise ValueError("Drive download tuning values must be greater than 0")
        return value

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def parse_cors_allowed_origins(cls, value: Any) -> list[str]:
        """Accept either a list or a comma-separated env var for CORS origins."""

        if value is None:
            return []
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        if isinstance(value, list):
            return [str(origin).strip() for origin in value if str(origin).strip()]
        raise ValueError(
            "CORS_ALLOWED_ORIGINS must be a comma-separated string or list"
        )

    @model_validator(mode="after")
    def validate_chunking_relationship(self) -> "Settings":
        """Validate overlap does not exceed chunk size."""

        if self.summary_chunk_overlap >= self.summary_chunk_size:
            raise ValueError(
                "SUMMARY_CHUNK_OVERLAP must be less than SUMMARY_CHUNK_SIZE"
            )
        return self

    def validate_google_drive_config(self) -> None:
        """Validate required Google Drive configuration for integration workflows."""

        if not self.google_drive_folder_id.strip():
            raise ConfigurationError(
                "GOOGLE_DRIVE_FOLDER_ID is required for Google Drive integration"
            )

        service_account_path = Path(self.google_service_account_file)
        if (
            not self.google_service_account_file.strip()
            or not service_account_path.exists()
        ):
            raise ConfigurationError(
                "GOOGLE_SERVICE_ACCOUNT_FILE must point to an existing key file"
            )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance for consistent app configuration."""

    return Settings()
