"""Runtime settings. Authentication and database configuration fail closed."""
from pathlib import Path
from typing import List, Union
from urllib.parse import urlparse
from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Only PostgreSQL is supported. There is no SQLite fallback.
    DATABASE_URL: SecretStr | None = None

    # Generic OIDC resource-server settings. The token must be an access token
    # whose issuer, audience and RS256 signature match these settings.
    OIDC_ISSUER: str | None = None
    OIDC_JWKS_URL: str | None = None
    OIDC_AUDIENCE: str | None = None
    CONSENT_POLICY_VERSION: str | None = None

    HOST: str = "127.0.0.1"
    PORT: int = 8000
    DEBUG: bool = False
    LOG_LEVEL: str = "info"
    ALLOWED_ORIGINS: Union[List[str], str] = ["http://localhost", "http://10.0.2.2"]

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def require_postgresql(cls, value):
        if value is None or value == "":
            return None
        raw = value.get_secret_value() if isinstance(value, SecretStr) else str(value)
        if raw.startswith("postgresql://"):
            raw = "postgresql+psycopg://" + raw.removeprefix("postgresql://")
        if not raw.startswith("postgresql+psycopg://"):
            raise ValueError("DATABASE_URL must use PostgreSQL with the psycopg 3 driver")
        return raw

    @field_validator("OIDC_ISSUER", "OIDC_JWKS_URL", "OIDC_AUDIENCE", "CONSENT_POLICY_VERSION", mode="before")
    @classmethod
    def empty_optional_values_are_missing(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value.strip() if isinstance(value, str) else value

    @field_validator("OIDC_ISSUER", "OIDC_JWKS_URL")
    @classmethod
    def require_https_identity_metadata(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("OIDC issuer and JWKS URLs must use HTTPS")
        # Issuer comparison is exact per OIDC; preserve any trailing slash.
        return value

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, value: Union[str, List[str]]) -> List[str]:
        if isinstance(value, str):
            if value.startswith("[") and value.endswith("]"):
                import json
                try:
                    value = json.loads(value)
                except ValueError:
                    value = value[1:-1].split(",")
            else:
                value = value.split(",")
        if not isinstance(value, list):
            return ["http://localhost", "http://10.0.2.2"]
        origins = [str(origin).strip() for origin in value if str(origin).strip()]
        if "*" in origins:
            raise ValueError("Wildcard CORS origins are not allowed")
        return origins

    @property
    def oidc_configured(self) -> bool:
        return bool(self.OIDC_ISSUER and self.OIDC_JWKS_URL and self.OIDC_AUDIENCE)


settings = Settings()
