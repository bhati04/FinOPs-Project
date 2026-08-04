"""Validated environment configuration."""

from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field, RedisDsn, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded exclusively from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="CLOUDWISE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["local", "test", "development", "staging", "production"] = "local"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    database_url: str = "postgresql+asyncpg://cloudwise:cloudwise@postgres:5432/cloudwise"
    redis_url: RedisDsn = RedisDsn("redis://redis:6379/0")
    cors_origins: list[AnyHttpUrl] = [AnyHttpUrl("http://localhost:5173")]
    api_request_max_bytes: int = Field(default=1_048_576, ge=1_024, le=10_485_760)
    auth_secret_key: SecretStr = SecretStr(
        "local-only-change-before-production-0123456789abcdef0123456789abcdef"
    )
    access_token_minutes: int = Field(default=15, ge=5, le=60)
    refresh_token_days: int = Field(default=7, ge=1, le=30)
    external_id_encryption_key: SecretStr = SecretStr(
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
    )
    cost_allocation_tag_key: str | None = Field(default=None, max_length=128)
    recommendation_pricing_provider: Literal["aws", "mock"] = "mock"
    recommendation_pricing_endpoint_region: Literal["us-east-1", "eu-central-1", "ap-south-1"] = (
        "us-east-1"
    )
    recommendation_pricing_stale_hours: int = Field(default=48, ge=1, le=720)
    report_storage_provider: Literal["local", "s3"] = "local"
    report_local_directory: str = "/var/lib/cloudwise/reports"
    report_s3_bucket: str | None = None
    report_s3_prefix: str = "cloudwise-reports"
    report_retention_days: int = Field(default=30, ge=1, le=365)
    notification_provider: Literal["disabled", "ses"] = "disabled"
    notification_ses_region: str = "us-east-1"
    notification_from_email: str | None = Field(default=None, max_length=320)
    ai_advisor_enabled: bool = False
    ai_advisor_provider: Literal["bedrock"] = "bedrock"
    ai_advisor_model_id: str | None = None
    ai_advisor_aws_region: str = "us-east-1"
    ai_advisor_max_output_tokens: int = Field(default=800, ge=256, le=2_048)
    ai_advisor_timeout_seconds: int = Field(default=20, ge=1, le=60)

    @field_validator("database_url")
    @classmethod
    def validate_database_driver(cls, value: str) -> str:
        """Require the async PostgreSQL driver used by the service."""
        if not value.startswith("postgresql+asyncpg://"):
            raise ValueError("database_url must use postgresql+asyncpg")
        return value

    @field_validator("cors_origins")
    @classmethod
    def validate_production_origins(cls, value: list[AnyHttpUrl], info: object) -> list[AnyHttpUrl]:
        """Reject wildcard origins; credentialed CORS must be explicit."""
        if not value:
            raise ValueError("at least one CORS origin is required")
        return value

    @model_validator(mode="after")
    def validate_ai_advisor(self) -> "Settings":
        """Require an explicit model only when advisory generation is enabled."""
        if self.ai_advisor_enabled and not self.ai_advisor_model_id:
            raise ValueError("ai_advisor_model_id is required when AI advisory is enabled")
        if self.environment == "production" and self.auth_secret_key.get_secret_value().startswith(
            "local-only-"
        ):
            raise ValueError("auth_secret_key must be replaced in production")
        if (
            self.environment == "production"
            and self.external_id_encryption_key.get_secret_value()
            == "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
        ):
            raise ValueError("external_id_encryption_key must be replaced in production")
        if self.environment == "production" and self.recommendation_pricing_provider != "aws":
            raise ValueError("recommendation_pricing_provider must be aws in production")
        if self.environment == "production" and self.report_storage_provider != "s3":
            raise ValueError("report_storage_provider must be s3 in production")
        if self.report_storage_provider == "s3" and not self.report_s3_bucket:
            raise ValueError("report_s3_bucket is required when report storage uses s3")
        if self.notification_provider == "ses" and not self.notification_from_email:
            raise ValueError("notification_from_email is required when SES is enabled")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return one immutable-by-convention settings instance per process."""
    return Settings()
