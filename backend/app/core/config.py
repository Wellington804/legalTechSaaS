from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    PROJECT_NAME: str = "LegalTech SaaS Enterprise"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: Literal["development", "test", "staging", "production"] = "development"
    RELEASE: str | None = None
    PROTOTYPE_MODULES_ENABLED: bool = False

    # Local defaults are rejected by the hardened-environment validator below.
    SECRET_KEY: str = "development-only-change-me-32-bytes"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    COOKIE_NAME: str = "lexflow_session"
    COOKIE_SECURE: bool = False
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres_password@localhost:5432/legaltech_db"
    REDIS_URL: str = "redis://localhost:6379/0"
    CORS_ORIGINS: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )
    ALLOWED_HOSTS: list[str] = Field(
        default_factory=lambda: ["localhost", "127.0.0.1", "testserver"]
    )

    SENTRY_DSN: str | None = None
    SUPPORT_URL: str | None = None
    FRONTEND_URL: str = "http://localhost:3000"
    ACCOUNT_TOKEN_PEPPER: str | None = None
    MFA_ENCRYPTION_KEY: str | None = None
    PRIVILEGED_MFA_REQUIRED: bool = True
    ACCOUNT_EMAILS_ENABLED: bool = False
    NOTIFICATION_PROCESSING_TIMEOUT_SECONDS: int = Field(default=900, ge=60)
    NOTIFICATION_RECONCILE_BATCH_SIZE: int = Field(default=100, ge=1, le=500)
    NOTIFICATION_MAX_DELIVERY_ATTEMPTS: int = Field(default=5, ge=1, le=20)
    NOTIFICATION_RETRY_DELAY_SECONDS: int = Field(default=60, ge=10, le=3600)
    DEFAULT_TRIAL_DAYS: int = Field(default=14, ge=1, le=90)
    PILOT_ALLOWED_REGISTRATION_EMAILS: list[str] = Field(default_factory=list)
    TRIAL_QUOTA_USERS: int = Field(default=3, ge=1)
    TRIAL_QUOTA_STORAGE_BYTES: int = Field(default=1073741824, ge=10485760)
    TRIAL_QUOTA_MESSAGES: int = Field(default=100, ge=0)

    R2_ENABLED: bool = False
    R2_ACCOUNT_ID: str | None = None
    R2_BUCKET_NAME: str | None = None
    R2_ACCESS_KEY_ID: str | None = None
    R2_SECRET_ACCESS_KEY: str | None = None
    CLAMAV_HOST: str = "clamav"
    CLAMAV_PORT: int = Field(default=3310, ge=1, le=65535)

    DATAJUD_ENABLED: bool = False
    DATAJUD_API_KEY: str | None = None
    JUDICIAL_MONITORING_PROVIDER: Literal["datajud", "escavador"] = "datajud"
    ESCAVADOR_ENABLED: bool = False
    ESCAVADOR_API_TOKEN: str | None = None
    ESCAVADOR_CALLBACK_TOKEN: str | None = None
    AI_ENABLED: bool = False
    AI_PROVIDER: Literal["gemini", "openrouter"] = "gemini"
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = ""
    OPENROUTER_API_KEY: str | None = None
    OPENROUTER_MODEL: str = ""
    OPENROUTER_GENERAL_MODEL: str = ""
    OPENROUTER_GENERAL_REASONING: Literal["minimal", "low", "medium", "high", "xhigh", "max"] = "low"
    OPENROUTER_DEEP_MODEL: str = ""
    OPENROUTER_DEEP_REASONING: Literal["minimal", "low", "medium", "high", "xhigh", "max"] = "max"
    OPENROUTER_LEGAL_MODEL: str = ""
    OPENROUTER_VISUAL_API_KEY: str | None = None
    OPENROUTER_VISUAL_MODEL: str = ""
    OPENROUTER_IMAGE_MODEL: str = ""
    OPENROUTER_APP_NAME: str = "LexFlow"
    # Image generation is a separate, explicitly enabled provider capability.
    BRAND_IMAGE_AI_ENABLED: bool = False
    GEMINI_IMAGE_MODEL: str = ""
    # Zero disables only the daily AI quota; provider-side billing limits still apply.
    AI_REQUESTS_PER_DAY: int = Field(default=20, ge=0, le=1000)

    WEB_PUSH_ENABLED: bool = False
    WEB_PUSH_VAPID_PUBLIC_KEY: str | None = None
    WEB_PUSH_VAPID_PRIVATE_KEY: str | None = None
    WEB_PUSH_VAPID_SUBJECT: str | None = None

    NOTIFICATIONS_DRY_RUN: bool = True
    UNBOUND_NOTIFICATION_DISPATCH_ENABLED: bool = False
    RESEND_ENABLED: bool = False
    RESEND_API_KEY: str | None = None
    RESEND_FROM_EMAIL: str | None = None
    RESEND_WEBHOOK_SECRET: str | None = None
    EVOLUTION_ENABLED: bool = False
    EVOLUTION_GO_URL: str = "http://evolution-go:4000"
    EVOLUTION_API_KEY: str | None = None

    @property
    def is_hardened_environment(self) -> bool:
        return self.ENVIRONMENT in {"staging", "production"}

    @model_validator(mode="after")
    def reject_unsafe_deployment_settings(self) -> "Settings":
        if self.SUPPORT_URL:
            import ipaddress
            import re
            support = urlsplit(self.SUPPORT_URL)
            host = support.hostname or ""
            try:
                ipaddress.ip_address(host)
                public_host = False
            except ValueError:
                public_host = "." in host and not host.endswith((".localhost", ".local", ".invalid"))
            email_contact = support.scheme == "mailto" and bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", support.path)) and not support.query
            web_contact = support.scheme == "https" and public_host and not support.username and not support.password and support.port in {None, 443}
            if len(self.SUPPORT_URL) > 2048 or any(c.isspace() for c in self.SUPPORT_URL) or support.fragment or not (email_contact or web_contact):
                raise ValueError("SUPPORT_URL must be a mailto contact or public HTTPS address without credentials")
        if self.WEB_PUSH_ENABLED:
            import hmac
            import ipaddress
            import re
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.primitives.asymmetric import ec
            from app.schemas.push import decode_url_key

            try:
                private = ec.derive_private_key(int.from_bytes(decode_url_key(self.WEB_PUSH_VAPID_PRIVATE_KEY or "", 32), "big"), ec.SECP256R1())
                public = private.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
                if not hmac.compare_digest(public, decode_url_key(self.WEB_PUSH_VAPID_PUBLIC_KEY or "", 65)):
                    raise ValueError("mismatched keys")
            except ValueError as exc:
                raise ValueError("Web Push requires a matching base64url P-256 VAPID key pair") from exc
            subject = urlsplit(self.WEB_PUSH_VAPID_SUBJECT or "")
            host = (subject.hostname if subject.scheme == "https" else subject.path.rsplit("@", 1)[-1]) or ""
            host = host.lower().rstrip(".")
            if not ((subject.scheme == "mailto" and re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", subject.path) and not subject.query)
                    or (subject.scheme == "https" and subject.hostname and not subject.username and not subject.password)) or subject.fragment:
                raise ValueError("Web Push requires a mailto or HTTPS contact subject")
            try:
                ipaddress.ip_address(host)
                is_ip = True
            except ValueError:
                is_ip = False
            if self.is_hardened_environment and (not host or "." not in host or is_ip or host in {"localhost", "example.com", "example.org", "example.net"} or host.endswith((".invalid", ".localhost", ".test", ".example", ".example.com", ".example.org", ".example.net"))):
                raise ValueError("Web Push production subject must be a real public contact")
        if not self.is_hardened_environment:
            return self

        problems: list[str] = []
        if len(self.SECRET_KEY) < 64:
            problems.append("SECRET_KEY must be a random value with at least 64 characters")
        if not self.COOKIE_SECURE:
            problems.append("COOKIE_SECURE must be enabled")
        frontend = urlsplit(self.FRONTEND_URL)
        if frontend.scheme != "https" or self.FRONTEND_URL.rstrip("/") not in {origin.rstrip("/") for origin in self.CORS_ORIGINS}:
            problems.append("FRONTEND_URL must be an explicit HTTPS CORS origin")
        if not self.ACCOUNT_TOKEN_PEPPER or len(self.ACCOUNT_TOKEN_PEPPER) < 32:
            problems.append("ACCOUNT_TOKEN_PEPPER must be an independent random value (32+ characters)")
        try:
            from cryptography.fernet import Fernet
            Fernet((self.MFA_ENCRYPTION_KEY or "").encode())
        except (ValueError, TypeError):
            problems.append("MFA_ENCRYPTION_KEY must be a Fernet key")
        if self.ACCOUNT_EMAILS_ENABLED and (not self.RESEND_ENABLED or self.NOTIFICATIONS_DRY_RUN):
            problems.append("Account emails require enabled, live Resend")
        if self.DATAJUD_ENABLED and not self.DATAJUD_API_KEY:
            problems.append("DataJud enabled without API key")
        if self.ESCAVADOR_ENABLED and not self.ESCAVADOR_API_TOKEN:
            problems.append("Escavador enabled without API token")
        if self.ESCAVADOR_ENABLED and not self.ESCAVADOR_CALLBACK_TOKEN:
            problems.append("Escavador enabled without callback token")
        monitoring_enabled = self.DATAJUD_ENABLED or self.ESCAVADOR_ENABLED
        if monitoring_enabled and self.JUDICIAL_MONITORING_PROVIDER == "datajud" and not self.DATAJUD_ENABLED:
            problems.append("selected judicial monitoring provider DataJud is disabled")
        if monitoring_enabled and self.JUDICIAL_MONITORING_PROVIDER == "escavador" and not self.ESCAVADOR_ENABLED:
            problems.append("selected judicial monitoring provider Escavador is disabled")
        if self.AI_ENABLED and self.AI_PROVIDER == "gemini" and (not self.GEMINI_API_KEY or not self.GEMINI_MODEL):
            problems.append("Gemini AI enabled without API key and model")
        if self.AI_ENABLED and self.AI_PROVIDER == "openrouter" and (
            not self.OPENROUTER_API_KEY or not (self.OPENROUTER_GENERAL_MODEL or self.OPENROUTER_MODEL)
        ):
            problems.append("OpenRouter AI enabled without API key and model")
        if self.R2_ENABLED and not all((self.R2_ACCOUNT_ID, self.R2_BUCKET_NAME, self.R2_ACCESS_KEY_ID, self.R2_SECRET_ACCESS_KEY)):
            problems.append("R2 enabled without account, bucket and S3 credentials")
        image_model = self.OPENROUTER_IMAGE_MODEL if self.AI_PROVIDER == "openrouter" else self.GEMINI_IMAGE_MODEL
        if self.BRAND_IMAGE_AI_ENABLED and (not self.AI_ENABLED or not image_model):
            problems.append("Brand image AI requires enabled AI and an image model")

        database = urlsplit(self.DATABASE_URL)
        if database.scheme != "postgresql+asyncpg" or database.hostname in {None, "localhost", "127.0.0.1"}:
            problems.append("DATABASE_URL must use postgresql+asyncpg and a non-local host")
        if database.password in {None, "postgres", "postgres_password", "password"}:
            problems.append("DATABASE_URL must contain a non-default password")

        redis = urlsplit(self.REDIS_URL)
        if redis.scheme not in {"redis", "rediss"} or redis.hostname in {None, "localhost", "127.0.0.1"}:
            problems.append("REDIS_URL must use redis/rediss and a non-local host")
        if not redis.password:
            problems.append("REDIS_URL must authenticate in staging/production")

        for origin in self.CORS_ORIGINS:
            parsed = urlsplit(origin)
            if parsed.scheme != "https" or not parsed.hostname or parsed.hostname in {"localhost", "127.0.0.1"}:
                problems.append(f"unsafe CORS origin: {origin}")
        if not self.ALLOWED_HOSTS or "*" in self.ALLOWED_HOSTS:
            problems.append("ALLOWED_HOSTS must be explicit")
        if self.SENTRY_DSN and urlsplit(self.SENTRY_DSN).scheme != "https":
            problems.append("SENTRY_DSN must use HTTPS")
        if self.RESEND_ENABLED and not all(
            [self.RESEND_API_KEY, self.RESEND_FROM_EMAIL, self.RESEND_WEBHOOK_SECRET]
        ):
            problems.append("Resend enabled without API key, sender and webhook secret")
        if self.EVOLUTION_ENABLED:
            evolution = urlsplit(self.EVOLUTION_GO_URL)
            if evolution.scheme not in {"http", "https"} or not evolution.hostname or evolution.username or evolution.password:
                problems.append("Evolution Go gateway URL is invalid")
            if not self.EVOLUTION_API_KEY or self.NOTIFICATIONS_DRY_RUN:
                problems.append("Evolution Go requires its global API key and live notifications")
            # Instance secrets are encrypted per tenant, not shared by all offices.
        if self.UNBOUND_NOTIFICATION_DISPATCH_ENABLED:
            problems.append("unbound notification dispatch cannot be enabled in a hardened environment")
        if self.PROTOTYPE_MODULES_ENABLED:
            problems.append("prototype modules cannot be enabled in a hardened environment")

        if problems:
            raise ValueError("Unsafe deployment configuration: " + "; ".join(problems))
        return self


settings = Settings()
