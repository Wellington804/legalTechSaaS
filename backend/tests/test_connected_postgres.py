"""Real HTTP/SQL flow against a disposable migrated database with a restricted role.

Set AUDIT_TEST_DATABASE_URL. No provider messages are sent. Each test creates unique
tenants; use a disposable database, never a production/application database.
"""
import os
import unittest
import uuid
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

import httpx
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import _set_tenant_context
from app.core.security import encrypt_mfa_secret, hash_account_token
from app.models.engagement import TenantChannel
from app.core.redis_cache import cache_manager
from app.main import app

DATABASE = os.environ.get("AUDIT_TEST_DATABASE_URL")


class LocalRateLimiter:
    """Only the Redis transport is stubbed; authorization and persistence are real."""
    async def eval(self, script, *args):
        return [1, 1] if "return {a,b}" in script else 1


@unittest.skipUnless(DATABASE, "AUDIT_TEST_DATABASE_URL must point to disposable migrated PostgreSQL")
class ConnectedPostgresTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine(DATABASE, poolclass=NullPool)
        self.Session = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.connect() as db:
            superuser, bypass = (await db.execute(text("SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user"))).one()
            self.assertFalse(superuser or bypass, "Use the restricted runtime role")
        async def database_override():
            async with self.Session() as session:
                yield session
        app.dependency_overrides[get_db] = database_override
        self.old_redis = cache_manager.redis_client
        cache_manager.redis_client = LocalRateLimiter()
        self.transport = httpx.ASGITransport(app=app)
        self.clients = []

    async def asyncTearDown(self):
        for client in self.clients:
            await client.aclose()
        app.dependency_overrides.pop(get_db, None)
        cache_manager.redis_client = self.old_redis
        await self.engine.dispose()

    def client(self):
        client = httpx.AsyncClient(transport=self.transport, base_url="http://testserver", headers={"Origin": "http://localhost:3000"})
        self.clients.append(client)
        return client

    async def request(self, client, method, path, expected=200, **kwargs):
        response = await client.request(method, "/api/v1" + path, **kwargs)
        self.assertEqual(response.status_code, expected, f"{method} {path}: {response.text[:1000]}")
        return response.json() if response.content else None

    async def register(self):
        client = self.client()
        key = uuid.uuid4().hex
        profile = await self.request(client, "POST", "/auth/register", 201, json={"full_name": "Teste Integrado", "tenant_name": f"Office {key}", "email": f"{key}@example.com", "password": "Disposable-Check-123456"})
        return client, profile

    async def test_branding_authenticated_http_and_real_pdf_word_exports(self):
        a, _ = await self.register()
        b, _ = await self.register()
        brand = await self.request(a, "POST", "/branding/profiles", 201, json={"name": "Identidade fictícia", "scope": "personal", "settings": {"header_text": "Advocacia — exemplo fictício", "footer_text": "Somente validação técnica", "header_fields": [], "footer_fields": []}})
        path = f"/branding/profiles/{brand['id']}"
        await self.request(b, "PUT", path, 404, json={"name": "Ataque", "settings": {}, "expected_revision": 1})
        await self.request(a, "POST", path + "/publish", json={"expected_revision": 1})
        await self.request(a, "POST", path + "/publish", 409, json={"expected_revision": 1})
        await self.request(a, "POST", path + "/suggest", 403, json={"brief": "Estilo sóbrio para advocacia", "consent": False, "expected_revision": 2})
        await self.request(a, "POST", path + "/assets", 422, data={"kind": "logo"}, files={"file": ("script.svg", b"<svg onload='evil()'/>", "image/svg+xml")})
        document = await self.request(a, "POST", "/workspace/documents", 201, json={"title": "Minuta fictícia", "content_text": "# Síntese\nTexto **revisado** para teste.\n- Documento editável", "content_format": "markdown"})
        artifact = await self.request(a, "POST", f"/branding/documents/{document['id']}/exports", 201, json={"expected_version": 1})
        repeated = await self.request(a, "POST", f"/branding/documents/{document['id']}/exports", 201, json={"expected_version": 1})
        self.assertEqual(repeated["id"], artifact["id"])
        for format, magic in (("pdf", b"%PDF"), ("docx", b"PK")):
            response = await a.get(f"/api/v1/branding/exports/{artifact['id']}/download?format={format}")
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.content.startswith(magic))
            self.assertEqual(response.headers["cache-control"], "private, no-store")
            await self.request(b, "GET", f"/branding/exports/{artifact['id']}/download?format={format}", 404)
        docs = await self.request(a, "GET", "/workspace/documents")
        self.assertEqual(docs["items"][0]["current_version"], 1)
        self.assertEqual(docs["items"][0]["content_format"], "markdown")
        self.assertIsNone(docs["items"][0]["filename"])
        anonymous = self.client()
        await self.request(anonymous, "GET", "/branding/capabilities", 401)

    async def test_real_push_events_are_atomic_private_and_revoked_on_logout(self):
        import base64
        from app.cli.push_keys import generate_pair
        private, public = generate_pair()
        _, browser_public = generate_pair()
        with patch.multiple(settings, WEB_PUSH_ENABLED=True, WEB_PUSH_VAPID_PRIVATE_KEY=private,
                            WEB_PUSH_VAPID_PUBLIC_KEY=public, WEB_PUSH_VAPID_SUBJECT="mailto:local@example.invalid"):
            staff, profile = await self.register()
            other, _ = await self.register()
            body = {"endpoint": f"https://fcm.googleapis.com/fcm/send/{uuid.uuid4().hex}",
                    "keys": {"p256dh": browser_public, "auth": base64.urlsafe_b64encode(os.urandom(16)).decode().rstrip("=")},
                    "label": "Celular fictício", "consent": True}
            await self.request(staff, "POST", "/push/subscriptions", 403, json=body, headers={"Origin": "https://attacker.example"})
            await self.request(staff, "POST", "/push/subscriptions", 422, json={**body, "consent": False})
            await self.request(self.client(), "GET", "/push/capabilities", 401)
            subscription = await self.request(staff, "POST", "/push/subscriptions", json=body)
            self.assertNotIn("endpoint", subscription)
            self.assertNotIn("keys", subscription)
            self.assertEqual((await self.request(other, "GET", "/push/subscriptions"))["items"], [])
            await self.request(other, "DELETE", f"/push/subscriptions/{subscription['id']}", 404)
            await self.request(other, "POST", "/push/subscriptions", 409, json=body)
            client = await self.request(staff, "POST", "/workspace/clients", 201, json={"name": "Cliente privado"})
            case = await self.request(staff, "POST", "/workspace/cases", 201, json={"client_id": client["id"], "title": "Caso privado", "responsible_user_id": profile["user_id"]})
            task = await self.request(staff, "POST", "/workspace/tasks", 201, json={"title": "Tarefa privada", "case_id": case["id"], "assigned_user_id": profile["user_id"]})
            task = await self.request(staff, "PUT", f"/workspace/tasks/{task['id']}", json={"expected_revision": task["revision"], "assigned_user_id": None})
            await self.request(staff, "PUT", f"/workspace/tasks/{task['id']}", json={"expected_revision": task["revision"], "assigned_user_id": profile["user_id"]})
            invite = await self.request(staff, "POST", f"/engagement/cases/{case['id']}/portal-invites", 201)
            token = parse_qs(urlsplit(invite["invite_link"]).fragment)["token"][0]
            portal = self.client()
            await self.request(portal, "POST", "/client-portal/redeem", json={"token": token})
            message = {"request_id": str(uuid.uuid4()), "channel": "portal", "body": "Conteúdo sigiloso"}
            await self.request(portal, "POST", "/client-portal/messages", 201, json=message)
            await self.request(portal, "POST", "/client-portal/messages", 201, json=message)
            item = await self.request(staff, "POST", f"/engagement/cases/{case['id']}/checklist", 201, json={"title": "Documento particular"})
            await self.request(portal, "POST", f"/client-portal/documents/{item['id']}/upload", 201, files={"file": ("privado.txt", b"Arquivo sigiloso", "text/plain")})
            async with self.Session() as db:
                await _set_tenant_context(db, profile["tenant_id"])
                rows = (await db.execute(text("SELECT kind,status FROM push_deliveries WHERE subscription_id=:id"), {"id": subscription["id"]})).all()
                self.assertCountEqual(rows, [("task_assigned", "queued"), ("task_assigned", "queued"), ("portal_message", "queued"), ("portal_document", "queued")])
                stored = await db.scalar(text("SELECT credentials_encrypted FROM push_subscriptions WHERE id=:id"), {"id": subscription["id"]})
                self.assertNotIn(body["endpoint"], stored)
            await self.request(staff, "POST", "/auth/logout", 204)
            async with self.Session() as db:
                await _set_tenant_context(db, profile["tenant_id"])
                count = await db.scalar(text("SELECT count(*) FROM push_deliveries WHERE subscription_id=:id AND status='cancelled'"), {"id": subscription["id"]})
                self.assertEqual(count, 4)
                self.assertIsNotNone(await db.scalar(text("SELECT revoked_at FROM push_subscriptions WHERE id=:id"), {"id": subscription["id"]}))

    async def test_connected_case_document_ledger_portal_and_revocation(self):
        a, profile = await self.register()
        b, other_profile = await self.register()
        team_invite = await self.request(a, "POST", "/account/team/invites", 201, json={"email": f"invite-{uuid.uuid4().hex}@example.com", "role": "lawyer"})
        pending = await self.request(a, "GET", "/account/team/invites")
        self.assertEqual(pending["items"][0]["id"], team_invite["id"])
        self.assertNotIn("invite_link", pending["items"][0])
        self.assertNotIn("token_hash", pending["items"][0])
        self.assertEqual((await self.request(b, "GET", "/account/team/invites"))["items"], [])
        await self.request(b, "POST", f"/account/team/invites/{team_invite['id']}/cancel", 404, json={})
        await self.request(a, "POST", f"/account/team/invites/{team_invite['id']}/cancel", 204, json={})
        self.assertEqual((await self.request(a, "GET", "/account/team/invites"))["items"], [])
        client = await self.request(a, "POST", "/workspace/clients", 201, json={"name": "Cliente Teste", "email": "client@example.com", "stage": "client"})
        case = await self.request(a, "POST", "/workspace/cases", 201, json={"client_id": client["id"], "title": "Caso de integração", "responsible_user_id": profile["user_id"], "restricted": True})
        case_id = case["id"]
        await self.request(b, "GET", f"/workspace/cases/{case_id}", 404)
        await self.request(a, "POST", "/workspace/tasks", 201, json={"case_id": case_id, "title": "Conferir prazo", "kind": "deadline", "due_at": "2027-01-10T15:00:00Z", "manually_reviewed": True})
        document = await self.request(a, "POST", "/workspace/documents", 201, json={"case_id": case_id, "title": "Peça inicial", "content_text": "Texto da primeira versão."})
        doc_id = document["id"]
        version = await self.request(a, "PUT", f"/workspace/documents/{doc_id}", json={"content_text": "Segunda versão.", "expected_version": 1})
        self.assertEqual(version["current_version"], 2)
        await self.request(a, "PUT", f"/workspace/documents/{doc_id}", 409, json={"content_text": "Edição desatualizada", "expected_version": 1})
        await self.request(a, "POST", f"/workspace/documents/{doc_id}/upload", data={"expected_version": "2"}, files={"file": ("documento.txt", b"Arquivo privado real", "text/plain")})
        await self.request(b, "GET", f"/workspace/documents/{doc_id}/download", 404)
        binary = await a.get(f"/api/v1/workspace/documents/{doc_id}/download")
        self.assertEqual(binary.content, b"Arquivo privado real")
        payment = {"request_id": str(uuid.uuid4()), "case_id": case_id, "amount": "123.45", "description": "Honorário recebido", "confirmation_reason": "Conferência manual do comprovante"}
        first = await self.request(a, "POST", "/workspace/ledger/payments/manual", 201, json=payment)
        duplicate = await a.post("/api/v1/workspace/ledger/payments/manual", json=payment)
        self.assertIn(duplicate.status_code, (200, 201))
        self.assertEqual(first["id"], duplicate.json()["id"])
        await self.request(a, "POST", f"/workspace/ledger/{first['id']}/reverse", json={"reason": "Correção do registro"})
        await self.request(a, "POST", f"/workspace/ledger/{first['id']}/reverse", 409, json={"reason": "Tentativa duplicada"})
        checklist = await self.request(a, "POST", f"/engagement/cases/{case_id}/checklist", 201, json={"title": "Documento aprovado para compartilhar", "document_id": doc_id})
        message = {"request_id": str(uuid.uuid4()), "channel": "portal", "body": "Mensagem persistida no portal"}
        sent = await self.request(a, "POST", f"/engagement/cases/{case_id}/messages", 202, json=message)
        repeated = await self.request(a, "POST", f"/engagement/cases/{case_id}/messages", 202, json=message)
        self.assertEqual(sent["id"], repeated["id"])
        invite = await self.request(a, "POST", f"/engagement/cases/{case_id}/portal-invites", 201)
        token = parse_qs(urlsplit(invite["invite_link"]).fragment)["token"][0]
        portal = self.client()
        await self.request(portal, "POST", "/client-portal/redeem", json={"token": token})
        await self.request(self.client(), "POST", "/client-portal/redeem", 401, json={"token": token})
        page = await self.request(portal, "GET", "/client-portal")
        self.assertEqual(page["case"]["title"], case["title"])
        self.assertEqual(page["messages"][0]["body"], message["body"])
        response = await portal.get(f"/api/v1/client-portal/documents/{checklist['id']}")
        self.assertEqual(response.content, b"Arquivo privado real")
        requested_file = await self.request(a, "POST", f"/engagement/cases/{case_id}/checklist", 201, json={"title": "Comprovante do cliente"})
        received = await self.request(portal, "POST", f"/client-portal/documents/{requested_file['id']}/upload", 201, files={"file": ("comprovante.txt", b"Documento do cliente", "text/plain")})
        history = await self.request(a, "GET", f"/workspace/documents/{received['document_id']}/versions")
        self.assertEqual(history["items"][0]["created_by_portal_grant_id"], invite["id"])
        self.assertIsNone(history["items"][0]["created_by_user_id"])
        other_client = await self.request(b, "POST", "/workspace/clients", 201, json={"name": "Outro cliente"})
        other_case = await self.request(b, "POST", "/workspace/cases", 201, json={"client_id": other_client["id"], "title": "Outro caso", "responsible_user_id": other_profile["user_id"]})
        other_invite = await self.request(b, "POST", f"/engagement/cases/{other_case['id']}/portal-invites", 201)
        async with self.Session() as db:
            await _set_tenant_context(db, profile["tenant_id"])
            with self.assertRaises(IntegrityError):
                await db.execute(text("""INSERT INTO workspace_document_versions
                    (id,tenant_id,document_id,version,created_by_portal_grant_id,created_at)
                    VALUES (:id,:tenant,:doc,99,:grant,now())"""),
                    {"id": str(uuid.uuid4()), "tenant": profile["tenant_id"], "doc": doc_id, "grant": other_invite["id"]})
            await db.rollback()
        await self.request(portal, "GET", "/client-portal/documents/not-shared", 404)
        await self.request(portal, "POST", "/client-portal/messages", 201, json={"request_id": str(uuid.uuid4()), "body": "Recebi o documento.", "channel": "portal"})
        await self.request(a, "DELETE", f"/engagement/portal-invites/{invite['id']}", 204)
        await self.request(portal, "GET", "/client-portal", 401)
        cookie = a.cookies.get(settings.COOKIE_NAME)
        await self.request(a, "POST", "/auth/logout", 204)
        replay = self.client()
        replay.cookies.set(settings.COOKIE_NAME, cookie)
        await self.request(replay, "GET", "/auth/me", 401)

    async def test_runtime_functions_and_no_context_rls(self):
        _, profile = await self.register()
        instance_id = f"test-{uuid.uuid4().hex}"
        encrypted = encrypt_mfa_secret("local-test-token-not-real")
        async with self.Session() as db:
            await _set_tenant_context(db, profile["tenant_id"])
            db.add(TenantChannel(tenant_id=profile["tenant_id"], whatsapp_enabled=True,
                                 evolution_instance_id_encrypted=encrypt_mfa_secret(instance_id),
                                 evolution_instance_id_hash=hash_account_token(instance_id),
                                 evolution_token_encrypted=encrypted))
            await db.commit()
        async with self.Session() as db:
            for table in ("workspace_clients", "workspace_cases", "workspace_documents", "case_messages", "portal_grants", "tenant_channels"):
                rows = await db.execute(text(f'SELECT id FROM "{table}" LIMIT 1') if table != "tenant_channels" else text("SELECT tenant_id FROM tenant_channels LIMIT 1"))
                self.assertEqual(rows.all(), [])
            rows = await db.execute(text("SELECT * FROM tenant_channel_webhook_identity('nonexistent-instance')"))
            self.assertEqual(rows.all(), [])
            row = (await db.execute(text("SELECT * FROM tenant_channel_webhook_identity(:instance_hash)"),
                                    {"instance_hash": hash_account_token(instance_id)})).one()
            self.assertEqual(tuple(row), (profile["tenant_id"], encrypted))
            can_update, can_delete = (await db.execute(text("SELECT has_table_privilege(current_user, 'workspace_document_versions', 'UPDATE'), has_table_privilege(current_user, 'workspace_ledger_entries', 'DELETE')"))).one()
            self.assertFalse(can_update or can_delete)
            await db.execute(text("SELECT * FROM notification_recovery_candidates(60,10)"))


if __name__ == "__main__":
    unittest.main()
