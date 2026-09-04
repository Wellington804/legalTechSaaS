"""Enforced-RLS routine flows; real database, no Redis or push network."""
import asyncio
import os
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.v1.endpoints import routines, workspace
from app.core.dependencies import _set_tenant_context
from app.models.account import AuthSession
from app.models.engagement import PortalGrant  # register the existing document-version FK target
from app.models.push import PushDelivery, PushSubscription
from app.models.routine import RoutineAction, RoutineReminder
from app.models.tenant import Tenant
from app.models.user import User
from app.models.workspace import WorkspaceCase, WorkspaceClient, WorkspaceDocument, WorkspaceDocumentVersion, WorkspaceTask
from app.schemas.routine import ChecklistCreate, OutcomeCreate, ReminderSet
from app.schemas.workspace import TaskUpdate
from app.services import push_service, push_tasks, routine_tasks
from app.services.push_provider import PushResult
from app.services.routine_service import dispatch_reminder
from tests.test_push import subscription_data


@unittest.skipUnless(os.environ.get("AUDIT_TEST_DATABASE_URL"), "Requires disposable PostgreSQL runtime-role database")
class RoutinePostgresTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine(os.environ["AUDIT_TEST_DATABASE_URL"], poolclass=NullPool)
        self.Session = async_sessionmaker(self.engine, expire_on_commit=False, autoflush=False)
        self.config = SimpleNamespace(WEB_PUSH_ENABLED=True, WEB_PUSH_VAPID_PUBLIC_KEY="test-public-key")
        self.patches = [patch.object(module, "settings", self.config) for module in (push_service, push_tasks)]
        self.patches += [patch.object(push_tasks, "AsyncSessionLocal", self.Session), patch.object(routine_tasks, "AsyncSessionLocal", self.Session)]
        for item in self.patches:
            item.start()
        self.tenant_id, self.other_tenant = str(uuid.uuid4()), str(uuid.uuid4())
        self.now = datetime.now(timezone.utc)
        self.request = SimpleNamespace(client=None, headers={})
        async with self.Session() as db:
            role = (await db.execute(text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user"))).one()
            self.assertFalse(role.rolsuper or role.rolbypassrls)
            db.add_all([Tenant(id=self.tenant_id, name="Fictitious routine", slug=str(uuid.uuid4()),
                              subscription_status="active", subscription_ends_at=self.now + timedelta(days=14)),
                        Tenant(id=self.other_tenant, name="Other routine", slug=str(uuid.uuid4()))])
            await db.flush()
            self.user = User(id=str(uuid.uuid4()), tenant_id=self.tenant_id, full_name="Fictitious lawyer", email=f"{uuid.uuid4()}@example.test",
                             hashed_password="not-used", role="lawyer", is_active=True)
            self.other = User(id=str(uuid.uuid4()), tenant_id=self.tenant_id, full_name="Other lawyer", email=f"{uuid.uuid4()}@example.test",
                              hashed_password="not-used", role="lawyer", is_active=True)
            db.add_all([self.user, self.other])
            await db.flush()
            session = AuthSession(tenant_id=self.tenant_id, user_id=self.user.id, expires_at=self.now - timedelta(minutes=1))
            db.add(session)
            await _set_tenant_context(db, self.tenant_id)
            await db.flush()
            client = WorkspaceClient(tenant_id=self.tenant_id, name="Fictitious client")
            db.add(client)
            await db.flush()
            case = WorkspaceCase(tenant_id=self.tenant_id, client_id=client.id, title="Restricted fictitious case",
                                 responsible_user_id=self.user.id, restricted=True)
            db.add(case)
            await db.flush()
            task = WorkspaceTask(tenant_id=self.tenant_id, case_id=case.id, assigned_user_id=self.user.id,
                title="Fictitious diligence", due_at=self.now + timedelta(days=2), manually_reviewed=True,
                location="Fictional forum", contact="Fictional clerk", notes="Bring fictional documents")
            db.add(task)
            await db.flush()
            self.task_id, self.case_id = task.id, case.id
            credentials = subscription_data()
            endpoint = f"https://fcm.googleapis.com/fcm/send/{uuid.uuid4()}"
            sub = PushSubscription(tenant_id=self.tenant_id, user_id=self.user.id, auth_session_id=session.id,
                endpoint_hash=push_service.digest(endpoint), credentials_encrypted=push_service.encrypt_subscription(endpoint, credentials["keys"]),
                vapid_key_hash=push_service.digest(self.config.WEB_PUSH_VAPID_PUBLIC_KEY), label="Test", expires_at=self.now + timedelta(days=90))
            db.add(sub)
            await db.commit()
            self.subscription_id = sub.id

    async def asyncTearDown(self):
        for item in reversed(self.patches):
            item.stop()
        await self.engine.dispose()

    async def schedule(self, offset=60):
        async with self.Session() as db:
            await _set_tenant_context(db, self.tenant_id)
            result = await routines.set_reminder(self.task_id, ReminderSet(remind_at=self.now + timedelta(minutes=offset), expected_revision=1),
                self.request, self.user, db, self.user)
            return result.id

    async def make_due(self, reminder_id):
        async with self.Session() as db:
            await _set_tenant_context(db, self.tenant_id)
            await db.execute(update(RoutineReminder).where(RoutineReminder.id == reminder_id).values(remind_at=self.now - timedelta(minutes=1)))
            await db.commit()
        async with self.Session() as db:
            await _set_tenant_context(db, self.tenant_id)
            status = await dispatch_reminder(db, reminder_id, self.tenant_id)
            await db.commit()
            return status

    async def test_checklist_concurrent_idempotency_and_versioned_outcome(self):
        payload = ChecklistCreate(key="hearing", request_id=uuid.uuid4())
        async def apply():
            async with self.Session() as db:
                await _set_tenant_context(db, self.tenant_id)
                return await routines.apply_checklist(self.case_id, payload, self.request, self.user, db, self.user)
        first, second = await asyncio.gather(apply(), apply())
        self.assertEqual(first["task_ids"], second["task_ids"])
        self.assertEqual({first["created"], second["created"]}, {True, False})
        async with self.Session() as db:
            await _set_tenant_context(db, self.tenant_id)
            tasks = (await db.scalars(select(WorkspaceTask).where(WorkspaceTask.id.in_(first["task_ids"])))).all()
            self.assertEqual(len(tasks), 4)
            self.assertTrue(all(task.due_at is None and not task.manually_reviewed for task in tasks))
            with self.assertRaises(HTTPException) as conflict:
                await routines.apply_checklist(self.case_id, ChecklistCreate(key="documents", request_id=payload.request_id), self.request, self.user, db, self.user)
            self.assertEqual(conflict.exception.status_code, 409)
        outcome = OutcomeCreate(request_id=uuid.uuid4(), title="Resultado da diligência", content_text="Documento fictício recebido; conferir próxima ação.")
        async with self.Session() as db:
            await _set_tenant_context(db, self.tenant_id)
            first = await routines.create_outcome(self.case_id, outcome, self.request, self.user, db, self.user)
            await _set_tenant_context(db, self.tenant_id)
            second = await routines.create_outcome(self.case_id, outcome, self.request, self.user, db, self.user)
            self.assertEqual(first.id, second.id)
            self.assertEqual(first.kind, "note")
            self.assertEqual(await db.scalar(select(func.count(WorkspaceDocumentVersion.id)).where(WorkspaceDocumentVersion.document_id == first.id)), 1)
            with self.assertRaises(HTTPException) as denied:
                await routines.list_outcomes(self.case_id, self.other, db)
            self.assertEqual(denied.exception.status_code, 404)

    async def test_in_app_due_without_push_and_acknowledge(self):
        reminder_id = await self.schedule()
        with patch.object(push_service, "settings", SimpleNamespace(WEB_PUSH_ENABLED=False)):
            self.assertEqual(await self.make_due(reminder_id), "due")
        async with self.Session() as db:
            await _set_tenant_context(db, self.tenant_id)
            response = await routines.attention(self.user, db)
            self.assertEqual(response["reminders"][0].id, reminder_id)
            self.assertEqual(response["reminders"][0].push_status, "unavailable")
            await routines.acknowledge_reminder(reminder_id, self.request, self.user, db)
            await _set_tenant_context(db, self.tenant_id)
            self.assertEqual((await routines.attention(self.user, db))["reminders"], [])

    async def test_scheduler_discovery_next_action_and_date_boundaries(self):
        async with self.Session() as db:
            await _set_tenant_context(db, self.tenant_id)
            case = await db.get(WorkspaceCase, self.case_id)
            visible = WorkspaceCase(tenant_id=self.tenant_id, client_id=case.client_id, title="Needs next action",
                responsible_user_id=self.user.id, restricted=True)
            hidden = WorkspaceCase(tenant_id=self.tenant_id, client_id=case.client_id, title="Hidden next action",
                responsible_user_id=self.other.id, restricted=True)
            db.add_all([visible, hidden])
            await db.flush()
            results = await routines.attention(self.user, db)
            self.assertIn(visible.id, [item["id"] for item in results["cases_without_next_action"]])
            self.assertNotIn(hidden.id, [item["id"] for item in results["cases_without_next_action"]])
            self.assertNotIn(self.case_id, [item["id"] for item in results["cases_without_next_action"]])
            await db.commit()
        for remind_at in (self.now - timedelta(minutes=1), self.now + timedelta(days=3)):
            async with self.Session() as db:
                await _set_tenant_context(db, self.tenant_id)
                with self.assertRaises(HTTPException) as invalid:
                    await routines.set_reminder(self.task_id, ReminderSet(expected_revision=1, remind_at=remind_at), self.request, self.user, db, self.user)
                self.assertEqual(invalid.exception.status_code, 422)
        reminder_id = await self.schedule()
        async with self.Session() as db:
            await _set_tenant_context(db, self.tenant_id)
            await db.execute(update(RoutineReminder).where(RoutineReminder.id == reminder_id).values(remind_at=self.now - timedelta(minutes=1)))
            await db.commit()
        with patch.object(routine_tasks, "_heartbeat", new_callable=AsyncMock), patch.object(push_tasks, "send_push") as send:
            result = await routine_tasks._dispatch_reminders()
            self.assertEqual(result["deferred"], 0)
            self.assertGreaterEqual(result["due"], 1)
            send.assert_not_called()
        async with self.Session() as db:
            await _set_tenant_context(db, self.tenant_id)
            self.assertEqual((await db.get(RoutineReminder, reminder_id)).status, "due")

    async def test_replacement_never_resurrects_queued_push(self):
        old_id = await self.schedule()
        self.assertEqual(await self.make_due(old_id), "due")
        new_id = await self.schedule(offset=90)
        self.assertNotEqual(old_id, new_id)
        async with self.Session() as db:
            await _set_tenant_context(db, self.tenant_id)
            old = await db.get(RoutineReminder, old_id)
            self.assertEqual(old.status, "cancelled")
            delivery = await db.scalar(select(PushDelivery).where(PushDelivery.reminder_id == old_id))
            self.assertEqual(delivery.status, "cancelled")
            # Even a stale/requeued old job cannot attach itself to the new schedule.
            delivery.status = "queued"
            await db.commit()
        with patch.object(push_tasks, "send_push") as send:
            self.assertEqual(await push_tasks._process_delivery(delivery.id, self.tenant_id), "cancelled")
            send.assert_not_called()

    async def test_task_edit_cancels_reminder_and_requires_new_date_review(self):
        reminder_id = await self.schedule()
        async with self.Session() as db:
            await _set_tenant_context(db, self.tenant_id)
            response = await workspace.update_task(self.task_id, TaskUpdate(expected_revision=1,
                due_at=self.now + timedelta(days=3)), self.request, current_user=self.user, db=db, _write=self.user)
            self.assertFalse(response.manually_reviewed)
            self.assertEqual(response.location, "Fictional forum")
            await _set_tenant_context(db, self.tenant_id)
            self.assertEqual((await db.get(RoutineReminder, reminder_id)).status, "cancelled")
            with self.assertRaises(HTTPException) as invalid:
                await routines.set_reminder(self.task_id, ReminderSet(expected_revision=2, remind_at=self.now + timedelta(hours=1)), self.request, self.user, db, self.user)
            self.assertEqual(invalid.exception.status_code, 422)

    async def test_scheduler_and_sender_revalidate_acl_and_subscription(self):
        reminder_id = await self.schedule()
        self.assertEqual(await self.make_due(reminder_id), "due")
        async with self.Session() as db:
            await _set_tenant_context(db, self.tenant_id)
            delivery = await db.scalar(select(PushDelivery).where(PushDelivery.reminder_id == reminder_id))
            await db.execute(update(WorkspaceCase).where(WorkspaceCase.id == self.case_id).values(responsible_user_id=self.other.id))
            await db.commit()
        with patch.object(push_tasks, "send_push") as send:
            self.assertEqual(await push_tasks._process_delivery(delivery.id, self.tenant_id), "cancelled")
            send.assert_not_called()
        async with self.Session() as db:
            await _set_tenant_context(db, self.tenant_id)
            self.assertEqual((await routines.attention(self.user, db))["reminders"], [])
            await db.execute(update(WorkspaceCase).where(WorkspaceCase.id == self.case_id).values(responsible_user_id=self.user.id))
            await db.commit()
        next_id = await self.schedule(offset=90)
        async with self.Session() as db:
            await db.execute(update(Tenant).where(Tenant.id == self.tenant_id).values(subscription_ends_at=self.now - timedelta(seconds=1)))
            await db.commit()
        self.assertEqual(await self.make_due(next_id), "cancelled")

    async def test_rls_private_owner_and_current_task_revision(self):
        reminder_id = await self.schedule()
        self.assertEqual(await self.schedule(), reminder_id)
        async with self.Session() as db:
            for tenant in (None, self.other_tenant):
                if tenant:
                    await _set_tenant_context(db, tenant)
                self.assertIsNone(await db.scalar(select(RoutineReminder).where(RoutineReminder.id == reminder_id)))
                self.assertEqual((await db.scalars(select(RoutineAction))).all(), [])
            await _set_tenant_context(db, self.tenant_id)
            with self.assertRaises(HTTPException) as denied:
                await routines.acknowledge_reminder(reminder_id, self.request, self.other, db)
            self.assertEqual(denied.exception.status_code, 404)
            with self.assertRaises(HTTPException) as stale:
                await routines.set_reminder(self.task_id, ReminderSet(expected_revision=99, remind_at=self.now + timedelta(hours=1)), self.request, self.user, db, self.user)
            self.assertEqual(stale.exception.status_code, 409)
        async with self.Session() as db:
            await _set_tenant_context(db, self.tenant_id)
            with self.assertRaises(DBAPIError):
                await db.execute(update(RoutineReminder).where(RoutineReminder.id == reminder_id).values(tenant_id=self.other_tenant))
            await db.rollback()


if __name__ == "__main__":
    unittest.main()
