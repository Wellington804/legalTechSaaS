import asyncio
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from fastapi import HTTPException

from app.api.v1.endpoints.account import OfficeUpdate, ProfileUpdate, _account_email_ready, _trusted_frontend_url
from app.api.v1.endpoints.auth import _profile, _registration_is_allowed
from app.core.dependencies import ensure_tenant_write_access, require_privileged_mfa
from app.core.security import (
    _totp_at,
    decrypt_mfa_secret,
    encrypt_mfa_secret,
    hash_account_token,
    matching_totp_counter,
    verify_totp_code,
)
from app.models.tenant import Tenant
from app.models.user import User


class TenantDatabase:
    def __init__(self, tenant):
        self.tenant = tenant

    async def scalar(self, _statement):
        return self.tenant


class AccountSecurityTests(unittest.TestCase):
    def test_pilot_can_disable_mfa_gate_without_bypassing_email_approval(self):
        from app.core import dependencies

        original = dependencies.settings
        dependencies.settings = SimpleNamespace(
            is_hardened_environment=True,
            PRIVILEGED_MFA_REQUIRED=False,
        )
        user = SimpleNamespace(email_verified_at=None, role="admin")
        try:
            with self.assertRaises(HTTPException) as caught:
                asyncio.run(require_privileged_mfa(SimpleNamespace(state=SimpleNamespace()), user))
            self.assertEqual(caught.exception.status_code, 403)
            user.email_verified_at = datetime.now(timezone.utc)
            self.assertIs(
                asyncio.run(require_privileged_mfa(SimpleNamespace(state=SimpleNamespace()), user)),
                user,
            )
        finally:
            dependencies.settings = original

    def test_pilot_registration_allowlist_is_case_insensitive_and_optional(self):
        from app.api.v1.endpoints import auth

        original = auth.settings
        try:
            auth.settings = SimpleNamespace(PILOT_ALLOWED_REGISTRATION_EMAILS=[])
            self.assertTrue(_registration_is_allowed("qualquer@example.test"))
            auth.settings = SimpleNamespace(PILOT_ALLOWED_REGISTRATION_EMAILS=[" DCSLESSA@GMAIL.COM "])
            self.assertTrue(_registration_is_allowed("dcslessa@gmail.com"))
            self.assertFalse(_registration_is_allowed("outro@gmail.com"))
        finally:
            auth.settings = original

    def test_account_phone_contracts_store_brazilian_e164(self):
        self.assertEqual(ProfileUpdate(professional_phone="(11) 99999-9999").professional_phone, "+5511999999999")
        self.assertEqual(OfficeUpdate(name="Escritório", office_phone="11999999999").office_phone, "+5511999999999")

    def test_totp_accepts_current_window_and_rejects_wrong_code(self):
        secret = "JBSWY3DPEHPK3PXP"
        timestamp = 1_700_000_000
        code = _totp_at(secret, timestamp)
        self.assertTrue(verify_totp_code(secret, code, now=timestamp))
        self.assertTrue(verify_totp_code(secret, code, now=timestamp + 30))
        self.assertEqual(
            matching_totp_counter(secret, code, now=timestamp), timestamp // 30
        )
        self.assertFalse(verify_totp_code(secret, "000000", now=timestamp))

    def test_mfa_secret_is_encrypted_and_account_tokens_are_hashed(self):
        secret = "JBSWY3DPEHPK3PXP"
        encrypted = encrypt_mfa_secret(secret)
        self.assertNotEqual(encrypted, secret)
        self.assertEqual(decrypt_mfa_secret(encrypted), secret)
        self.assertNotEqual(hash_account_token("single-use-token"), "single-use-token")

    def test_expired_trial_blocks_writes_but_active_subscription_does_not(self):
        expired_trial = Tenant(
            id="tenant-a",
            name="Test",
            slug="test-a",
            is_active=True,
            subscription_status="trial",
            trial_ends_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
        with self.assertRaises(HTTPException) as caught:
            asyncio.run(ensure_tenant_write_access(TenantDatabase(expired_trial), "tenant-a"))
        self.assertEqual(caught.exception.status_code, 402)

        active = Tenant(
            id="tenant-a",
            name="Test",
            slug="test-a",
            is_active=True,
            subscription_status="active",
        )
        self.assertIs(
            asyncio.run(ensure_tenant_write_access(TenantDatabase(active), "tenant-a")), active
        )

    def test_active_subscription_is_read_only_after_its_period_ends(self):
        expired_active = Tenant(
            id="tenant-a",
            name="Test",
            slug="test-a",
            is_active=True,
            subscription_status="active",
            subscription_ends_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
        with self.assertRaises(HTTPException) as caught:
            asyncio.run(ensure_tenant_write_access(TenantDatabase(expired_active), "tenant-a"))
        self.assertEqual(caught.exception.status_code, 402)

        current_active = Tenant(
            id="tenant-a",
            name="Test",
            slug="test-a",
            is_active=True,
            subscription_status="active",
            subscription_ends_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
        self.assertIs(
            asyncio.run(ensure_tenant_write_access(TenantDatabase(current_active), "tenant-a")),
            current_active,
        )

    def test_account_email_requires_explicit_enabled_provider_and_trusted_origin(self):
        from app.api.v1.endpoints import account

        original = account.settings
        account.settings = SimpleNamespace(
            ACCOUNT_EMAILS_ENABLED=True,
            RESEND_ENABLED=True,
            NOTIFICATIONS_DRY_RUN=False,
            RESEND_API_KEY="test-key",
            RESEND_FROM_EMAIL="security@example.test",
            FRONTEND_URL="https://app.example.test",
            CORS_ORIGINS=["https://app.example.test"],
        )
        try:
            self.assertTrue(_account_email_ready())
            self.assertEqual(_trusted_frontend_url(), "https://app.example.test")
        finally:
            account.settings = original

    def test_profile_exposes_nullable_office_cnpj(self):
        tenant = Tenant(
            id="tenant-a",
            name="Test",
            slug="test-a",
            cnpj="12.345.678/0001-99",
        )
        user = User(
            id="user-a",
            tenant_id=tenant.id,
            full_name="Test User",
            email="user@example.test",
            hashed_password="not-used-by-this-test",
            role="admin",
        )
        self.assertEqual(_profile(user, tenant)["tenant_cnpj"], "12.345.678/0001-99")

    def test_profile_requires_email_verification_only_in_hardened_environment(self):
        from app.api.v1.endpoints import auth

        tenant = Tenant(id="tenant-a", name="Test", slug="test-a")
        user = User(
            id="user-a",
            tenant_id=tenant.id,
            full_name="Test User",
            email="user@example.test",
            hashed_password="not-used-by-this-test",
            role="admin",
        )
        original = auth.settings
        auth.settings = SimpleNamespace(is_hardened_environment=True, PRIVILEGED_MFA_REQUIRED=True)
        try:
            self.assertTrue(_profile(user, tenant)["email_verification_required"])
            user.email_verified_at = datetime.now(timezone.utc)
            self.assertFalse(_profile(user, tenant)["email_verification_required"])
            auth.settings.PRIVILEGED_MFA_REQUIRED = False
            self.assertFalse(_profile(user, tenant)["mfa_required"])
        finally:
            auth.settings = original


if __name__ == "__main__":
    unittest.main()
