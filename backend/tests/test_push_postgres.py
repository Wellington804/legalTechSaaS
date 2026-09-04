"""Enforced-RLS tests against a migrated disposable PostgreSQL database; no push network."""
import asyncio
import os
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.v1.endpoints import push as api
from app.core.dependencies import _set_tenant_context
from app.models.account import AuthSession
from app.models.push import PushDelivery, PushSubscription
from app.models.tenant import Tenant
from app.models.user import User
from app.models.workspace import WorkspaceCase, WorkspaceClient, WorkspaceTask
from app.schemas.push import PushSubscriptionCreate
from app.services import push_tasks, push_service
from app.services.push_provider import PushResult
from tests.test_push import subscription_data


@unittest.skipUnless(os.environ.get("AUDIT_TEST_DATABASE_URL"), "Requires disposable PostgreSQL runtime-role database")
class PushPostgresTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine(os.environ["AUDIT_TEST_DATABASE_URL"], poolclass=NullPool)
        self.Session = async_sessionmaker(self.engine, expire_on_commit=False, autoflush=False)
        self.config = SimpleNamespace(WEB_PUSH_ENABLED=True, WEB_PUSH_VAPID_PUBLIC_KEY="test-public-key")
        self.patches = [patch.object(module, "settings", self.config) for module in (api, push_tasks, push_service)]
        self.patches.append(patch.object(push_tasks, "AsyncSessionLocal", self.Session))
        for item in self.patches:
            item.start()
        self.tenant_id, self.other_tenant = str(uuid.uuid4()), str(uuid.uuid4())
        self.user_id, self.other_user_id, self.session_id = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        async with self.Session() as db:
            role = (await db.execute(text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user"))).one()
            self.assertFalse(role.rolsuper or role.rolbypassrls)
            db.add_all([Tenant(id=self.tenant_id, name="Push test", slug=str(uuid.uuid4())), Tenant(id=self.other_tenant, name="Other push test", slug=str(uuid.uuid4()))])
            await db.flush()
            db.add_all([User(id=self.user_id, tenant_id=self.tenant_id, full_name="Push owner", email=f"{uuid.uuid4()}@example.test", hashed_password="not-used", role="lawyer"), User(id=self.other_user_id, tenant_id=self.tenant_id, full_name="Other lawyer", email=f"{uuid.uuid4()}@example.test", hashed_password="not-used", role="lawyer")])
            await db.flush()
            # Expired navigation sessions still allow generic notifications until explicitly revoked.
            db.add(AuthSession(id=self.session_id, tenant_id=self.tenant_id, user_id=self.user_id, expires_at=now - timedelta(minutes=1)))
            await _set_tenant_context(db, self.tenant_id)
            await db.flush()
            client = WorkspaceClient(tenant_id=self.tenant_id, name="Fictitious client")
            db.add(client)
            await db.flush()
            case = WorkspaceCase(tenant_id=self.tenant_id, client_id=client.id, title="Fictitious restricted case", responsible_user_id=self.user_id, restricted=True)
            db.add(case)
            await db.flush()
            task = WorkspaceTask(tenant_id=self.tenant_id, case_id=case.id, assigned_user_id=self.user_id, title="Fictitious task")
            db.add(task)
            await db.flush()
            self.case_id, self.task_id = case.id, task.id
            await db.commit()
        self.user = SimpleNamespace(id=self.user_id, tenant_id=self.tenant_id)
        self.request = SimpleNamespace(state=SimpleNamespace(auth_session=SimpleNamespace(id=self.session_id)))
        self.body = PushSubscriptionCreate(**(subscription_data() | {"endpoint": f"https://fcm.googleapis.com/fcm/send/{uuid.uuid4()}"}))
        async with self.Session() as db:
            await _set_tenant_context(db, self.tenant_id)
            item = await api.subscribe(self.body, self.request, self.user, db)
            self.subscription_id = item.id

    async def asyncTearDown(self):
        for item in reversed(self.patches):
            item.stop()
        await self.engine.dispose()

    async def enqueue(self, key="event", kind="task_assigned"):
        async with self.Session() as db:
            await _set_tenant_context(db, self.tenant_id)
            count = await push_service.enqueue_user_push(db, tenant_id=self.tenant_id, user_id=self.user_id, event_key=key, kind=kind, case_id=self.case_id, task_id=self.task_id if kind == "task_assigned" else None)
            await db.commit()
            await _set_tenant_context(db, self.tenant_id)
            delivery = await db.scalar(select(PushDelivery).where(PushDelivery.tenant_id == self.tenant_id).order_by(PushDelivery.created_at.desc()))
            return count, delivery.id

    async def test_enforced_rls_cross_user_bind_and_durable_dedupe(self):
        count, delivery_id = await self.enqueue()
        self.assertEqual(count, 1)
        self.assertEqual((await self.enqueue())[0], 0)
        async with self.Session() as db:
            flags = (await db.execute(text("SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname IN ('push_subscriptions','push_deliveries')"))).all()
            self.assertEqual(len(flags), 2)
            self.assertTrue(all(row.relrowsecurity and row.relforcerowsecurity for row in flags))
            for tenant in (None, self.other_tenant):
                if tenant:
                    await _set_tenant_context(db, tenant)
                self.assertIsNone(await db.scalar(select(PushSubscription).where(PushSubscription.id == self.subscription_id)))
                self.assertIsNone(await db.scalar(select(PushDelivery).where(PushDelivery.id == delivery_id)))
            candidates = (await db.execute(text("SELECT * FROM push_recovery_candidates(100,120)"))).all()
            self.assertTrue(any(row.delivery_id == delivery_id for row in candidates))
            await _set_tenant_context(db, self.tenant_id)
            stranger = SimpleNamespace(id=self.other_user_id, tenant_id=self.tenant_id)
            with self.assertRaises(HTTPException) as denied:
                await api.owned_subscription(db, stranger, self.subscription_id)
            self.assertEqual(denied.exception.status_code, 404)
            with self.assertRaises(HTTPException) as conflict:
                await api.subscribe(self.body, self.request, stranger, db)
            self.assertEqual(conflict.exception.status_code, 409)
        async with self.Session() as db:
            await _set_tenant_context(db, self.tenant_id)
            with self.assertRaises(DBAPIError):
                await db.execute(update(PushDelivery).where(PushDelivery.id == delivery_id).values(user_id=self.other_user_id))
            await db.rollback()

    async def test_worker_acceptance_claim_idempotency_and_expired_session(self):
        _, delivery_id = await self.enqueue()
        with patch.object(push_tasks, "send_push", return_value=PushResult("accepted")) as send:
            self.assertEqual(await push_tasks._process_delivery(delivery_id, self.tenant_id), "accepted")
            self.assertEqual(await push_tasks._process_delivery(delivery_id, self.tenant_id), "ignored")
            self.assertEqual(send.call_count, 1)
        async with self.Session() as db:
            await _set_tenant_context(db, self.tenant_id)
            item = await db.get(PushDelivery, delivery_id)
            self.assertIsNotNone(item.accepted_at)
            self.assertEqual(item.status, "accepted")

    async def test_authority_changes_prevent_send(self):
        _, delivery_id = await self.enqueue()
        async with self.Session() as db:
            await _set_tenant_context(db, self.tenant_id)
            await db.execute(update(WorkspaceTask).where(WorkspaceTask.id == self.task_id).values(assigned_user_id=self.other_user_id))
            await db.commit()
        with patch.object(push_tasks, "send_push") as send:
            self.assertEqual(await push_tasks._process_delivery(delivery_id, self.tenant_id), "cancelled")
            send.assert_not_called()
        _, portal_id = await self.enqueue("portal", kind="portal_message")
        async with self.Session() as db:
            await _set_tenant_context(db, self.tenant_id)
            await db.execute(update(WorkspaceCase).where(WorkspaceCase.id == self.case_id).values(responsible_user_id=self.other_user_id))
            await db.commit()
        with patch.object(push_tasks, "send_push") as send:
            self.assertEqual(await push_tasks._process_delivery(portal_id, self.tenant_id), "cancelled")
            send.assert_not_called()

    async def test_session_revocation_and_crash_recovery_are_conservative(self):
        _, delivery_id = await self.enqueue()
        async with self.Session() as db:
            await _set_tenant_context(db, self.tenant_id)
            await db.execute(update(AuthSession).where(AuthSession.id == self.session_id).values(revoked_at=datetime.now(timezone.utc)))
            await db.commit()
        with patch.object(push_tasks, "send_push") as send:
            self.assertEqual(await push_tasks._process_delivery(delivery_id, self.tenant_id), "cancelled")
            send.assert_not_called()
        async with self.Session() as db:
            await _set_tenant_context(db, self.tenant_id)
            await db.execute(update(PushDelivery).where(PushDelivery.id == delivery_id).values(status="processing", processing_started_at=datetime.now(timezone.utc) - timedelta(minutes=10)))
            await db.commit()
        with patch.object(push_tasks, "send_push") as send:
            self.assertEqual(await push_tasks._process_delivery(delivery_id, self.tenant_id), "unknown")
            send.assert_not_called()

    async def test_provider_expiration_revokes_other_queued_work_and_rate_limit(self):
        _, delivery_id = await self.enqueue("first")
        _, second_id = await self.enqueue("second")
        with patch.object(push_tasks, "send_push", return_value=PushResult("expired", "subscription_expired")):
            self.assertEqual(await push_tasks._process_delivery(delivery_id, self.tenant_id), "expired")
        async with self.Session() as db:
            await _set_tenant_context(db, self.tenant_id)
            self.assertIsNotNone((await db.get(PushSubscription, self.subscription_id)).revoked_at)
            self.assertEqual((await db.get(PushDelivery, second_id)).status, "cancelled")
            await api.subscribe(self.body, self.request, self.user, db)
            for _ in range(5):
                await _set_tenant_context(db, self.tenant_id)
                self.assertEqual(await api.test_subscription(self.subscription_id, self.user, db), {"status": "queued"})
            await _set_tenant_context(db, self.tenant_id)
            with self.assertRaises(HTTPException) as rate:
                await api.test_subscription(self.subscription_id, self.user, db)
            self.assertEqual(rate.exception.status_code, 429)

    async def test_concurrent_workers_send_once_and_transient_retries_are_bounded(self):
        _, delivery_id = await self.enqueue("concurrent")
        with patch.object(push_tasks, "send_push", return_value=PushResult("accepted")) as send:
            results = await asyncio.gather(*(push_tasks._process_delivery(delivery_id, self.tenant_id) for _ in range(3)))
            self.assertEqual(results.count("accepted"), 1)
            self.assertEqual(send.call_count, 1)
        _, retry_id = await self.enqueue("retry")
        with patch.object(push_tasks, "send_push", return_value=PushResult("queued", "provider_rate_limited", retryable=True)) as send:
            for expected in ("queued", "queued", "failed"):
                self.assertEqual(await push_tasks._process_delivery(retry_id, self.tenant_id), expected)
                async with self.Session() as db:
                    await _set_tenant_context(db, self.tenant_id)
                    await db.execute(update(PushDelivery).where(PushDelivery.id == retry_id).values(next_attempt_at=None))
                    await db.commit()
            self.assertEqual(await push_tasks._process_delivery(retry_id, self.tenant_id), "ignored")
            self.assertEqual(send.call_count, 3)

    async def test_expiration_and_corrupt_ciphertext_never_send(self):
        _, expired_id = await self.enqueue("expired")
        async with self.Session() as db:
            await _set_tenant_context(db, self.tenant_id)
            await db.execute(update(PushDelivery).where(PushDelivery.id == expired_id).values(expires_at=datetime.now(timezone.utc) - timedelta(minutes=1)))
            await db.commit()
        with patch.object(push_tasks, "send_push") as send:
            self.assertEqual(await push_tasks._process_delivery(expired_id, self.tenant_id), "expired")
            send.assert_not_called()
        _, corrupt_id = await self.enqueue("corrupt")
        async with self.Session() as db:
            await _set_tenant_context(db, self.tenant_id)
            await db.execute(update(PushSubscription).where(PushSubscription.id == self.subscription_id).values(credentials_encrypted="invalid-ciphertext"))
            await db.commit()
        with patch.object(push_tasks, "send_push") as send:
            self.assertEqual(await push_tasks._process_delivery(corrupt_id, self.tenant_id), "failed")
            send.assert_not_called()

    async def test_registration_limits_bound_active_devices_and_churn(self):
        def extra_subscription():
            return PushSubscription(tenant_id=self.tenant_id, user_id=self.user_id, auth_session_id=self.session_id,
                endpoint_hash=push_service.digest(str(uuid.uuid4())), credentials_encrypted="unused-in-quota-test",
                vapid_key_hash=push_service.digest(self.config.WEB_PUSH_VAPID_PUBLIC_KEY), label="Test device",
                expires_at=datetime.now(timezone.utc) + timedelta(days=90))

        body = self.body.model_copy(update={"endpoint": f"https://fcm.googleapis.com/fcm/send/{uuid.uuid4()}"})
        async with self.Session() as db:
            await _set_tenant_context(db, self.tenant_id)
            db.add_all([extra_subscription() for _ in range(9)])
            await db.flush()
            with self.assertRaises(HTTPException) as active_limit:
                await api.subscribe(body, self.request, self.user, db)
            self.assertEqual(active_limit.exception.status_code, 409)
            await db.execute(update(PushSubscription).where(PushSubscription.tenant_id == self.tenant_id).values(revoked_at=datetime.now(timezone.utc)))
            retired = [extra_subscription() for _ in range(20)]
            for item in retired:
                item.revoked_at = datetime.now(timezone.utc)
            db.add_all(retired)
            await db.flush()
            with self.assertRaises(HTTPException) as churn_limit:
                await api.subscribe(body, self.request, self.user, db)
            self.assertEqual(churn_limit.exception.status_code, 429)


if __name__ == "__main__":
    unittest.main()
