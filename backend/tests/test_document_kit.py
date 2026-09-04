"""Draft-boundary checks plus real HTTP/RLS/idempotency against disposable PostgreSQL."""
import asyncio
import os
import unittest
import uuid
from types import SimpleNamespace

import httpx
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.database import get_db
from app.core.dependencies import _set_tenant_context
from app.core.redis_cache import cache_manager
from app.main import app
from app.models.user import User
from app.schemas.document_kit import DocumentKitCreate, DocumentKitPreview
from app.services.document_kit import TEMPLATES, catalog, render_preview
from tests.test_connected_postgres import LocalRateLimiter


class DocumentKitTests(unittest.TestCase):
    def setUp(self):
        self.sources = {
            "case": SimpleNamespace(id="case", title="Caso fictício", number=None, court=None, revision=1),
            "client": SimpleNamespace(id="client", name="Cliente fictício", tax_id=None, revision=1, email=None, phone=None),
            "lawyer": SimpleNamespace(id="lawyer", full_name="Advogada fictícia", oab_number=None, oab_uf=None),
            "tenant": SimpleNamespace(id="tenant", name="Escritório fictício"),
        }

    def test_missing_fields_do_not_invent_legal_terms_or_authoritative_values(self):
        self.assertEqual(len(catalog()["items"]), 8)
        for template_key in TEMPLATES:
            rendered = render_preview(DocumentKitPreview(template_key=template_key, case_id="case"), **self.sources)
            self.assertIn("Modelo genérico não homologado", rendered["content_text"])
            self.assertTrue(rendered["review_required"])
            self.assertTrue(rendered["missing_fields"])
            self.assertNotIn("R$", rendered["content_text"])
        with self.assertRaises(HTTPException) as forbidden:
            render_preview(DocumentKitPreview(template_key="intake", case_id="case", values={"client.name": "Override"}), **self.sources)
        self.assertEqual(forbidden.exception.status_code, 422)
        self.sources["client"].tax_id = "00000000000"
        self.sources["lawyer"].oab_number = "123456"
        self.sources["lawyer"].oab_uf = "SP"
        for key in ("power_of_attorney", "fee_agreement"):
            values = {item["key"]: "Condição fictícia informada e conferida" for item in TEMPLATES[key]["fields"]}
            values["signed_on"] = "2026-08-28"
            rendered = render_preview(DocumentKitPreview(template_key=key, case_id="case", values=values), **self.sources)
            self.assertEqual(rendered["missing_fields"], [])
            self.assertIn("28/08/2026", rendered["content_text"])
            self.assertIn("Condição fictícia informada e conferida", rendered["content_text"])

    def test_fingerprint_binds_terms_profile_and_revision_and_draft_is_plain(self):
        payload = DocumentKitPreview(template_key="intake", case_id="case", values={"summary": "Relato conferido {{not_executable}}"})
        original = render_preview(payload, **self.sources)
        self.assertEqual(original["content_format"], "plain")
        self.assertEqual(original["missing_fields"], [])
        self.assertIn("{{not_executable}}", original["content_text"])
        self.assertEqual(original, render_preview(payload, **self.sources))
        changed = render_preview(payload.model_copy(update={"values": {"summary": "Termos diferentes"}}), **self.sources)
        self.assertNotEqual(original["source"], changed["source"])
        self.sources["lawyer"].full_name = "Outro nome cadastrado"
        self.assertNotEqual(original["source"], render_preview(payload, **self.sources)["source"])
        self.sources["case"].revision = 2
        self.assertEqual(render_preview(payload, **self.sources)["source"]["case_revision"], 2)

    def test_saved_professional_and_client_data_fill_repeated_fields(self):
        self.sources["client"].qualification = "brasileira, empresária"
        self.sources["client"].occupation = None
        self.sources["client"].person_type = "company"
        self.sources["client"].has_legal_representative = True
        self.sources["client"].representative_name = "Ana Representante"
        self.sources["client"].representative_tax_id = "12345678901"
        self.sources["client"].representative_qualification = "brasileira, empresária"
        self.sources["client"].representative_email = "ana@example.test"
        self.sources["client"].representative_phone = "+5511999999999"
        self.sources["client"].representative_address = {"street": "Rua Dois", "number": "20", "city": "São Paulo", "state": "SP", "postal_code": "01000-001"}
        self.sources["client"].address = {"street": "Rua Um", "number": "10", "city": "São Paulo", "state": "SP", "postal_code": "01000-000"}
        self.sources["lawyer"].professional_address = {"street": "Avenida Central", "number": "100", "city": "São Paulo", "state": "SP", "postal_code": "01001-000"}
        self.sources["tenant"].office_address = None
        self.sources["tenant"].signature_city = "São Paulo"
        self.sources["lawyer"].professional_name = "Dra. Advogada"
        self.sources["client"].tax_id = "00000000000"
        self.sources["lawyer"].oab_number = "123456"
        self.sources["lawyer"].oab_uf = "SP"
        values = {"scope": "Atuação conferida", "powers": "Poderes conferidos", "signed_on": "2026-08-30"}
        rendered = render_preview(DocumentKitPreview(template_key="power_of_attorney", case_id="case", values=values), **self.sources)
        self.assertEqual(rendered["missing_fields"], [])
        self.assertIn("Rua Um, 10", rendered["content_text"])
        self.assertIn("representada por Ana Representante", rendered["content_text"])
        self.assertIn("CPF/CNPJ 12345678901", rendered["content_text"])
        self.assertIn("WhatsApp +5511999999999", rendered["content_text"])
        self.assertIn("Rua Dois, 20", rendered["content_text"])
        self.assertIn("Assinatura do representante legal", rendered["content_text"])
        self.assertIn("Avenida Central, 100", rendered["content_text"])

    def test_explicit_review_dates_and_input_limits(self):
        preview = DocumentKitPreview(template_key="intake", case_id="case", values={"summary": "Relato"})
        source = render_preview(preview, **self.sources)["source"]
        for reviewed in (False, "true", 1):
            with self.assertRaises(ValidationError):
                DocumentKitCreate(**preview.model_dump(), request_id=uuid.uuid4(), source=source, reviewed=reviewed)
        for bad_value in ("\x00", "<script>alert(1)</script>", "x" * 4001):
            with self.assertRaises(ValidationError):
                DocumentKitPreview(template_key="intake", case_id="case", values={"summary": bad_value})
        with self.assertRaises(HTTPException):
            render_preview(DocumentKitPreview(template_key="power_of_attorney", case_id="case", values={"signed_on": "2026-02-30"}), **self.sources)


@unittest.skipUnless(os.environ.get("AUDIT_TEST_DATABASE_URL"), "Requires disposable migrated PostgreSQL with NOBYPASSRLS")
class DocumentKitPostgresTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine(os.environ["AUDIT_TEST_DATABASE_URL"], poolclass=NullPool)
        self.Session = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.connect() as conn:
            role = (await conn.execute(text("SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user"))).one()
            self.assertFalse(any(role))
        async def database_override():
            async with self.Session() as session:
                yield session
        app.dependency_overrides[get_db] = database_override
        self.old_redis = cache_manager.redis_client
        cache_manager.redis_client = LocalRateLimiter()
        self.clients = []

    async def asyncTearDown(self):
        for client in self.clients:
            await client.aclose()
        app.dependency_overrides.pop(get_db, None)
        cache_manager.redis_client = self.old_redis
        await self.engine.dispose()

    def client(self):
        client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver", headers={"Origin": "http://localhost:3000"})
        self.clients.append(client)
        return client

    async def request(self, client, method, path, expected=200, **kwargs):
        response = await client.request(method, "/api/v1" + path, **kwargs)
        self.assertEqual(response.status_code, expected, response.text[:1000])
        return response.json() if response.content else None

    async def register(self):
        client = self.client()
        profile = await self.request(client, "POST", "/auth/register", 201, json={"full_name": "Advogada fictícia", "tenant_name": f"Kit {uuid.uuid4()}", "email": f"{uuid.uuid4()}@example.com", "password": "Disposable-Check-123456"})
        return client, profile

    async def test_real_preview_commit_retry_acl_quota_and_immutable_receipt(self):
        a, profile = await self.register()
        b, other = await self.register()
        await self.request(self.client(), "GET", "/document-kit/templates", 401)
        self.assertEqual(len((await self.request(a, "GET", "/document-kit/templates"))["items"]), 8)
        client = await self.request(a, "POST", "/workspace/clients", 201, json={"name": "Cliente fictício"})
        case = await self.request(a, "POST", "/workspace/cases", 201, json={"client_id": client["id"], "title": "Caso restrito fictício", "responsible_user_id": profile["user_id"], "restricted": True})
        values = {"summary": "Relato fictício revisado", "next_action": "Conferir documentos"}
        payload = {"template_key": "intake", "case_id": case["id"], "values": values}
        preview = await self.request(a, "POST", "/document-kit/preview", json=payload)
        await self.request(b, "POST", "/document-kit/preview", 404, json=payload)
        await self.request(a, "POST", "/document-kit/preview", 422, json={**payload, "values": {"lawyer.oab_number": "123"}})
        await self.request(a, "POST", "/document-kit/preview", 403, json=payload, headers={"Origin": "https://attacker.example"})
        creation = {**payload, "request_id": str(uuid.uuid4()), "source": preview["source"], "reviewed": True}
        await self.request(a, "POST", "/document-kit/documents", 422, json={**creation, "reviewed": False})
        await self.request(a, "POST", "/document-kit/documents", 409, json={**creation, "values": {"summary": "Texto alterado sem revisão"}})
        # A profile edit invalidates even a forged-looking, syntactically valid client snapshot.
        await self.request(a, "PATCH", "/account/profile", json={"full_name": "Nome atualizado fictício"})
        await self.request(a, "POST", "/document-kit/documents", 409, json=creation)
        preview = await self.request(a, "POST", "/document-kit/preview", json=payload)
        creation["source"] = preview["source"]
        first, repeated = await asyncio.gather(*[self.request(a, "POST", "/document-kit/documents", 201, json=creation) for _ in range(2)])
        document = first["document"]
        self.assertEqual(document["id"], repeated["document"]["id"])
        self.assertEqual(document["content_text"], preview["content_text"])
        self.assertEqual(document["content_format"], "plain")
        self.assertEqual(document["current_version"], 1)
        await self.request(a, "POST", "/document-kit/documents", 409, json={**creation, "values": {"summary": "Outra solicitação"}})
        incomplete = {"template_key": "power_of_attorney", "case_id": case["id"], "values": {}}
        missing = await self.request(a, "POST", "/document-kit/preview", json=incomplete)
        self.assertIn("lawyer.oab_number", {item["key"] for item in missing["missing_fields"]})
        await self.request(a, "POST", "/document-kit/documents", 422, json={**incomplete, "request_id": str(uuid.uuid4()), "source": missing["source"], "reviewed": True})
        async with self.Session() as db:
            await _set_tenant_context(db, profile["tenant_id"])
            self.assertEqual(await db.scalar(text("SELECT count(*) FROM document_kit_receipts")), 1)
            self.assertEqual(await db.scalar(text("SELECT count(*) FROM workspace_document_versions WHERE document_id=:id"), {"id": document["id"]}), 1)
            owner = await db.get(User, profile["user_id"])
            stranger_email = f"{uuid.uuid4()}@example.com"
            db.add(User(tenant_id=profile["tenant_id"], full_name="Outro advogado", email=stranger_email, hashed_password=owner.hashed_password, role="lawyer"))
            await db.execute(text("UPDATE tenants SET quota_storage_bytes=0 WHERE id=:id"), {"id": profile["tenant_id"]})
            await db.commit()
        stranger = self.client()
        await self.request(stranger, "POST", "/auth/login", json={"email": stranger_email, "password": "Disposable-Check-123456"})
        await self.request(stranger, "POST", "/document-kit/preview", 404, json=payload)
        await self.request(stranger, "POST", "/document-kit/documents", 404, json=creation)
        await self.request(a, "POST", "/document-kit/documents", 413, json={**creation, "request_id": str(uuid.uuid4())})
        # Previously committed requests can be recovered without charging quota twice.
        self.assertEqual((await self.request(a, "POST", "/document-kit/documents", 201, json=creation))["document"]["id"], document["id"])
        async with self.Session() as db:
            await _set_tenant_context(db, other["tenant_id"])
            self.assertEqual(await db.scalar(text("SELECT count(*) FROM document_kit_receipts WHERE tenant_id=:id"), {"id": profile["tenant_id"]}), 0)
            await db.rollback()
            await _set_tenant_context(db, profile["tenant_id"])
            self.assertEqual(await db.scalar(text("SELECT count(*) FROM document_kit_receipts")), 1)
            with self.assertRaises(DBAPIError):
                await db.execute(text("UPDATE document_kit_receipts SET payload_hash='changed'"))
            await db.rollback()
