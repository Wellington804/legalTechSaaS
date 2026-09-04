import asyncio
import unittest
from types import SimpleNamespace

from fastapi import HTTPException
from pydantic import ValidationError

from app.api.v1.endpoints.audit import list_audit_logs
from app.core.config import Settings


class NoQueryDatabase:
    async def execute(self, _statement):
        raise AssertionError("unauthorized audit readers must not query logs")


class SecurityGuardsTests(unittest.TestCase):
    def test_hardened_environment_rejects_prototype_modules(self):
        safe_settings = {
            "SECRET_KEY": "a" * 64,
            "COOKIE_SECURE": True,
            "DATABASE_URL": "postgresql+asyncpg://app:secure-db-pass@db.example.test:5432/legaltech",
            "REDIS_URL": "redis://:secure-redis-pass@redis.example.test:6379/0",
            "CORS_ORIGINS": ["https://app.example.test"],
            "ALLOWED_HOSTS": ["app.example.test"],
            "FRONTEND_URL": "https://app.example.test",
            "ACCOUNT_TOKEN_PEPPER": "test-pepper-" * 4,
            "MFA_ENCRYPTION_KEY": "A" * 43 + "=",
            "_env_file": None,
        }
        for environment in ("staging", "production"):
            Settings(ENVIRONMENT=environment, **safe_settings)
            with self.assertRaises(ValidationError) as caught:
                Settings(
                    ENVIRONMENT=environment,
                    PROTOTYPE_MODULES_ENABLED=True,
                    **safe_settings,
                )
            self.assertIn("prototype modules cannot be enabled", str(caught.exception))

    def test_audit_logs_require_admin_or_partner(self):
        user = SimpleNamespace(role="lawyer", tenant_id="tenant-id")
        with self.assertRaises(HTTPException) as caught:
            asyncio.run(list_audit_logs(current_user=user, db=NoQueryDatabase()))
        self.assertEqual(caught.exception.status_code, 403)

    def test_hardened_escavador_requires_api_and_callback_tokens(self):
        safe_settings = {
            "SECRET_KEY": "a" * 64,
            "COOKIE_SECURE": True,
            "DATABASE_URL": "postgresql+asyncpg://app:secure-db-pass@db.example.test:5432/legaltech",
            "REDIS_URL": "redis://:secure-redis-pass@redis.example.test:6379/0",
            "CORS_ORIGINS": ["https://app.example.test"],
            "ALLOWED_HOSTS": ["app.example.test"],
            "FRONTEND_URL": "https://app.example.test",
            "ACCOUNT_TOKEN_PEPPER": "test-pepper-" * 4,
            "MFA_ENCRYPTION_KEY": "A" * 43 + "=",
            "ESCAVADOR_ENABLED": True,
            "JUDICIAL_MONITORING_PROVIDER": "escavador",
            "_env_file": None,
        }
        with self.assertRaises(ValidationError) as caught:
            Settings(ENVIRONMENT="production", **safe_settings)
        self.assertIn("Escavador enabled without API token", str(caught.exception))
        self.assertIn("Escavador enabled without callback token", str(caught.exception))

        Settings(
            ENVIRONMENT="production",
            ESCAVADOR_API_TOKEN="api-token",
            ESCAVADOR_CALLBACK_TOKEN="callback-token",
            **safe_settings,
        )

    def test_hardened_judicial_connectors_fail_closed(self):
        safe_settings = {
            "SECRET_KEY": "a" * 64,
            "COOKIE_SECURE": True,
            "DATABASE_URL": "postgresql+asyncpg://app:secure-db-pass@db.example.test:5432/legaltech",
            "REDIS_URL": "redis://:secure-redis-pass@redis.example.test:6379/0",
            "CORS_ORIGINS": ["https://app.example.test"],
            "ALLOWED_HOSTS": ["app.example.test"],
            "FRONTEND_URL": "https://app.example.test",
            "ACCOUNT_TOKEN_PEPPER": "test-pepper-" * 4,
            "MFA_ENCRYPTION_KEY": "A" * 43 + "=",
            "_env_file": None,
        }
        with self.assertRaises(ValidationError) as caught:
            Settings(ENVIRONMENT="production", DJEN_API_URL="https://attacker.invalid/djen", **safe_settings)
        self.assertIn("approved CNJ HTTPS host", str(caught.exception))

        with self.assertRaises(ValidationError) as caught:
            Settings(
                ENVIRONMENT="production",
                DOMICILIO_JUDICIAL_API_URL="https://domicilio.example.test/events",
                **safe_settings,
            )
        self.assertIn("Domicilio Judicial configuration is incomplete", str(caught.exception))

        with self.assertRaises(ValidationError) as caught:
            Settings(
                ENVIRONMENT="production",
                JUDICIAL_MONITORING_PROVIDER="tribunal_api",
                TRIBUNAL_SOURCE_CONNECTORS={
                    "tjsp": {
                        "url": "https://tribunal.example.test/events",
                        "token": "secret",
                        "homologated": False,
                    }
                },
                **safe_settings,
            )
        self.assertIn("no homologated connector", str(caught.exception))

    def test_hardened_calendar_oauth_requires_complete_public_endpoints(self):
        safe_settings = {
            "SECRET_KEY": "a" * 64,
            "COOKIE_SECURE": True,
            "DATABASE_URL": "postgresql+asyncpg://app:secure-db-pass@db.example.test:5432/legaltech",
            "REDIS_URL": "redis://:secure-redis-pass@redis.example.test:6379/0",
            "CORS_ORIGINS": ["https://app.example.test"],
            "ALLOWED_HOSTS": ["app.example.test"],
            "FRONTEND_URL": "https://app.example.test",
            "ACCOUNT_TOKEN_PEPPER": "test-pepper-" * 4,
            "MFA_ENCRYPTION_KEY": "A" * 43 + "=",
            "_env_file": None,
        }
        with self.assertRaises(ValidationError) as caught:
            Settings(
                ENVIRONMENT="production",
                GOOGLE_CALENDAR_CLIENT_ID="client",
                **safe_settings,
            )
        self.assertIn("Google Calendar OAuth configuration is incomplete", str(caught.exception))

        Settings(
            ENVIRONMENT="production",
            GOOGLE_CALENDAR_CLIENT_ID="client",
            GOOGLE_CALENDAR_CLIENT_SECRET="secret",
            GOOGLE_CALENDAR_REDIRECT_URI="https://app.example.test/api/v1/integrations/calendar-oauth/google/callback",
            GOOGLE_CALENDAR_WEBHOOK_URL="https://app.example.test/api/v1/integrations/calendar-webhooks/google",
            **safe_settings,
        )
