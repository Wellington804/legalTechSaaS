import asyncio
import base64
import hashlib
import hmac
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from fastapi import HTTPException

from app.api.v1.endpoints.notifications import enforce_dispatch_rate_limit
from app.core.redis_cache import cache_manager
from app.models.notification import NotificationDelivery
from app.schemas.notification import NotificationDispatchRequest
from app.services.engagement_service import delivery_context
from app.services.notification_providers import send_evolution, send_resend
from app.services.tasks import _process_notification
from app.services.notification_service import (
    apply_provider_event,
    delivery_scope,
    next_delivery_status,
    resend_retry_window_open,
    verify_resend_signature,
)


class FakeClient:
    def __init__(self, result):
        self.result = result
        self.request_headers = None
        self.request_json = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    async def post(self, _url, *, headers, json):
        self.request_headers = headers
        self.request_json = json
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class FakeRedis:
    def __init__(self, count):
        self.count = count

    async def eval(self, *_):
        return self.count


class FakeScalars:
    def __init__(self, value):
        self.value = value

    def first(self):
        return self.value


class FakeResult:
    def __init__(self, value):
        self.value = value

    def scalars(self):
        return FakeScalars(self.value)


class EventDatabase:
    bind = None

    def __init__(self, delivery):
        self.delivery = delivery
        self.statement = None
        self.events = []
        self.commits = 0

    async def execute(self, statement):
        self.statement = statement
        return FakeResult(self.delivery)

    async def flush(self):
        return None

    def add(self, event):
        self.events.append(event)

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        raise AssertionError("rollback is not expected")


class RollbackEventDatabase(EventDatabase):
    def __init__(self, delivery):
        super().__init__(delivery)
        self.rollbacks = 0

    async def rollback(self):
        self.rollbacks += 1


class DeliveryContextDatabase:
    bind = None

    def __init__(self, message, case, client, channel):
        self.message = message
        self.case = case
        self.client = client
        self.channel = channel
        self.statement = None

    async def execute(self, statement):
        self.statement = statement
        return SimpleNamespace(first=lambda: (self.message, self.case, self.client))

    async def scalar(self, _statement):
        return self.channel


class NotificationSecurityTests(unittest.TestCase):
    def test_whatsapp_recipient_accepts_brazilian_format(self):
        request = NotificationDispatchRequest(
            resource_ref="case-message:1",
            recipient="(11) 99999-9999",
            channel="whatsapp",
        )
        self.assertEqual(request.recipient, "+5511999999999")

    def test_dispatch_rate_limit_fails_closed(self):
        original = cache_manager.redis_client
        user = SimpleNamespace(tenant_id="tenant-a", id="user-a")
        try:
            cache_manager.redis_client = FakeRedis(21)
            with self.assertRaises(HTTPException) as limited:
                asyncio.run(enforce_dispatch_rate_limit(user))
            self.assertEqual(limited.exception.status_code, 429)

            cache_manager.redis_client = None
            with self.assertRaises(HTTPException) as unavailable:
                asyncio.run(enforce_dispatch_rate_limit(user))
            self.assertEqual(unavailable.exception.status_code, 503)
        finally:
            cache_manager.redis_client = original

    def test_late_sent_event_cannot_downgrade_terminal_state(self):
        self.assertEqual(next_delivery_status("delivered", "sent"), "delivered")
        self.assertEqual(next_delivery_status("failed", "sent"), "failed")
        self.assertEqual(next_delivery_status("delivered", "failed"), "failed")

    def test_resend_recovery_window_is_strictly_24_hours(self):
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        self.assertFalse(resend_retry_window_open(None, now=now))
        self.assertTrue(resend_retry_window_open(now - timedelta(hours=23, minutes=59), now=now))
        self.assertFalse(resend_retry_window_open(now - timedelta(hours=24), now=now))

    def test_delivery_identity_and_queries_are_tenant_scoped(self):
        unique = next(
            constraint
            for constraint in NotificationDelivery.__table__.constraints
            if constraint.name == "uq_notification_delivery_identity"
        )
        self.assertEqual(
            [column.name for column in unique.columns],
            ["tenant_id", "resource_ref", "recipient_hash", "channel"],
        )
        sql = str(
            delivery_scope("delivery-a", "tenant-b").compile(
                compile_kwargs={"literal_binds": True}
            )
        )
        self.assertIn("notification_deliveries.id = 'delivery-a'", sql)
        self.assertIn("notification_deliveries.tenant_id = 'tenant-b'", sql)

    def test_resend_signature_rejects_invalid_and_replayed_payloads(self):
        raw = b'{"type":"email.delivered"}'
        message_id = "msg_123"
        timestamp = str(int(time.time()))
        key = b"test-webhook-key"
        secret = "whsec_" + base64.b64encode(key).decode("ascii")
        signed = f"{message_id}.{timestamp}.".encode() + raw
        signature = "v1," + base64.b64encode(
            hmac.new(key, signed, hashlib.sha256).digest()
        ).decode("ascii")

        self.assertTrue(
            verify_resend_signature(
                raw,
                message_id=message_id,
                timestamp=timestamp,
                signatures=signature,
                secret=secret,
            )
        )
        self.assertFalse(
            verify_resend_signature(
                raw + b" ",
                message_id=message_id,
                timestamp=timestamp,
                signatures=signature,
                secret=secret,
            )
        )
        self.assertFalse(
            verify_resend_signature(
                raw,
                message_id=message_id,
                timestamp=str(int(timestamp) - 301),
                signatures=signature,
                secret=secret,
                now=int(timestamp),
            )
        )

    def test_evolution_timeout_is_unknown_and_not_retryable(self):
        fake = FakeClient(httpx.ReadTimeout("ambiguous"))
        provider_settings = SimpleNamespace(
            EVOLUTION_GO_URL="http://evolution-go:8080",
        )
        with (
            patch("app.services.notification_providers.settings", provider_settings),
            patch("app.services.notification_providers.httpx.AsyncClient", return_value=fake),
        ):
            result = asyncio.run(send_evolution("+5511999999999", instance_id="instance-id", api_key="instance-key"))
        self.assertEqual(result.status, "unknown")
        self.assertFalse(result.retryable)

    def test_resend_uses_delivery_id_as_idempotency_key(self):
        response = httpx.Response(200, json={"id": "email-id"})
        fake = FakeClient(response)
        provider_settings = SimpleNamespace(
            RESEND_API_KEY="secret",
            RESEND_FROM_EMAIL="LegalTech <noreply@example.test>",
        )
        with (
            patch("app.services.notification_providers.settings", provider_settings),
            patch("app.services.notification_providers.httpx.AsyncClient", return_value=fake),
        ):
            result = asyncio.run(send_resend("delivery-id", "client@example.test"))
        self.assertEqual(result.status, "sent")
        self.assertEqual(fake.request_headers["Idempotency-Key"], "delivery-id")

    def test_case_bound_provider_context_overrides_generic_message_and_instance(self):
        response = httpx.Response(200, json={"messageId": "whatsapp-id"})
        fake = FakeClient(response)
        provider_settings = SimpleNamespace(
            EVOLUTION_GO_URL="http://evolution-go:8080",
        )
        with (
            patch("app.services.notification_providers.settings", provider_settings),
            patch("app.services.notification_providers.httpx.AsyncClient", return_value=fake),
        ):
            result = asyncio.run(
                send_evolution(
                    "+5511999999999",
                    text="Mensagem vinculada ao caso",
                    instance_id="tenant-instance",
                    api_key="tenant-key",
                )
            )
        self.assertEqual(result.status, "sent")
        self.assertEqual(fake.request_headers["apikey"], "tenant-key")
        self.assertEqual(fake.request_headers["instanceId"], "tenant-instance")
        self.assertEqual(fake.request_json["text"], "Mensagem vinculada ao caso")

    def test_evolution_never_falls_back_to_global_instance_credentials(self):
        result = asyncio.run(send_evolution("+5511999999999"))
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.error_code, "provider_not_configured")

    def test_provider_event_locks_delivery_before_updating_status(self):
        delivery = SimpleNamespace(
            id="delivery-id",
            tenant_id="tenant-id",
            status="sent",
            error_code="old-error",
            sent_at=None,
            delivered_at=None,
        )
        db = EventDatabase(delivery)

        self.assertTrue(
            asyncio.run(
                apply_provider_event(
                    db,
                    provider="resend",
                    provider_message_id="message-id",
                    event_identity="event-id",
                    event_type="email.delivered",
                    status="delivered",
                )
            )
        )
        sql = str(db.statement.compile(compile_kwargs={"literal_binds": True}))
        self.assertIn("FOR UPDATE", sql)
        self.assertEqual(delivery.status, "delivered")
        self.assertEqual(db.commits, 1)
        self.assertEqual(len(db.events), 2)  # hashed inbox receipt + tenant event

    def test_hardened_worker_does_not_send_legacy_unbound_delivery(self):
        claimed = ("email", "client@example.test", 1)
        hardened = SimpleNamespace(
            is_hardened_environment=True,
            UNBOUND_NOTIFICATION_DISPATCH_ENABLED=False,
        )
        with (
            patch("app.services.tasks._claim_notification", return_value=("claimed", claimed)),
            patch("app.services.tasks._delivery_context", return_value=None),
            patch("app.services.tasks._block_unbound_notification") as block,
            patch("app.core.config.settings", hardened),
            patch("app.services.notification_providers.send_resend") as send,
        ):
            result = asyncio.run(_process_notification("delivery-id", "tenant-id", True))
        self.assertEqual(result, "blocked")
        block.assert_awaited_once_with("delivery-id", "tenant-id", 1)
        send.assert_not_called()

    def test_delivery_context_uses_case_message_and_tenant_email(self):
        message = SimpleNamespace(body="Atualização vinculada ao caso")
        case = SimpleNamespace(archived_at=None)
        client = SimpleNamespace(stage="client", email="client@example.test")
        channel = SimpleNamespace(email_enabled=True)
        db = DeliveryContextDatabase(message, case, client, channel)
        delivery = SimpleNamespace(
            id="delivery-id",
            tenant_id="tenant-a",
            resource_ref="case-message:message-id",
            channel="email",
            recipient="client@example.test",
        )
        context = asyncio.run(delivery_context(db, delivery))
        self.assertEqual(
            context,
            {"text": "Atualização vinculada ao caso", "subject": "Mensagem do seu escritório"},
        )

    def test_expected_tenant_rejects_cross_tenant_webhook_mapping(self):
        delivery = SimpleNamespace(
            id="delivery-id",
            tenant_id="tenant-b",
            status="sent",
            error_code=None,
            sent_at=None,
            delivered_at=None,
        )
        db = RollbackEventDatabase(delivery)
        with patch(
            "app.services.notification_service._provider_delivery",
            return_value=(delivery, "tenant-b"),
        ):
            applied = asyncio.run(
                apply_provider_event(
                    db,
                    provider="evolution",
                    provider_message_id="message-id",
                    event_identity="event-id",
                    event_type="Receipt.Delivered",
                    status="delivered",
                    expected_tenant_id="tenant-a",
                )
            )
        self.assertFalse(applied)
        self.assertEqual(db.rollbacks, 1)
        self.assertEqual(db.commits, 0)
        self.assertEqual(delivery.status, "sent")


if __name__ == "__main__":
    unittest.main()
