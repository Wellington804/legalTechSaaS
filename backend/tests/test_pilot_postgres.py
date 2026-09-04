"""Pilot controls over real authenticated HTTP and restricted PostgreSQL."""
import os
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from sqlalchemy import text
from app.core.config import settings
from app.core.dependencies import _set_tenant_context
from tests import test_connected_postgres as connected


@unittest.skipUnless(os.environ.get("AUDIT_TEST_DATABASE_URL"), "Requires disposable PostgreSQL")
class PilotHTTPTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = connected.ConnectedPostgresTests.asyncSetUp
    asyncTearDown = connected.ConnectedPostgresTests.asyncTearDown
    client = connected.ConnectedPostgresTests.client
    request = connected.ConnectedPostgresTests.request
    register = connected.ConnectedPostgresTests.register

    async def test_onboarding_is_derived_and_feedback_is_private_idempotent_even_after_trial(self):
        a, profile = await self.register()
        b, _ = await self.register()
        overview = await self.request(a, "GET", "/pilot/overview")
        self.assertTrue(overview["subscription"]["write_allowed"])
        self.assertTrue(all(step["status"] == "pending" for step in overview["steps"]))
        self.assertFalse(overview["security"]["https_configured"])
        await self.request(a, "PATCH", "/account/profile", json={"full_name": "Advogado Piloto", "oab_number": "12345", "oab_uf": "SP"})
        await self.request(a, "POST", "/workspace/clients", 201, json={"name": "Cliente fictício"})
        overview = await self.request(a, "GET", "/pilot/overview")
        self.assertEqual([s["id"] for s in overview["steps"] if s["status"] == "done"], ["profile", "client"])
        self.assertTrue(all(s["status"] == "pending" for s in (await self.request(b, "GET", "/pilot/overview"))["steps"]))
        body = {"request_id": str(uuid.uuid4()), "kind": "weekly", "area": "clients", "message": "Cadastro concluído com ajuda.", "completed_steps": ["client"], "help_steps": ["client"], "consent": True}
        sent = await self.request(a, "POST", "/pilot/feedback", 201, json=body)
        self.assertEqual(sent["id"], (await self.request(a, "POST", "/pilot/feedback", 201, json=body))["id"])
        await self.request(a, "POST", "/pilot/feedback", 409, json={**body, "message": "Outro relato"})
        self.assertEqual((await self.request(b, "GET", "/pilot/feedback"))["items"], [])
        await self.request(a, "POST", "/pilot/feedback", 403, json=body, headers={"Origin": "https://evil.test"})
        async with self.Session() as db:
            await _set_tenant_context(db, profile["tenant_id"])
            await db.execute(text("UPDATE tenants SET trial_ends_at=:end WHERE id=:id"), {"id": profile["tenant_id"], "end": datetime.now(timezone.utc) - timedelta(days=1)})
            await db.commit()
        overview = await self.request(a, "GET", "/pilot/overview")
        self.assertFalse(overview["subscription"]["write_allowed"])
        self.assertEqual(overview["subscription"]["days_remaining"], 0)
        self.assertIsNotNone(overview["weekly"]["last_report_at"])
        await self.request(a, "POST", "/workspace/clients", 402, json={"name": "Bloqueado"})
        await self.request(a, "POST", "/pilot/feedback", 201, json={**body, "request_id": str(uuid.uuid4()), "kind": "problem"})

    async def test_mfa_login_recovery_and_session_revocation_with_real_database(self):
        a, profile = await self.register()
        setup = await self.request(a, "POST", "/account/mfa/setup", json={})
        import time
        from app.core.security import _totp_at
        confirmation = await self.request(a, "POST", "/account/mfa/confirm", json={"code": _totp_at(setup["secret"], int(time.time()))})
        self.assertTrue((await self.request(a, "GET", "/account/profile"))["mfa_enabled"])
        code = confirmation["recovery_codes"][0]
        await self.request(a, "POST", "/auth/logout", 204)
        await self.request(a, "POST", "/auth/login", 401, json={"email": profile["email"], "password": "Disposable-Check-123456"})
        await self.request(a, "POST", "/auth/login", json={"email": profile["email"], "password": "Disposable-Check-123456", "otp_code": code})
        cookie = a.cookies.get(settings.COOKIE_NAME)
        await self.request(a, "POST", "/account/sessions/revoke-all", 204, json={})
        replay = self.client()
        replay.cookies.set(settings.COOKIE_NAME, cookie)
        await self.request(replay, "GET", "/auth/me", 401)
        await self.request(a, "POST", "/auth/login", 401, json={"email": profile["email"], "password": "Disposable-Check-123456", "otp_code": code})

    async def test_email_verification_and_password_reset_are_single_use_and_revoke_sessions(self):
        a, profile = await self.register()
        cookie = a.cookies.get(settings.COOKIE_NAME)
        # Only e-mail transport is replaced; tokens, password hashing, sessions and HTTP are real.
        with patch("app.api.v1.endpoints.account._send_account_email", new_callable=AsyncMock) as send:
            await self.request(a, "POST", "/account/email-verifications/request", 202, json={})
            token = send.call_args.kwargs["raw_token"]
        await self.request(self.client(), "POST", "/account/email-verifications/confirm", 204, json={"token": token})
        await self.request(self.client(), "POST", "/account/email-verifications/confirm", 400, json={"token": token})
        self.assertTrue((await self.request(a, "GET", "/account/profile"))["email_verified"])
        with patch("app.api.v1.endpoints.account._account_email_ready", return_value=True), patch("app.api.v1.endpoints.account._send_account_email", new_callable=AsyncMock) as send:
            await self.request(self.client(), "POST", "/account/password-resets/request", 202, json={"email": profile["email"]})
            reset = send.call_args.kwargs["raw_token"]
        new_password = "New-Disposable-Pilot-123456"
        await self.request(self.client(), "POST", "/account/password-resets/confirm", 204, json={"token": reset, "new_password": new_password})
        await self.request(self.client(), "POST", "/account/password-resets/confirm", 400, json={"token": reset, "new_password": new_password})
        replay = self.client()
        replay.cookies.set(settings.COOKIE_NAME, cookie)
        await self.request(replay, "GET", "/auth/me", 401)
        await self.request(a, "POST", "/auth/login", 401, json={"email": profile["email"], "password": "Disposable-Check-123456"})
        await self.request(a, "POST", "/auth/login", json={"email": profile["email"], "password": new_password})
