import base64
import hashlib
import json
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from app.core.security import decrypt_mfa_secret, encrypt_mfa_secret
from app.models.external_integrations import CalendarConnection, CalendarOAuthState, CalendarSyncConflict, CalendarTaskLink
from app.models.workspace import WorkspaceTask
from app.services.calendar_providers import CalendarProviderError, OAuthTokens, ProviderAccount, RemoteEvent
from app.services.calendar_sync import (
    _audit_calendar_change,
    _link_audit_state,
    _pkce,
    _record_conflict,
    _serialize_remote,
    _single_recoverable_remote,
    _task_audit_state,
    complete_oauth,
    conflict_payload,
    digest,
    disconnect_calendar,
    record_webhook,
    resolve_conflict,
    select_tasks,
    unselect_task,
)


class FakeDB:
    def __init__(self, scalars, scalar_rows=None):
        self.bind = None
        self._scalars = list(scalars)
        self._scalar_rows = list(scalar_rows or [])
        self.added = []
        self.commits = 0

    async def scalar(self, _statement):
        return self._scalars.pop(0)

    async def scalars(self, _statement):
        rows = self._scalar_rows.pop(0)
        return SimpleNamespace(all=lambda: rows)

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        self.commits += 1

    async def flush(self):
        return None

    async def delete(self, value):
        self.added.append(("deleted", value))


class FakeCalendarClient:
    def __init__(self, provider, token):
        self.provider = provider
        self.token = token

    async def account(self):
        return ProviderAccount("provider-user-1", "advogado@example.com")


class CalendarOAuthTests(unittest.IsolatedAsyncioTestCase):
    def test_pkce_is_s256_and_does_not_reveal_verifier(self):
        verifier, challenge = _pkce()
        expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        self.assertEqual(challenge, expected)
        self.assertNotIn(verifier, challenge)
        self.assertGreaterEqual(len(verifier), 43)

    async def test_callback_consumes_state_once_and_encrypts_refresh_token(self):
        now = datetime.now(timezone.utc)
        state = CalendarOAuthState(
            tenant_id="tenant-a",
            user_id="user-a",
            provider="google",
            state_digest=hashlib.sha256(b"opaque-state").hexdigest(),
            pkce_verifier_encrypted=encrypt_mfa_secret("pkce-verifier"),
            redirect_path="/dashboard/tasks",
            expires_at=now + timedelta(minutes=5),
        )
        user = SimpleNamespace(id="user-a", tenant_id="tenant-a")
        db = FakeDB([state, None])
        tokens = OAuthTokens("access-secret", "refresh-secret", now + timedelta(hours=1), ("openid", "email"))
        with patch("app.services.calendar_sync.exchange_code", return_value=tokens), patch(
            "app.services.calendar_sync.CalendarClient", FakeCalendarClient
        ):
            connection, path = await complete_oauth(
                db, user, "google", state_value="opaque-state", code="one-use-code"
            )
        self.assertEqual(path, "/dashboard/tasks")
        self.assertIsNotNone(state.consumed_at)
        self.assertEqual(decrypt_mfa_secret(connection.refresh_token_encrypted), "refresh-secret")
        self.assertNotIn("refresh-secret", connection.refresh_token_encrypted)
        with self.assertRaises(HTTPException) as replay:
            await complete_oauth(
                FakeDB([state]), user, "google", state_value="opaque-state", code="replayed-code"
            )
        self.assertEqual(replay.exception.status_code, 401)

    async def test_conflict_payload_is_encrypted_and_never_overwrites_task(self):
        connection = CalendarConnection(id="connection-a", tenant_id="tenant-a", user_id="user-a", provider="google")
        link = CalendarTaskLink(id="link-a", tenant_id="tenant-a", connection_id="connection-a", task_id="task-a")
        task = WorkspaceTask(
            id="task-a", tenant_id="tenant-a", title="Prazo local", kind="deadline",
            due_at=datetime(2026, 9, 10, 12, tzinfo=timezone.utc), status="pending", revision=7,
        )
        from app.services.calendar_providers import RemoteEvent

        remote = RemoteEvent(
            "remote-a", '"etag-2"', False, "Prazo remoto",
            datetime(2026, 9, 11, 12, tzinfo=timezone.utc), "Fórum", "Alterado fora",
        )
        db = FakeDB([None])
        conflict = await _record_conflict(db, connection, link, task, remote, "both_changed")
        self.assertEqual(task.title, "Prazo local")
        self.assertEqual(link.status, "conflict")
        self.assertNotIn("Prazo remoto", conflict.remote_payload_encrypted)
        self.assertIn("Prazo remoto", decrypt_mfa_secret(conflict.remote_payload_encrypted))
        payload = conflict_payload(conflict, task)
        self.assertEqual(payload["local"]["title"], "Prazo local")
        self.assertEqual(payload["remote"]["title"], "Prazo remoto")
        self.assertEqual(payload["remote_hash"], remote.canonical_hash())

    async def test_repeated_remote_snapshot_reuses_conflict_without_losing_pending_review(self):
        connection = CalendarConnection(id="connection-a", tenant_id="tenant-a", user_id="user-a", provider="google")
        link = CalendarTaskLink(id="link-a", tenant_id="tenant-a", connection_id="connection-a", task_id="task-a")
        task = WorkspaceTask(
            id="task-a", tenant_id="tenant-a", title="Prazo local", kind="deadline",
            due_at=datetime(2026, 9, 10, 12, tzinfo=timezone.utc), status="pending", revision=9,
        )
        remote = RemoteEvent(
            "remote-a", '"etag-new"', False, "Prazo remoto",
            datetime(2026, 9, 11, 12, tzinfo=timezone.utc), "Fórum", "Alterado fora",
        )
        existing = CalendarSyncConflict(
            id="conflict-old", tenant_id="tenant-a", connection_id="connection-a", task_id="task-a",
            reason="both_changed", remote_hash=remote.canonical_hash(), remote_etag='"etag-old"',
            remote_payload_encrypted=encrypt_mfa_secret(_serialize_remote(remote)), local_revision=7,
            status="kept_local", resolved_by_user_id="user-a", resolved_at=datetime.now(timezone.utc),
        )
        result = await _record_conflict(FakeDB([existing]), connection, link, task, remote, "both_changed")
        self.assertIs(result, existing)
        self.assertEqual(existing.status, "pending")
        self.assertEqual(existing.local_revision, 9)
        self.assertEqual(existing.remote_etag, '"etag-new"')
        self.assertIsNone(existing.resolved_by_user_id)
        self.assertEqual(link.status, "conflict")

    async def test_conflict_resolution_revalidates_remote_hash_and_fails_stale(self):
        task = WorkspaceTask(
            id="task-a", tenant_id="tenant-a", title="Prazo local", kind="deadline",
            due_at=datetime(2026, 9, 10, 12, tzinfo=timezone.utc), status="pending", revision=7,
        )
        stored = RemoteEvent(
            "remote-a", '"etag-1"', False, "Prazo remoto",
            datetime(2026, 9, 11, 12, tzinfo=timezone.utc), "Fórum", "Alterado fora",
        )
        live = RemoteEvent(
            "remote-a", '"etag-2"', False, "Prazo remoto novamente alterado",
            datetime(2026, 9, 12, 12, tzinfo=timezone.utc), "Fórum", "Mudou depois",
        )
        conflict = CalendarSyncConflict(
            id="conflict-a", tenant_id="tenant-a", connection_id="connection-a", task_id="task-a",
            reason="both_changed", remote_hash=stored.canonical_hash(), remote_etag=stored.etag,
            remote_payload_encrypted=encrypt_mfa_secret(_serialize_remote(stored)), local_revision=7, status="pending",
        )
        connection = CalendarConnection(
            id="connection-a", tenant_id="tenant-a", user_id="user-a", provider="google", status="active",
            selected_calendar_id_encrypted=encrypt_mfa_secret("calendar-a"),
        )
        link = CalendarTaskLink(
            id="link-a", tenant_id="tenant-a", connection_id="connection-a", task_id="task-a", status="conflict",
        )
        db = FakeDB([connection, connection, conflict, task, link, None])
        user = SimpleNamespace(id="user-a", tenant_id="tenant-a")

        class Client:
            def __init__(self, *_args):
                pass

            async def get_event(self, _calendar_id, _event_id):
                return live

        with patch("app.services.calendar_sync.get_task", AsyncMock(return_value=task)), patch(
            "app.services.calendar_sync.require_task_write"
        ), patch("app.services.calendar_sync._access_token", AsyncMock(return_value="access")), patch(
            "app.services.calendar_sync._set_tenant_context", AsyncMock()
        ), patch("app.services.calendar_sync.CalendarClient", Client):
            with self.assertRaises(HTTPException) as stale:
                await resolve_conflict(
                    db,
                    user,
                    conflict,
                    "accept_remote",
                    expected_local_revision=7,
                    expected_remote_hash=stored.canonical_hash(),
                )
        self.assertEqual(stale.exception.status_code, 409)
        self.assertEqual(task.title, "Prazo local")
        self.assertEqual(conflict.status, "pending")
        self.assertEqual(conflict.remote_hash, live.canonical_hash())
        self.assertEqual(conflict.remote_etag, live.etag)
        self.assertIn("novamente alterado", decrypt_mfa_secret(conflict.remote_payload_encrypted))
        self.assertEqual(db.commits, 1)

    async def test_conflict_resolution_applies_exact_revalidated_snapshot_without_committing(self):
        task = WorkspaceTask(
            id="task-a", tenant_id="tenant-a", title="Prazo local", kind="deadline",
            due_at=datetime(2026, 9, 10, 12, tzinfo=timezone.utc), status="pending", revision=7,
        )
        remote = RemoteEvent(
            "remote-a", '"etag-2"', False, "Prazo remoto",
            datetime(2026, 9, 11, 12, tzinfo=timezone.utc), "Fórum", "Alterado fora",
        )
        conflict = CalendarSyncConflict(
            id="conflict-a", tenant_id="tenant-a", connection_id="connection-a", task_id="task-a",
            reason="both_changed", remote_hash=remote.canonical_hash(), remote_etag=remote.etag,
            remote_payload_encrypted=encrypt_mfa_secret(_serialize_remote(remote)), local_revision=7, status="pending",
        )
        connection = CalendarConnection(
            id="connection-a", tenant_id="tenant-a", user_id="user-a", provider="google", status="active",
            selected_calendar_id_encrypted=encrypt_mfa_secret("calendar-a"),
        )
        link = CalendarTaskLink(
            id="link-a", tenant_id="tenant-a", connection_id="connection-a", task_id="task-a", status="conflict",
        )
        db = FakeDB([connection, connection, conflict, task, link])
        user = SimpleNamespace(id="user-a", tenant_id="tenant-a")

        class Client:
            def __init__(self, *_args):
                pass

            async def get_event(self, _calendar_id, _event_id):
                return remote

        with patch("app.services.calendar_sync.get_task", AsyncMock(return_value=task)), patch(
            "app.services.calendar_sync.require_task_write"
        ), patch("app.services.calendar_sync._access_token", AsyncMock(return_value="access")), patch(
            "app.services.calendar_sync._set_tenant_context", AsyncMock()
        ), patch("app.services.calendar_sync.CalendarClient", Client):
            result = await resolve_conflict(
                db,
                user,
                conflict,
                "accept_remote",
                expected_local_revision=7,
                expected_remote_hash=remote.canonical_hash(),
            )
        self.assertEqual(result.status, "accepted_remote")
        self.assertEqual(task.title, "Prazo remoto")
        self.assertEqual(task.revision, 8)
        self.assertEqual(link.status, "active")
        self.assertEqual(db.commits, 0)

    async def test_unselect_remains_retryable_until_provider_confirms_delete(self):
        user = SimpleNamespace(id="user-a", tenant_id="tenant-a")
        connection = CalendarConnection(
            id="connection-a", tenant_id="tenant-a", user_id="user-a", provider="google", status="active",
            selected_calendar_id_encrypted=encrypt_mfa_secret("calendar-a"),
        )
        link = CalendarTaskLink(
            id="link-a", tenant_id="tenant-a", connection_id="connection-a", task_id="task-a", status="active",
            provider_event_id_encrypted=encrypt_mfa_secret("event-a"), provider_etag='"etag-1"',
        )
        remote = RemoteEvent("event-a", '"etag-2"', False, "Prazo", datetime.now(timezone.utc), None, None)
        db = FakeDB([link])

        class Client:
            def __init__(self, *_args):
                pass

            async def get_event(self, *_args):
                return remote

            async def delete_event(self, *_args):
                raise CalendarProviderError("stale", conflict=True)

        with patch("app.services.calendar_sync._access_token", AsyncMock(return_value="access")), patch(
            "app.services.calendar_sync._set_tenant_context", AsyncMock()
        ), patch("app.services.calendar_sync.CalendarClient", Client):
            await unselect_task(db, user, connection, "task-a")
        self.assertEqual(link.status, "delete_pending")
        self.assertEqual(db.commits, 1)

    async def test_tombstoned_link_can_be_reselected_and_is_audited(self):
        user = SimpleNamespace(id="user-a", tenant_id="tenant-a")
        connection = CalendarConnection(
            id="connection-a",
            tenant_id="tenant-a",
            user_id="user-a",
            provider="google",
            status="active",
            selected_calendar_id_encrypted=encrypt_mfa_secret("calendar-a"),
        )
        task = WorkspaceTask(
            id="task-a",
            tenant_id="tenant-a",
            title="Audiência",
            kind="deadline",
            due_at=datetime(2026, 9, 10, 12, tzinfo=timezone.utc),
            status="pending",
            revision=3,
        )
        link = CalendarTaskLink(
            id="link-a",
            tenant_id="tenant-a",
            connection_id="connection-a",
            task_id="task-a",
            status="tombstoned",
            provider_event_id_encrypted=encrypt_mfa_secret("deleted-event"),
            provider_event_hash=digest("deleted-event"),
            provider_etag='"deleted-etag"',
            last_local_hash="a" * 64,
            last_remote_hash="b" * 64,
            last_synced_at=datetime.now(timezone.utc),
        )
        db = FakeDB([link])

        with patch("app.services.calendar_sync.get_task", AsyncMock(return_value=task)), patch(
            "app.services.calendar_sync.require_task_write"
        ):
            result = await select_tasks(db, user, connection, [task.id])

        self.assertEqual(result, [link])
        self.assertEqual(link.status, "active")
        self.assertIsNone(link.provider_event_id_encrypted)
        self.assertIsNone(link.provider_event_hash)
        self.assertIsNone(link.provider_etag)
        self.assertIsNone(link.last_local_hash)
        self.assertIsNone(link.last_remote_hash)
        self.assertIsNone(link.last_synced_at)
        self.assertEqual(db.commits, 1)
        audit = next(item for item in db.added if item.__class__.__name__ == "AuditLog")
        self.assertEqual(audit.user_id, user.id)
        self.assertEqual(audit.action, "CALENDAR_TASK_LINK_SELECTED")
        self.assertEqual(audit.details["provider"], "google")
        self.assertEqual(audit.details["origin"], "user_selection")
        self.assertEqual(
            audit.details["changes"]["status"],
            {"before": "tombstoned", "after": "active"},
        )
        self.assertEqual(
            audit.details["changes"]["provider_event_bound"],
            {"before": True, "after": False},
        )

    def test_deleted_remote_marker_is_never_reused_after_reactivation(self):
        deleted = RemoteEvent("deleted-event", '"etag-old"', True, None, None, None, None)
        active = RemoteEvent(
            "new-event",
            '"etag-new"',
            False,
            "Audiência",
            datetime(2026, 9, 10, 12, tzinfo=timezone.utc),
            None,
            None,
        )
        self.assertIsNone(_single_recoverable_remote([deleted]))
        self.assertIs(_single_recoverable_remote([deleted, active]), active)

    async def test_calendar_audit_records_safe_before_after_without_tokens_or_raw_notes(self):
        connection = CalendarConnection(
            id="connection-a",
            tenant_id="tenant-a",
            user_id="user-a",
            provider="microsoft",
            access_token_encrypted=encrypt_mfa_secret("do-not-log-token"),
        )
        task = WorkspaceTask(
            id="task-a",
            tenant_id="tenant-a",
            title="Prazo atualizado",
            kind="deadline",
            due_at=datetime(2026, 9, 10, 12, tzinfo=timezone.utc),
            notes="segredo do cliente",
            status="pending",
            revision=8,
        )
        before = _task_audit_state(task)
        task.title = "Prazo confirmado"
        task.notes = "outro segredo do cliente"
        task.revision += 1
        db = FakeDB([])

        await _audit_calendar_change(
            db,
            connection=connection,
            actor_user_id="user-a",
            action="CALENDAR_TASK_REMOTE_APPLIED",
            resource_type="workspace_tasks",
            resource_id=task.id,
            task_id=task.id,
            origin="provider_sync",
            before=before,
            after=_task_audit_state(task),
        )

        audit = next(item for item in db.added if item.__class__.__name__ == "AuditLog")
        serialized = json.dumps(audit.details)
        self.assertEqual(audit.user_id, "user-a")
        self.assertEqual(audit.details["provider"], "microsoft")
        self.assertEqual(audit.details["origin"], "provider_sync")
        self.assertIn("title", audit.details["changes"])
        self.assertIn("notes", audit.details["changes"])
        self.assertNotIn("do-not-log-token", serialized)
        self.assertNotIn("segredo do cliente", serialized)
        self.assertNotIn("outro segredo do cliente", serialized)
        link_state = _link_audit_state(CalendarTaskLink(provider_etag='"sensitive-etag"'))
        self.assertIn("provider_etag_hash", link_state)
        self.assertNotIn("sensitive-etag", json.dumps(link_state))

    async def test_disconnect_audits_links_before_cascade_delete(self):
        connection = CalendarConnection(
            id="connection-a",
            tenant_id="tenant-a",
            user_id="user-a",
            provider="microsoft",
            refresh_token_encrypted=encrypt_mfa_secret("refresh-secret"),
        )
        link = CalendarTaskLink(
            id="link-a",
            tenant_id="tenant-a",
            connection_id="connection-a",
            task_id="task-a",
            status="active",
        )
        db = FakeDB([], scalar_rows=[[link]])

        with patch("app.services.calendar_sync._access_token", AsyncMock(return_value="access")), patch(
            "app.services.calendar_sync._set_tenant_context", AsyncMock()
        ):
            warning = await disconnect_calendar(db, connection)

        self.assertIsNone(warning)
        audit = next(item for item in db.added if item.__class__.__name__ == "AuditLog")
        self.assertEqual(audit.user_id, "user-a")
        self.assertEqual(audit.details["origin"], "user_disconnect")
        self.assertEqual(audit.details["changes"]["exists"], {"before": True, "after": False})
        self.assertIn(("deleted", connection), db.added)
        self.assertEqual(db.commits, 1)

    async def test_google_webhook_requires_the_registered_resource_id(self):
        connection = CalendarConnection(
            id="connection-a", tenant_id="tenant-a", user_id="user-a", provider="google",
            watch_reference_hash=digest("channel-a"), watch_token_hash=digest("secret"),
            watch_resource_hash=digest("resource-a"),
        )
        db = FakeDB([connection])
        resolved, duplicate = await record_webhook(
            db,
            provider="google",
            reference="channel-a",
            token="secret",
            delivery_id="delivery-a",
            payload=b"",
            resource=None,
        )
        self.assertIsNone(resolved)
        self.assertFalse(duplicate)
        self.assertEqual(db.commits, 0)

    def test_task_links_are_tenant_bound_at_both_foreign_keys(self):
        constraints = {
            constraint.name: tuple(column.name for column in constraint.columns)
            for constraint in CalendarTaskLink.__table__.foreign_key_constraints
        }
        self.assertEqual(constraints["fk_calendar_task_link_connection_tenant"], ("tenant_id", "connection_id"))
        self.assertEqual(constraints["fk_calendar_task_link_task_tenant"], ("tenant_id", "task_id"))


if __name__ == "__main__":
    unittest.main()
