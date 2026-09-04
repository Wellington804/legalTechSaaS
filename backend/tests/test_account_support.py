import argparse
import json
import unittest
from contextlib import redirect_stderr
from datetime import datetime, timezone
from io import StringIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.cli import account_support
from app.models.account import PrivacyRequest, SubscriptionRequest
from app.models.tenant import Tenant
from app.models.user import User


class FakeScalars:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class FakeSession:
    def __init__(self, scalar_values, rows=None):
        self.bind = SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))
        self.scalar_values = iter(scalar_values)
        self.rows = rows or []
        self.statements = []
        self.committed = False

    async def scalar(self, statement):
        self.statements.append(statement)
        return next(self.scalar_values)

    async def scalars(self, statement):
        self.statements.append(statement)
        return FakeScalars(self.rows)

    async def commit(self):
        self.committed = True


class FakeSessionFactory:
    def __init__(self, session):
        self.session = session

    def __call__(self):
        return self

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, traceback):
        return False


def support_args(**overrides):
    values = {
        "command": "set-subscription-status",
        "tenant_id": "tenant-a",
        "status": "active",
        "plan": "professional",
        "quota_users": 12,
        "quota_storage_bytes": 2_000_000,
        "quota_messages": 400,
        "ends_at": datetime(2027, 1, 1, tzinfo=timezone.utc),
        "request_id": "request-a",
        "operator": "support@example.test",
        "reason": "Ajuste aprovado pelo suporte.",
    }
    values.update(overrides)
    return argparse.Namespace(**values)


class AccountSupportInputTests(unittest.TestCase):
    def test_reason_quota_and_timezone_validation_are_strict(self):
        with self.assertRaises(SystemExit):
            account_support.validate_args(support_args(reason="  "))
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit):
            account_support.parse_args(
                ["set-subscription-status", "--tenant-id", "tenant-a", "--status", "active", "--operator", "support", "--reason", "ok", "--quota-users", "0"]
            )
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit):
            account_support.parse_args(
                ["set-subscription-status", "--tenant-id", "tenant-a", "--status", "active", "--operator", "support", "--reason", "ok", "--ends-at", "2027-01-01T10:00:00"]
            )
        ends_at = account_support.parse_aware_datetime("2027-01-01T10:00:00-03:00")
        self.assertEqual(ends_at, datetime(2027, 1, 1, 13, tzinfo=timezone.utc))

    def test_pilot_email_approval_requires_a_valid_email_and_reason(self):
        args = argparse.Namespace(command="approve-pilot-email", user_email=" ADVOGADO@EXAMPLE.TEST ", operator="ops", reason="Confirmação por chamada.")
        self.assertEqual(account_support.validate_args(args).user_email, "advogado@example.test")
        with self.assertRaises(SystemExit):
            account_support.validate_args(argparse.Namespace(command="approve-pilot-email", user_email="invalido", operator="ops", reason="ok"))


class AccountSupportCommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_pilot_email_approval_is_audited(self):
        user = User(id="user-a", tenant_id="tenant-a", email="advogado@example.test", email_verified_at=None)
        db = FakeSession([user])
        audit = AsyncMock()
        args = argparse.Namespace(user_email="advogado@example.test", operator="ops@example.test", reason="Identidade confirmada no piloto privado.")
        with patch.object(account_support, "AsyncSessionLocal", FakeSessionFactory(db)), patch.object(account_support.AuditService, "log_action", audit), patch("builtins.print"):
            await account_support.approve_pilot_email(args)
        self.assertTrue(db.committed)
        self.assertIsNotNone(user.email_verified_at)
        self.assertEqual(audit.await_args.kwargs["action"], "SUPPORT_PILOT_EMAIL_APPROVED")
        self.assertEqual(audit.await_args.kwargs["resource_id"], "user-a")

    async def test_privacy_resolution_is_tenant_scoped_and_audited(self):
        tenant = Tenant(id="tenant-a")
        request = PrivacyRequest(id="privacy-a", tenant_id="tenant-a", request_type="export", scope="self", status="received")
        db = FakeSession([tenant, request])
        audit = AsyncMock()
        args = argparse.Namespace(tenant_id="tenant-a", request_id="privacy-a", status="completed", operator="privacy@example.com", resolution_note="Export entregue em canal autenticado.")
        with patch.object(account_support, "AsyncSessionLocal", FakeSessionFactory(db)), patch.object(account_support.AuditService, "log_action", audit), patch("builtins.print"):
            await account_support.resolve_privacy_request(args)
        self.assertTrue(db.committed)
        self.assertEqual(request.status, "completed")
        self.assertEqual(request.resolution_note, args.resolution_note)
        audit.assert_awaited_once()

    async def test_support_update_resolves_same_tenant_pending_request_and_audits(self):
        tenant = Tenant(id="tenant-a", subscription_status="past_due", subscription_plan="starter")
        request = SubscriptionRequest(id="request-a", tenant_id="tenant-a", request_type="subscription", status="received")
        db = FakeSession([tenant, request])
        audit = AsyncMock()
        with patch.object(account_support, "AsyncSessionLocal", FakeSessionFactory(db)), patch.object(
            account_support.AuditService, "log_action", audit
        ), patch("builtins.print"):
            await account_support.set_subscription_status(support_args())

        self.assertTrue(db.committed)
        self.assertEqual(tenant.subscription_status, "active")
        self.assertEqual(tenant.subscription_plan, "professional")
        self.assertEqual((tenant.quota_users, tenant.quota_storage_bytes, tenant.quota_messages), (12, 2_000_000, 400))
        self.assertEqual(tenant.subscription_ends_at, datetime(2027, 1, 1, tzinfo=timezone.utc))
        self.assertEqual(request.status, "resolved")
        self.assertIsNotNone(request.resolved_at)
        self.assertIn("FOR UPDATE", str(db.statements[1]))
        self.assertEqual(audit.await_args.kwargs["details"]["subscription_request_id"], "request-a")
        self.assertEqual(audit.await_args.kwargs["details"]["reason"], "Ajuste aprovado pelo suporte.")

    async def test_request_id_must_belong_to_a_pending_request_for_the_tenant(self):
        tenant = Tenant(id="tenant-a", subscription_status="past_due", subscription_plan="starter")
        db = FakeSession([tenant, None])
        audit = AsyncMock()
        with patch.object(account_support, "AsyncSessionLocal", FakeSessionFactory(db)), patch.object(
            account_support.AuditService, "log_action", audit
        ), self.assertRaisesRegex(SystemExit, "Pending subscription request"):
            await account_support.set_subscription_status(support_args())

        self.assertFalse(db.committed)
        audit.assert_not_awaited()
        self.assertEqual(tenant.subscription_status, "past_due")

    async def test_pending_list_emits_metadata_without_request_message(self):
        tenant = Tenant(id="tenant-a")
        request = SubscriptionRequest(
            id="request-a",
            tenant_id="tenant-a",
            request_type="cancellation",
            status="in_progress",
            message="Conteúdo que não deve ser exibido.",
            created_at=datetime(2026, 8, 27, 12, tzinfo=timezone.utc),
        )
        db = FakeSession([tenant], rows=[request])
        with patch.object(account_support, "AsyncSessionLocal", FakeSessionFactory(db)), patch("builtins.print") as print_mock:
            await account_support.list_pending_requests(argparse.Namespace(tenant_id="tenant-a"))

        payload = json.loads(print_mock.call_args.args[0])
        self.assertEqual(payload["id"], "request-a")
        self.assertNotIn("message", payload)
        self.assertIn("'in_progress'", str(db.statements[1].compile(compile_kwargs={"literal_binds": True})))


if __name__ == "__main__":
    unittest.main()
