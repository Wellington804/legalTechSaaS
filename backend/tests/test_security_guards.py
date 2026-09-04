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
