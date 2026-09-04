import asyncio
import io
import hashlib
import json
import unittest
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, call, patch

import httpx
from fastapi import HTTPException, UploadFile
from pydantic import ValidationError

from app.api.v1.endpoints import research
from app.core.config import Settings


REAL_ASYNC_CLIENT = httpx.AsyncClient


def mock_async_client(handler):
    def factory(**kwargs):
        return REAL_ASYNC_CLIENT(transport=httpx.MockTransport(handler), **kwargs)

    return factory


class ResearchDatabase:
    bind = None

    def __init__(self, channel=None):
        self.channel = channel
        self.added = []
        self.commits = 0

    async def get(self, _model, _identity):
        return self.channel

    def add(self, item):
        if getattr(item, "id", None) is None and item.__class__.__name__ == "AIConversation":
            item.id = "conversation-test"
            item.message_count = 0
        self.added.append(item)

    def add_all(self, items):
        for item in items:
            self.add(item)

    async def flush(self):
        return None

    async def commit(self):
        self.commits += 1

    @asynccontextmanager
    async def begin_nested(self):
        yield self


class ResearchEndpointTests(unittest.TestCase):
    user = SimpleNamespace(id="user-a", tenant_id="tenant-a", role="lawyer")
    valid_cnj = "00000000000000000000"

    def test_zero_ai_quota_disables_daily_limit_without_redis(self):
        self.assertEqual(Settings(_env_file=None, AI_REQUESTS_PER_DAY=0).AI_REQUESTS_PER_DAY, 0)
        with patch.object(research.cache_manager, "redis_client", None):
            asyncio.run(research.reserve_request(self.user.tenant_id, "ai", 0, 86400))

    def test_datajud_tribunal_whitelist_blocks_untrusted_destination(self):
        async def run():
            ensure_write = AsyncMock()
            get_case = AsyncMock(
                return_value=SimpleNamespace(id="case-a", number=self.valid_cnj)
            )
            with (
                patch.object(research, "ensure_tenant_write_access", ensure_write),
                patch.object(research, "get_case", get_case),
            ):
                with self.assertRaises(HTTPException) as caught:
                    await research.sync_case(
                        "case-a", research.SyncInput(tribunal="metadata"), self.user, ResearchDatabase()
                    )
            self.assertEqual(caught.exception.status_code, 422)
            ensure_write.assert_awaited_once()
            get_case.assert_awaited_once()

        asyncio.run(run())

    def test_datajud_without_credentials_fails_before_rate_limit_or_network(self):
        async def run():
            reserve = AsyncMock()
            config = SimpleNamespace(DATAJUD_ENABLED=False, DATAJUD_API_KEY=None)
            with (
                patch.object(research, "settings", config),
                patch.object(research, "ensure_tenant_write_access", AsyncMock()),
                patch.object(
                    research,
                    "get_case",
                    AsyncMock(return_value=SimpleNamespace(id="case-a", number=self.valid_cnj)),
                ),
                patch.object(research, "reserve_request", reserve),
            ):
                with self.assertRaises(HTTPException) as caught:
                    await research.sync_case(
                        "case-a", research.SyncInput(tribunal="tjsp"), self.user, ResearchDatabase()
                    )
            self.assertEqual(caught.exception.status_code, 503)
            reserve.assert_not_awaited()

        asyncio.run(run())

    def test_datajud_ignores_hit_for_a_different_cnj(self):
        async def run():
            requests = []

            def handler(request):
                requests.append(request)
                self.assertEqual(request.url.host, "api-publica.datajud.cnj.jus.br")
                self.assertEqual(request.headers["Authorization"], "APIKey test-key")
                self.assertEqual(
                    json.loads(request.content)["query"]["match"]["numeroProcesso"], self.valid_cnj
                )
                return httpx.Response(
                    200,
                    json={
                        "hits": {
                            "hits": [
                                {
                                    "_source": {
                                        "numeroProcesso": "11111111111111111111",
                                        "movimentos": [
                                            {"nome": "Não deve importar", "dataHora": "2026-08-27T10:00:00Z"}
                                        ],
                                    }
                                }
                            ]
                        }
                    },
                )

            db = ResearchDatabase()
            audit = AsyncMock()
            with (
                patch.object(
                    research,
                    "settings",
                    SimpleNamespace(DATAJUD_ENABLED=True, DATAJUD_API_KEY="test-key"),
                ),
                patch.object(research, "ensure_tenant_write_access", AsyncMock()),
                patch.object(
                    research,
                    "get_case",
                    AsyncMock(return_value=SimpleNamespace(id="case-a", number=self.valid_cnj)),
                ),
                patch.object(research, "reserve_request", AsyncMock()),
                patch.object(research.AuditService, "log_action", audit),
                patch.object(research.httpx, "AsyncClient", mock_async_client(handler)),
            ):
                result = await research.sync_case(
                    "case-a", research.SyncInput(tribunal="tjsp"), self.user, db
                )
            self.assertEqual(result["imported"], 0)
            self.assertTrue(result["manual_review_required"])
            self.assertEqual(result["deadlines_created"], 0)
            self.assertEqual(db.added, [])
            self.assertEqual(db.commits, 1)
            self.assertEqual(len(requests), 1)
            audit.assert_awaited_once()

        asyncio.run(run())

    def test_datajud_rejects_malformed_source_before_any_publication_or_commit(self):
        async def run():
            def handler(_request):
                return httpx.Response(200, json={"hits": {"hits": [{"_source": ["not-a-record"]}]}})

            db = ResearchDatabase()
            audit = AsyncMock()
            with (
                patch.object(
                    research,
                    "settings",
                    SimpleNamespace(DATAJUD_ENABLED=True, DATAJUD_API_KEY="test-key"),
                ),
                patch.object(research, "ensure_tenant_write_access", AsyncMock()),
                patch.object(
                    research,
                    "get_case",
                    AsyncMock(return_value=SimpleNamespace(id="case-a", number=self.valid_cnj)),
                ),
                patch.object(research, "reserve_request", AsyncMock()),
                patch.object(research.AuditService, "log_action", audit),
                patch.object(research.httpx, "AsyncClient", mock_async_client(handler)),
            ):
                with self.assertRaises(HTTPException) as caught:
                    await research.sync_case(
                        "case-a", research.SyncInput(tribunal="tjsp"), self.user, db
                    )
            self.assertEqual(caught.exception.status_code, 502)
            self.assertEqual(db.added, [])
            self.assertEqual(db.commits, 0)
            audit.assert_not_awaited()

        asyncio.run(run())

    def test_ai_requires_explicit_user_consent_before_provider_request(self):
        with self.assertRaises(ValidationError):
            research.AssistantInput(question="Organize o atendimento", consent="yes")

        async def run():
            reserve = AsyncMock()
            db = ResearchDatabase(channel=SimpleNamespace(ai_enabled=True))
            with (
                patch.object(research, "ensure_tenant_write_access", AsyncMock()),
                patch.object(
                    research,
                    "get_document",
                    AsyncMock(return_value=SimpleNamespace(id="doc-a", content_text="texto", current_version=1)),
                ),
                patch.object(research, "reserve_request", reserve),
            ):
                with self.assertRaises(HTTPException) as caught:
                    await research.assist_document(
                        "doc-a", research.AssistInput(consent=False), self.user, db
                    )
            self.assertEqual(caught.exception.status_code, 403)
            reserve.assert_not_awaited()
            self.assertEqual(db.commits, 0)

        asyncio.run(run())

    def test_chat_attachment_is_validated_and_forwarded_with_send_consent(self):
        async def run():
            forwarded = AsyncMock(return_value={"text": "resposta", "sources": [], "limitations": []})
            upload = UploadFile(filename="referencia.txt", file=io.BytesIO(b"Fatos fornecidos pelo advogado."))
            with patch.object(research, "_contextual_assistant", forwarded):
                result = await research.assistant_chat(
                    question="Resuma o documento anexado",
                    context_kind="global",
                    client_id=None,
                    case_id=None,
                    document_id=None,
                    history='[{"role":"assistant","content":"Como posso ajudar?"}]',
                    conversation_id=None,
                    retention_days=90,
                    consent=True,
                    files=[upload],
                    user=self.user,
                    db=ResearchDatabase(),
                )
            return result, forwarded

        result, forwarded = asyncio.run(run())
        self.assertEqual(result["text"], "resposta")
        self.assertEqual(result["conversation_id"], "conversation-test")
        body = forwarded.await_args.args[0]
        self.assertTrue(body.consent)
        self.assertEqual(forwarded.await_args.kwargs["history"][0].role, "assistant")
        self.assertIn("Fatos fornecidos", forwarded.await_args.kwargs["attachments"][0]["text"])

    def test_chat_accepts_explicit_true_from_multipart_form(self):
        async def run():
            from fastapi import FastAPI
            from app.core.database import get_db
            from app.core.dependencies import get_current_user

            app = FastAPI()
            app.include_router(research.router, prefix="/engagement")
            app.dependency_overrides[get_current_user] = lambda: self.user
            app.dependency_overrides[get_db] = lambda: ResearchDatabase()
            with patch.object(research, "_contextual_assistant", AsyncMock(return_value={"text": "ok", "sources": [], "limitations": []})):
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                    return await client.post("/engagement/assistant/chat", data={
                        "question": "Responda apenas com ok",
                        "context_kind": "global",
                        "consent": "true",
                    })

        response = asyncio.run(run())
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["text"], "ok")
        self.assertEqual(response.json()["conversation_id"], "conversation-test")

    def test_ai_response_is_snapshot_bound_stale_and_output_limited(self):
        async def run():
            source_text = "Fatos relevantes para revisão."
            initial = SimpleNamespace(id="doc-a", content_text=source_text, current_version=7)
            current = SimpleNamespace(id="doc-a", content_text="versão atual", current_version=8)
            db = ResearchDatabase(channel=SimpleNamespace(ai_enabled=True))
            audit = AsyncMock()
            set_tenant_context = AsyncMock()
            seen_requests = []

            def handler(request):
                seen_requests.append(request)
                self.assertEqual(request.url.host, "generativelanguage.googleapis.com")
                self.assertEqual(request.headers["x-goog-api-key"], "gemini-test-key")
                payload = json.loads(request.content)
                self.assertIn(source_text, payload["contents"][0]["parts"][0]["text"])
                return httpx.Response(
                    200,
                    json={
                        "candidates": [
                            {"content": {"parts": [{"text": "x" * 16001}]}}
                        ]
                    },
                )

            get_document = AsyncMock(side_effect=[initial, current])
            with (
                patch.object(
                    research,
                    "settings",
                    SimpleNamespace(
                        AI_ENABLED=True,
                        GEMINI_API_KEY="gemini-test-key",
                        GEMINI_MODEL="gemini-1.5-flash",
                        AI_REQUESTS_PER_DAY=20,
                    ),
                ),
                patch.object(research, "ensure_tenant_write_access", AsyncMock()),
                patch.object(research, "get_document", get_document),
                patch.object(research, "reserve_request", AsyncMock()),
                patch.object(research, "_set_tenant_context", set_tenant_context),
                patch.object(research.AuditService, "log_action", audit),
                patch.object(research.httpx, "AsyncClient", mock_async_client(handler)),
            ):
                result = await research.assist_document(
                    "doc-a", research.AssistInput(purpose="summary", consent=True), self.user, db
                )
            self.assertTrue(result["stale"])
            self.assertFalse(result["saved"])
            self.assertTrue(result["review_required"])
            self.assertEqual(result["source"]["version"], 7)
            self.assertEqual(result["source"]["sha256"], hashlib.sha256(source_text.encode()).hexdigest())
            self.assertEqual(len(result["text"]), 16000)
            self.assertEqual(db.commits, 2)
            self.assertEqual(len(seen_requests), 1)
            set_tenant_context.assert_awaited_once_with(db, self.user.tenant_id)
            self.assertEqual(audit.await_count, 2)
            self.assertEqual(
                get_document.await_args_list,
                [call(db, self.user, "doc-a"), call(db, self.user, "doc-a", refresh=True)],
            )

        asyncio.run(run())

    def test_ai_rejects_malformed_provider_payload_or_parts(self):
        async def run():
            for malformed_response in (
                ["not-an-object"],
                {"candidates": [{"content": {"parts": {"text": "not-a-list"}}}]},
            ):
                def handler(_request, payload=malformed_response):
                    return httpx.Response(200, json=payload)

                db = ResearchDatabase(channel=SimpleNamespace(ai_enabled=True))
                audit = AsyncMock()
                with (
                    patch.object(
                        research,
                        "settings",
                        SimpleNamespace(
                            AI_ENABLED=True,
                            GEMINI_API_KEY="gemini-test-key",
                            GEMINI_MODEL="gemini-1.5-flash",
                            AI_REQUESTS_PER_DAY=20,
                        ),
                    ),
                    patch.object(research, "ensure_tenant_write_access", AsyncMock()),
                    patch.object(
                        research,
                        "get_document",
                        AsyncMock(
                            return_value=SimpleNamespace(
                                id="doc-a", content_text="texto para revisão", current_version=1
                            )
                        ),
                    ),
                    patch.object(research, "reserve_request", AsyncMock()),
                    patch.object(research.AuditService, "log_action", audit),
                    patch.object(research.httpx, "AsyncClient", mock_async_client(handler)),
                ):
                    with self.assertRaises(HTTPException) as caught:
                        await research.assist_document(
                            "doc-a", research.AssistInput(consent=True), self.user, db
                        )
                self.assertEqual(caught.exception.status_code, 502)
                self.assertEqual(db.commits, 1, "request audit is committed; no result is saved")
                self.assertEqual(audit.await_count, 1)

        asyncio.run(run())

    def test_ai_rejects_oversized_document_before_rate_limit_or_network(self):
        async def run():
            reserve = AsyncMock()
            db = ResearchDatabase(channel=SimpleNamespace(ai_enabled=True))
            config = SimpleNamespace(
                AI_ENABLED=True,
                GEMINI_API_KEY="gemini-test-key",
                GEMINI_MODEL="gemini-1.5-flash",
                AI_REQUESTS_PER_DAY=20,
            )
            with (
                patch.object(research, "settings", config),
                patch.object(research, "ensure_tenant_write_access", AsyncMock()),
                patch.object(
                    research,
                    "get_document",
                    AsyncMock(
                        return_value=SimpleNamespace(
                            id="doc-a", content_text="x" * 40001, current_version=1
                        )
                    ),
                ),
                patch.object(research, "reserve_request", reserve),
            ):
                with self.assertRaises(HTTPException) as caught:
                    await research.assist_document(
                        "doc-a", research.AssistInput(consent=True), self.user, db
                    )
            self.assertEqual(caught.exception.status_code, 422)
            reserve.assert_not_awaited()
            self.assertEqual(db.commits, 0)

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
