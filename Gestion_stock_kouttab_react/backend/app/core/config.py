"""Application settings loaded from environment variables (.env)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


INSECURE_JWT_SECRETS = {"change-me", "change-me-in-production", "secret", ""}


class Settings(BaseSettings):
    """Centralised configuration."""

    # General
    app_env: str = Field(default="development", alias="APP_ENV")
    app_debug: bool = Field(default=False, alias="APP_DEBUG")
    app_name: str = "Kouttab Stock API"
    app_version: str = "1.0.0"

    # Database
    db_host: str = Field(default="localhost", alias="DB_HOST")
    db_port: int = Field(default=3306, alias="DB_PORT")
    db_user: str = Field(default="root", alias="DB_USER")
    db_password: str = Field(default="", alias="DB_PASSWORD")
    db_name: str = Field(default="kouttab_stock", alias="DB_NAME")
    database_url_override: str | None = Field(default=None, alias="DATABASE_URL")

    # JWT
    jwt_secret_key: str = Field(default="change-me", alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_access_token_minutes: int = Field(default=30, alias="JWT_ACCESS_TOKEN_MINUTES")
    jwt_refresh_token_days: int = Field(default=7, alias="JWT_REFRESH_TOKEN_DAYS")

    # SMTP
    smtp_host: str = Field(default="localhost", alias="SMTP_HOST")
    smtp_port: int = Field(default=465, alias="SMTP_PORT")
    smtp_user: str = Field(default="", alias="SMTP_USER")
    smtp_password: str = Field(default="", alias="SMTP_PASSWORD")
    smtp_use_tls: bool = Field(default=True, alias="SMTP_USE_TLS")
    smtp_use_ssl: bool = Field(default=False, alias="SMTP_USE_SSL")
    email_from: str = Field(default="no-reply@lekouttab.fr", alias="EMAIL_FROM")
    email_from_name: str = Field(default="Le Kouttab Stock", alias="EMAIL_FROM_NAME")
    # Destinataires des pieces comptables (factures, tickets), separes par des
    # virgules. Vide = les envois restent en file d'attente sans etre perdus.
    compta_email_raw: str = Field(default="", alias="COMPTA_EMAIL")

    # URLs
    frontend_url: str = Field(default="http://localhost:5173", alias="FRONTEND_URL")
    backend_url: str = Field(default="http://localhost:8000/api", alias="BACKEND_URL")
    cors_origins_raw: str = Field(
        default="http://localhost:5173,https://stock.lekouttab.fr",
        alias="CORS_ORIGINS",
    )

    # Uploads
    upload_dir: str = Field(default="./uploads", alias="UPLOAD_DIR")
    max_upload_mb: int = Field(default=10, alias="MAX_UPLOAD_MB")
    max_request_mb: int = Field(default=50, alias="MAX_REQUEST_MB")

    # PDF prets a l'envoi comptable. Volontairement HORS de upload_dir : le
    # .htaccess laisse passer /backend/uploads/, et ces fichiers portent des noms
    # previsibles ({Pole}_{Evenement}_{Date}.pdf) — les y ecrire rendrait des
    # factures fournisseur telechargeables sans authentification.
    outbox_dir: str = Field(default="./outbox", alias="OUTBOX_DIR")
    max_attachment_total_mb: int = Field(default=15, alias="MAX_ATTACHMENT_TOTAL_MB")

    # Rate limiting
    rate_limit_enabled: bool = Field(default=True, alias="RATE_LIMIT_ENABLED")

    # HelloAsso (Buvette)
    helloasso_api_base: str = Field(
        default="https://api.helloasso.com", alias="HELLOASSO_API_BASE"
    )
    helloasso_client_id: str = Field(default="", alias="HELLOASSO_CLIENT_ID")
    helloasso_client_secret: str = Field(default="", alias="HELLOASSO_CLIENT_SECRET")
    helloasso_org_slug: str = Field(
        default="eclat-education-culture-langues-apprentissage-transmission",
        alias="HELLOASSO_ORG_SLUG",
    )
    helloasso_buvette_form_slug: str = Field(
        default="buvette", alias="HELLOASSO_BUVETTE_FORM_SLUG"
    )
    # Secret partage ajoute a l'URL de webhook enregistree chez HelloAsso.
    # HelloAsso ne signe pas ses notifications ; a defaut de HMAC, un secret
    # dans l'URL evite que n'importe qui puisse forger des ventes et decrementer
    # le stock. Vide = pas de verification (comportement historique).
    helloasso_webhook_secret: str = Field(
        default="", alias="HELLOASSO_WEBHOOK_SECRET"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("cors_origins_raw")
    @classmethod
    def _strip_origins(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def _refuse_insecure_production_config(self) -> "Settings":
        """Empeche le demarrage en production avec une configuration dangereuse.

        Le defaut ``change-me`` est public : signer les JWT avec permettrait a
        n'importe qui de forger un token ``Super Admin``. Mieux vaut un refus de
        demarrage bruyant qu'une application ouverte silencieusement.
        """
        if not self.is_production:
            return self
        problems: list[str] = []
        if self.jwt_secret_key.strip() in INSECURE_JWT_SECRETS:
            problems.append(
                "JWT_SECRET_KEY utilise la valeur par defaut. Generer une cle avec : "
                'python -c "import secrets; print(secrets.token_urlsafe(64))"'
            )
        if self.app_debug:
            problems.append("APP_DEBUG doit valoir false en production.")
        if any(o.startswith("http://") for o in self.cors_origins):
            problems.append("CORS_ORIGINS contient une origine non chiffree (http://).")
        if problems:
            raise ValueError(
                "Configuration de production invalide :\n- " + "\n- ".join(problems)
            )
        return self

    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]

    @property
    def compta_emails(self) -> List[str]:
        return [e.strip() for e in self.compta_email_raw.split(",") if e.strip()]

    @property
    def database_url(self) -> str:
        if self.database_url_override:
            return self.database_url_override
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )

    @property
    def upload_path(self) -> Path:
        return Path(self.upload_dir).resolve()

    @property
    def outbox_path(self) -> Path:
        return Path(self.outbox_dir).resolve()

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor."""
    return Settings()


settings = get_settings()
