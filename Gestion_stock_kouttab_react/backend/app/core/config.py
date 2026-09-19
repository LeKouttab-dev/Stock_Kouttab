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

    # Pool de connexions. Reglable par l'environnement depuis que la base est
    # jointe par le reseau : un mutualise plafonne max_user_connections, et
    # `recycle` doit rester SOUS le wait_timeout du serveur (souvent 300 s),
    # sinon on reutilise des connexions deja fermees d'en face.
    db_pool_size: int = Field(default=5, alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=0, alias="DB_MAX_OVERFLOW")
    db_pool_recycle: int = Field(default=280, alias="DB_POOL_RECYCLE")

    # SSO entrant — passage signé depuis gestion.lekouttab.fr.
    # Secret partagé DÉDIÉ (jamais JWT_SECRET_KEY) : vide = fonctionnalité coupée,
    # l'endpoint d'échange répond alors 404 et rien n'existe.
    # Générer avec : python -c "import secrets; print(secrets.token_urlsafe(48))"
    sso_shared_secret: str = Field(default="", alias="SSO_SHARED_SECRET")
    sso_issuer: str = Field(default="gestion.lekouttab.fr", alias="SSO_ISSUER")
    sso_audience: str = Field(default="stock.lekouttab.fr", alias="SSO_AUDIENCE")
    sso_max_age_seconds: int = Field(default=60, alias="SSO_MAX_AGE_SECONDS")

    # JWT
    jwt_secret_key: str = Field(default="change-me", alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_access_token_minutes: int = Field(default=30, alias="JWT_ACCESS_TOKEN_MINUTES")
    jwt_refresh_token_days: int = Field(default=7, alias="JWT_REFRESH_TOKEN_DAYS")

    # SMTP
    # Coupe-circuit d'envoi. A `false`, tout courriel est journalise puis
    # abandonne, sans ouvrir de connexion SMTP. Indispensable en developpement :
    # le `.env` local porte les identifiants du serveur de messagerie reel de
    # l'association, et une seance de tests sur les notes de frais suffit a
    # ecrire a de vrais destinataires.
    email_enabled: bool = Field(default=True, alias="EMAIL_ENABLED")
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
    # URL de l'outil de gestion (gestion.lekouttab.fr) : les courriels y
    # renvoient les comptes « BenevoleFrais », qui n'ont pas de mot de passe
    # stock. Defaut = la production, pour ne JAMAIS empecher un demarrage
    # faute de variable posee a la main sur le VPS.
    gestion_url: str = Field(default="https://gestion.lekouttab.fr", alias="GESTION_URL")
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

    # Cle de la tablette de caisse (buvette encaissee par SumUp). Une cle et non
    # une session : la tablette reste en caisse des journees entieres, un jeton
    # de 30 minutes la deconnecterait en plein service. Vide = routes /caisse
    # inexistantes (404), comme le passage signe.
    # Generer avec : python -c "import secrets; print(secrets.token_urlsafe(48))"
    caisse_api_key: str = Field(default="", alias="CAISSE_API_KEY")

    # Google Agenda (onglet Calendrier) — compte de service Google Cloud avec
    # delegation a l'echelle du domaine, en LECTURE SEULE.
    #
    # La cle du compte de service tient dans le .env (JSON brut ou base64 du
    # JSON) plutot que dans un fichier monte : le compose du VPS ne monte que
    # `uploads` et `outbox`, et ajouter un volume imposerait de le recopier a
    # la main sur le serveur (cf. DEPLOIEMENT-VPS.md §13). Un chemin reste
    # accepte pour le developpement local.
    google_service_account_json: str = Field(
        default="", alias="GOOGLE_SERVICE_ACCOUNT_JSON"
    )
    google_service_account_file: str = Field(
        default="", alias="GOOGLE_SERVICE_ACCOUNT_FILE"
    )
    # Compte Workspace impersonne par le compte de service. C'est LUI qui decide
    # des agendas visibles : l'application voit exactement ce que voit ce compte,
    # y compris les agendas crees demain. Vide = fonctionnalite coupee.
    google_calendar_subject: str = Field(default="", alias="GOOGLE_CALENDAR_SUBJECT")
    # Agendas reserves au Super Admin (identifiants separes par des virgules).
    # Pense pour les rendez-vous de sante, donnees sensibles au sens du RGPD :
    # ils remontent bien dans l'application, mais pas dans l'onglet de tous.
    google_calendar_restricted_raw: str = Field(
        default="", alias="GOOGLE_CALENDAR_RESTRICTED"
    )
    # Duree de vie du cache memoire des evenements. 42 agendas = 42 appels a
    # Google par fenetre affichee : sans cache, chaque changement de mois d'un
    # utilisateur en declencherait autant.
    google_calendar_cache_seconds: int = Field(
        default=180, alias="GOOGLE_CALENDAR_CACHE_SECONDS"
    )

    # Cle de chiffrement du RIB au repos (AES-256-GCM, base64 de 32 octets).
    # La perdre rend les RIB deja enregistres definitivement illisibles :
    # elle se sauvegarde avec le reste du .env, hors du depot.
    rib_encryption_key: str = Field(default="", alias="RIB_ENCRYPTION_KEY")

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
        # Sans cle, les RIB repartiraient en clair dans la base sans que rien ne
        # le signale — exactement la situation que le chiffrement corrige.
        if not self.rib_encryption_key.strip():
            problems.append(
                "RIB_ENCRYPTION_KEY est vide : les RIB seraient ecrits en clair. "
                "Generer une cle avec : python -c "
                '"import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"'
            )
        # Le passage signé ouvre des sessions : un secret partagé faible ou
        # égal au secret JWT rendrait tout access token échangeable.
        sso = self.sso_shared_secret.strip()
        if sso and (len(sso) < 32 or sso in INSECURE_JWT_SECRETS):
            problems.append("SSO_SHARED_SECRET est trop court (32 caractères minimum).")
        if sso and sso == self.jwt_secret_key.strip():
            problems.append("SSO_SHARED_SECRET doit différer de JWT_SECRET_KEY.")
        # La cle de caisse autorise a decrementer le stock : une cle courte se
        # devine, et la reprendre d'un autre secret ferait fuir les deux a la fois.
        caisse = self.caisse_api_key.strip()
        if caisse and (len(caisse) < 32 or caisse in INSECURE_JWT_SECRETS):
            problems.append("CAISSE_API_KEY est trop courte (32 caractères minimum).")
        if caisse and caisse in (self.jwt_secret_key.strip(), sso):
            problems.append("CAISSE_API_KEY doit différer des autres secrets.")
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
    def google_calendar_restricted(self) -> List[str]:
        return [
            c.strip()
            for c in self.google_calendar_restricted_raw.split(",")
            if c.strip()
        ]

    @property
    def google_calendar_configured(self) -> bool:
        """Vrai si l'onglet Calendrier peut interroger Google.

        Le compte impersonne est aussi obligatoire que la cle : sans lui, le
        compte de service n'a acces a aucun agenda et l'API repondrait par une
        liste vide, ce qui ressemble a « aucun evenement » et non a « pas
        configure ».
        """
        a_une_cle = bool(
            self.google_service_account_json.strip()
            or self.google_service_account_file.strip()
        )
        return a_une_cle and bool(self.google_calendar_subject.strip())

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
