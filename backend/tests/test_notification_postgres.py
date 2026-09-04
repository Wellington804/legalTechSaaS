import asyncio
import os
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.models.notification import (
    NotificationDelivery,
    NotificationEvent,
    NotificationProviderReceipt,
)
from app.models.tenant import Tenant
from app.models.user import User
from app.services.notification_service import (
    apply_provider_event,
    create_or_get_delivery,
    get_tenant_delivery,
    reconcile_provider_receipts,
)
from app.services.notification_providers import ProviderResult
from app.services.tasks import _process_notification


AUDIT_TEST_DATABASE_URL = os.environ.get("AUDIT_TEST_DATABASE_URL")


@unittest.skipUnless(
    AUDIT_TEST_DATABASE_URL,
    "set AUDIT_TEST_DATABASE_URL to run PostgreSQL RLS notification tests",
)
class NotificationPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_async_engine(AUDIT_TEST_DATABASE_URL, poolclass=NullPool)
        cls.Session = async_sessionmaker(cls.engine, expire_on_commit=False)
        asyncio.run(cls._assert_runtime_role())

    @classmethod
    def tearDownClass(cls):
        asyncio.run(cls.engine.dispose())

    @classmethod
    async def _assert_runtime_role(cls):
        async with cls.engine.connect() as connection:
            role = (
                await connection.execute(
                    text(
                        "SELECT rolbypassrls, rolsuper "
                        "FROM pg_roles WHERE rolname = current_user"
                    )
                )
            ).one_or_none()
            rls_rows = await connection.execute(
                text(
                    "SELECT relname, relrowsecurity, relforcerowsecurity "
                    "FROM pg_class WHERE relname IN "
                    "('notification_deliveries', 'notification_events', "
                    "'notification_provider_receipts')"
                )
            )
        if not role or role.rolbypassrls or role.rolsuper:
            raise AssertionError("AUDIT_TEST_DATABASE_URL must use a NOBYPASSRLS runtime role")
        rls = {row.relname: (row.relrowsecurity, row.relforcerowsecurity) for row in rls_rows}
        expected_rls = {
            "notification_deliveries": (True, True),
            "notification_events": (True, True),
            "notification_provider_receipts": (True, True),
        }
        if rls != expected_rls:
            raise AssertionError("AUDIT_TEST_DATABASE_URL must enforce RLS on notification tables")

    @staticmethod
    async def _set_tenant(db, tenant_id):
        await db.execute(
            text("SELECT set_config('app.current_tenant', :tenant_id, true)"),
            {"tenant_id": tenant_id},
        )

    @classmethod
    async def _seed_tenant_user(cls):
        tenant_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        async with cls.Session() as db:
            async with db.begin():
                db.add(Tenant(id=tenant_id, name="Audit test", slug=str(uuid.uuid4())))
                db.add(
                    User(
                        id=user_id,
                        tenant_id=tenant_id,
                        full_name="Audit Test User",
                        email=f"{uuid.uuid4()}@example.test",
                        hashed_password="not-used-by-test",
                        role="admin",
                    )
                )
        return tenant_id, user_id

    @classmethod
    async def _create_delivery(cls, tenant_id, user_id, resource_ref=None, channel="email"):
        async with cls.Session() as db:
            async with db.begin():
                await cls._set_tenant(db, tenant_id)
                delivery, existing = await create_or_get_delivery(
                    db,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    resource_ref=resource_ref or f"resource:{uuid.uuid4()}",
                    recipient=(f"+55119{uuid.uuid4().int % 10**8:08d}" if channel == "whatsapp" else f"{uuid.uuid4()}@example.test"),
                    channel=channel,
                )
                return delivery.id, existing

    def test_transaction_local_tenant_does_not_survive_commit_or_rollback(self):
        async def scenario():
            async with self.Session() as db:
                await self._set_tenant(db, "commit-tenant")
                await db.commit()
                after_commit = await db.scalar(
                    text("SELECT current_setting('app.current_tenant', true)")
                )
                await self._set_tenant(db, "rollback-tenant")
                await db.rollback()
                after_rollback = await db.scalar(
                    text("SELECT current_setting('app.current_tenant', true)")
                )
            return after_commit, after_rollback

        after_commit, after_rollback = asyncio.run(scenario())
        self.assertNotEqual(after_commit, "commit-tenant")
        self.assertNotEqual(after_rollback, "rollback-tenant")

    def test_concurrent_duplicate_delivery_uses_savepoint_and_keeps_tenant_scope(self):
        async def scenario():
            tenant_id, user_id = await self._seed_tenant_user()
            resource_ref = f"resource:{uuid.uuid4()}"
            recipient = f"{uuid.uuid4()}@example.test"
            initial_selects = asyncio.Barrier(2)

            async def request():
                async with self.Session() as db:
                    async with db.begin():
                        await self._set_tenant(db, tenant_id)
                        execute = db.execute
                        first_select = True

                        async def synchronize_initial_select(statement, *args, **kwargs):
                            nonlocal first_select
                            result = await execute(statement, *args, **kwargs)
                            if first_select:
                                first_select = False
                                await initial_selects.wait()
                            return result

                        db.execute = synchronize_initial_select
                        return await create_or_get_delivery(
                            db,
                            tenant_id=tenant_id,
                            user_id=user_id,
                            resource_ref=resource_ref,
                            recipient=recipient,
                            channel="email",
                        )

            first_result, duplicate_result = await asyncio.wait_for(
                asyncio.gather(request(), request()), timeout=5
            )
            async with self.Session() as db:
                async with db.begin():
                    await self._set_tenant(db, tenant_id)
                    delivery_count = await db.scalar(
                        select(func.count(NotificationDelivery.id)).where(
                            NotificationDelivery.tenant_id == tenant_id,
                            NotificationDelivery.resource_ref == resource_ref,
                        )
                    )
            return first_result, duplicate_result, delivery_count

        first_result, duplicate_result, delivery_count = asyncio.run(scenario())
        self.assertEqual(first_result[0].id, duplicate_result[0].id)
        self.assertEqual(sorted([first_result[1], duplicate_result[1]]), [False, True])
        self.assertEqual(delivery_count, 1)

    def test_tenant_cannot_read_another_tenant_delivery(self):
        async def scenario():
            first_tenant, first_user = await self._seed_tenant_user()
            second_tenant, _ = await self._seed_tenant_user()
            delivery_id, _ = await self._create_delivery(first_tenant, first_user)
            async with self.Session() as db:
                async with db.begin():
                    await self._set_tenant(db, second_tenant)
                    other_tenant_delivery = await db.scalar(
                        select(NotificationDelivery).where(NotificationDelivery.id == delivery_id)
                    )
            async with self.Session() as db:
                async with db.begin():
                    no_context_delivery = await db.scalar(
                        select(NotificationDelivery).where(NotificationDelivery.id == delivery_id)
                    )
            async with self.Session() as db:
                async with db.begin():
                    await self._set_tenant(db, second_tenant)
                    scoped_delivery = await get_tenant_delivery(db, delivery_id, second_tenant)
            return other_tenant_delivery, no_context_delivery, scoped_delivery

        self.assertEqual(asyncio.run(scenario()), (None, None, None))

    def test_concurrent_provider_events_preserve_failed_terminal_status(self):
        async def scenario():
            tenant_id, user_id = await self._seed_tenant_user()
            delivery_id, _ = await self._create_delivery(tenant_id, user_id)
            provider_message_id = f"message-{uuid.uuid4()}"
            async with self.Session() as db:
                async with db.begin():
                    await self._set_tenant(db, tenant_id)
                    delivery = await db.get(NotificationDelivery, delivery_id)
                    delivery.status = "sent"
                    delivery.provider_message_id = provider_message_id

            start = asyncio.Event()

            async def apply(event_type, status):
                await start.wait()
                async with self.Session() as db:
                    return await apply_provider_event(
                        db,
                        provider="resend",
                        provider_message_id=provider_message_id,
                        event_identity=f"event-{uuid.uuid4()}",
                        event_type=event_type,
                        status=status,
                    )

            delivered = asyncio.create_task(apply("email.delivered", "delivered"))
            failed = asyncio.create_task(apply("email.failed", "failed"))
            start.set()
            results = await asyncio.gather(delivered, failed)
            async with self.Session() as db:
                async with db.begin():
                    await self._set_tenant(db, tenant_id)
                    delivery = await db.get(NotificationDelivery, delivery_id)
                    event_count = await db.scalar(
                        select(func.count(NotificationEvent.id)).where(
                            NotificationEvent.delivery_id == delivery_id
                        )
                    )
            return results, delivery.status, event_count

        results, final_status, event_count = asyncio.run(scenario())
        self.assertEqual(results, [True, True])
        self.assertEqual(final_status, "failed")
        self.assertEqual(event_count, 2)

    def test_early_provider_receipt_is_hashed_then_reconciled(self):
        async def scenario():
            tenant_id, user_id = await self._seed_tenant_user()
            provider_message_id = f"message-{uuid.uuid4()}"
            async with self.Session() as db:
                accepted = await apply_provider_event(
                    db,
                    provider="resend",
                    provider_message_id=provider_message_id,
                    event_identity=f"receipt-{uuid.uuid4()}",
                    event_type="email.delivered",
                    status="delivered",
                )
            delivery_id, _ = await self._create_delivery(tenant_id, user_id)
            async with self.Session() as db:
                async with db.begin():
                    await self._set_tenant(db, tenant_id)
                    delivery = await db.get(NotificationDelivery, delivery_id)
                    delivery.status = "sent"
                    delivery.provider_message_id = provider_message_id
                    reconciled = await reconcile_provider_receipts(db, delivery)
            async with self.Session() as db:
                async with db.begin():
                    await self._set_tenant(db, tenant_id)
                    delivery = await db.get(NotificationDelivery, delivery_id)
                    receipt = await db.scalar(
                        select(NotificationProviderReceipt).where(
                            NotificationProviderReceipt.delivery_id == delivery_id
                        )
                    )
            return accepted, reconciled, delivery.status, receipt, provider_message_id

        accepted, reconciled, status, receipt, provider_message_id = asyncio.run(scenario())
        self.assertTrue(accepted)
        self.assertEqual(reconciled, 1)
        self.assertEqual(status, "delivered")
        self.assertNotEqual(receipt.provider_message_hash, provider_message_id)
        self.assertEqual(len(receipt.provider_message_hash), 64)

    def test_recovery_discovers_durable_queued_work_without_bypassing_runtime_rls(self):
        async def scenario():
            tenant_id, user_id = await self._seed_tenant_user()
            delivery_id, _ = await self._create_delivery(tenant_id, user_id)
            async with self.Session() as db:
                rows = await db.execute(
                    text("SELECT delivery_id, tenant_id FROM notification_recovery_candidates(50, 900)")
                )
                return {(row.delivery_id, row.tenant_id) for row in rows}, delivery_id, tenant_id

        candidates, delivery_id, tenant_id = asyncio.run(scenario())
        self.assertIn((delivery_id, tenant_id), candidates)

    def test_stale_outcomes_do_not_send_after_the_safe_window(self):
        async def scenario(channel):
            tenant_id, user_id = await self._seed_tenant_user()
            delivery_id, _ = await self._create_delivery(tenant_id, user_id, channel=channel)
            async with self.Session() as db:
                async with db.begin():
                    await self._set_tenant(db, tenant_id)
                    delivery = await db.get(NotificationDelivery, delivery_id)
                    delivery.status = "processing"
                    delivery.processing_started_at = datetime.now(timezone.utc) - timedelta(hours=25)
                    if channel == "email":
                        delivery.provider_attempted_at = delivery.processing_started_at
            with patch("app.core.database.AsyncSessionLocal", self.Session):
                result = await _process_notification(delivery_id, tenant_id, can_retry=True)
            async with self.Session() as db:
                async with db.begin():
                    await self._set_tenant(db, tenant_id)
                    delivery = await db.get(NotificationDelivery, delivery_id)
            return result, delivery.status, delivery.attempts

        email = asyncio.run(scenario("email"))
        whatsapp = asyncio.run(scenario("whatsapp"))
        self.assertEqual(email, ("unknown", "unknown", 0))
        self.assertEqual(whatsapp, ("unknown", "unknown", 0))

    def test_concurrent_whatsapp_claim_sends_once_and_does_not_mark_live_work_unknown(self):
        async def scenario():
            tenant_id, user_id = await self._seed_tenant_user()
            delivery_id, _ = await self._create_delivery(
                tenant_id, user_id, channel="whatsapp"
            )
            send_started = asyncio.Event()
            release_send = asyncio.Event()
            provider_message_id = f"whatsapp-message-{uuid.uuid4()}"
            send_calls = 0

            async def send_evolution(_recipient, **_kwargs):
                nonlocal send_calls
                send_calls += 1
                send_started.set()
                await release_send.wait()
                return ProviderResult("sent", message_id=provider_message_id)

            with (
                patch("app.core.database.AsyncSessionLocal", self.Session),
                patch("app.services.notification_providers.provider_is_configured", return_value=True),
                patch("app.services.notification_providers.send_evolution", new=send_evolution),
            ):
                first = asyncio.create_task(
                    _process_notification(delivery_id, tenant_id, can_retry=True)
                )
                try:
                    await asyncio.wait_for(send_started.wait(), timeout=5)
                except TimeoutError:
                    if first.done():
                        await first
                    raise
                duplicate_result = await _process_notification(
                    delivery_id, tenant_id, can_retry=True
                )
                release_send.set()
                first_result = await first

            async with self.Session() as db:
                async with db.begin():
                    await self._set_tenant(db, tenant_id)
                    delivery = await db.get(NotificationDelivery, delivery_id)
            return duplicate_result, first_result, delivery, provider_message_id, send_calls

        duplicate_result, first_result, delivery, provider_message_id, send_calls = asyncio.run(scenario())
        self.assertEqual(duplicate_result, "busy")
        self.assertEqual(first_result, "sent")
        self.assertEqual(delivery.status, "sent")
        self.assertEqual(delivery.provider_message_id, provider_message_id)
        self.assertEqual(delivery.attempts, 1)
        self.assertEqual(send_calls, 1)
