import base64
import hashlib
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from app.core.security import decrypt_mfa_secret, encrypt_mfa_secret
from app.models.external_integrations import CalendarConnection, CalendarOAuthState, CalendarTaskLink
from app.models.workspace import WorkspaceTask
from app.services.calendar_providers import OAuthTokens, ProviderAccount
from app.services.calendar_sync import _pkce, _record_conflict, complete_oauth


class FakeDB:
    def __init__(self, scalars):
        self.bind = None
        self._scalars = list(scalars)
        self.added = []
        self.commits = 0

    async def scalar(self, _statement):
        return self._scalars.pop(0)

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        self.commits += 1


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

    def test_task_links_are_tenant_bound_at_both_foreign_keys(self):
        constraints = {
            constraint.name: tuple(column.name for column in constraint.columns)
            for constraint in CalendarTaskLink.__table__.foreign_key_constraints
        }
        self.assertEqual(constraints["fk_calendar_task_link_connection_tenant"], ("tenant_id", "connection_id"))
        self.assertEqual(constraints["fk_calendar_task_link_task_tenant"], ("tenant_id", "task_id"))


if __name__ == "__main__":
    unittest.main()
