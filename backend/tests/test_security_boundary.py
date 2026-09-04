import asyncio
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from fastapi import HTTPException
from pydantic import ValidationError
from starlette.requests import Request
from starlette.responses import Response

from app.api.v1.endpoints.auth import UserLogin, _enforce_auth_rate_limit, _session_lifetime, _set_session_cookie, create_session_token
from app.api.v1.endpoints.oab import get_application_checklist
from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.redis_cache import cache_manager
from app.core.security import create_access_token, decode_token


def request_with_bearer(token: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"authorization", f"Bearer {token}".encode())],
            "query_string": b"",
            "server": ("test", 80),
            "client": ("127.0.0.1", 1234),
            "scheme": "http",
        }
    )


class InvalidTokenDatabase:
    bind = None

    async def execute(self, statement):
        raise AssertionError("invalid tokens must be rejected before querying the database")


class MissingApplicationDatabase:
    def __init__(self):
        self.statement = None

    async def scalar(self, statement):
        self.statement = statement
        return None


class RateLimitRedis:
    def __init__(self, count: int):
        self.count = count
        self.key = None

    async def eval(self, _script, _keys, source_key, account_key, _window):
        self.key = f"{source_key}:{account_key}"
        return [self.count, self.count]


class SecurityBoundaryTests(unittest.TestCase):
    def test_remember_me_uses_a_strict_fourteen_day_session(self):
        self.assertEqual(_session_lifetime(), timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
        self.assertEqual(_session_lifetime(True), timedelta(days=14))
        self.assertFalse(UserLogin(email="user@example.com", password="password1").remember_me)
        with self.assertRaises(ValidationError):
            UserLogin(email="user@example.com", password="password1", remember_me="yes")
        response = Response()
        _set_session_cookie(response, "token", remember_me=True)
        self.assertIn("Max-Age=1209600", response.headers["set-cookie"])

        class SessionDB:
            bind = None
            session = None

            def add(self, session):
                session.id = "session-id"
                self.session = session

            async def flush(self):
                pass

        db = SessionDB()
        before = datetime.now(timezone.utc) + timedelta(days=14)
        token = asyncio.run(create_session_token(db, SimpleNamespace(id="user", tenant_id="tenant"), remember_me=True))
        after = datetime.now(timezone.utc) + timedelta(days=14)
        claims = decode_token(token)
        self.assertEqual(claims["exp"] - claims["iat"], 1209600)
        self.assertEqual(claims["sid"], "session-id")
        self.assertLessEqual(before, db.session.expires_at)
        self.assertLessEqual(db.session.expires_at, after)

    def test_invalid_token_is_rejected_before_database_access(self):
        with self.assertRaises(HTTPException) as caught:
            asyncio.run(
                get_current_user(
                    request=request_with_bearer("not-a-jwt"),
                    db=InvalidTokenDatabase(),
                )
            )
        self.assertEqual(caught.exception.status_code, 401)

    def test_bearer_token_is_not_an_authentication_path(self):
        token = create_access_token("user-a", "tenant-a")
        with self.assertRaises(HTTPException) as caught:
            asyncio.run(
                get_current_user(
                    request=request_with_bearer(token),
                    db=InvalidTokenDatabase(),
                )
            )
        self.assertEqual(caught.exception.status_code, 401)

    def test_oab_application_lookup_is_tenant_scoped(self):
        db = MissingApplicationDatabase()
        user = SimpleNamespace(id="user-a", tenant_id="tenant-a")

        with self.assertRaises(HTTPException) as caught:
            asyncio.run(
                get_application_checklist(
                    app_id="application-from-tenant-b",
                    current_user=user,
                    db=db,
                )
            )

        self.assertEqual(caught.exception.status_code, 404)
        query = str(db.statement.compile(compile_kwargs={"literal_binds": True}))
        self.assertIn("oab_applications.tenant_id = 'tenant-a'", query)
        self.assertIn("oab_applications.id = 'application-from-tenant-b'", query)

    def test_login_rate_limit_uses_hashed_identity_and_blocks(self):
        original = cache_manager.redis_client
        fake = RateLimitRedis(11)
        cache_manager.redis_client = fake
        try:
            with self.assertRaises(HTTPException) as caught:
                asyncio.run(
                    _enforce_auth_rate_limit(
                        "login",
                        request_with_bearer("unused"),
                        "client@example.test",
                        limit=10,
                        window_seconds=300,
                    )
                )
        finally:
            cache_manager.redis_client = original
        self.assertEqual(caught.exception.status_code, 429)
        self.assertNotIn("client@example.test", fake.key)


if __name__ == "__main__":
    unittest.main()
