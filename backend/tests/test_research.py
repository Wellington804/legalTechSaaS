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
from app.services import legal_ai


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

    def test_contextual_assistant_reports_retryable_failure_without_technical_details(self):
        async def run():
            db = ResearchDatabase()
            db.execute = AsyncMock(return_value=SimpleNamespace(
                scalars=lambda: SimpleNamespace(all=lambda: []),
            ))
            audit = AsyncMock()
            with (
                patch.object(research, "ensure_tenant_write_access", AsyncMock()),
                patch.object(research, "ai_available", return_value=True),
                patch.object(research, "provider_name", return_value="openrouter"),
                patch.object(research, "model_name", return_value="configured-model"),
                patch.object(research, "reserve_request", AsyncMock()),
                patch.object(research, "generate_text", AsyncMock(side_effect=research.AIProviderError("provider unavailable"))),
                patch.object(research.AuditService, "log_action", audit),
            ):
                with self.assertRaises(HTTPException) as caught:
                    await research._contextual_assistant(
                        research.AssistantInput(question="Organize as providências pendentes", consent=True),
                        self.user,
                        db,
                    )
            self.assertEqual(caught.exception.status_code, 503)
            self.assertEqual(
                caught.exception.detail,
                "O assistente está temporariamente indisponível. Tente novamente em instantes.",
            )
            self.assertNotIn("provedor", caught.exception.detail.lower())
            self.assertEqual(db.commits, 1, "a solicitação é auditada, mas nenhuma conversa é salva")
            self.assertEqual(db.added, [])
            audit.assert_awaited_once()

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
                            {"content": {"parts": [{"text": "[D1-N1] " + "x" * 16000}]}}
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

    def test_evidence_matrix_is_source_bound_audited_and_never_saved(self):
        async def run():
            case = SimpleNamespace(id="case-a", title="Cobrança", number=self.valid_cnj, court="TJSP", status="open")
            document = SimpleNamespace(
                id="doc-a", case_id="case-a", title="Contrato", current_version=2,
                content_text="O contrato foi assinado.\n\nA parcela de agosto não foi paga.",
            )
            source_id = legal_ai.build_evidence_bundle([document], "Analise a parcela não paga")["sources"][0].id
            response = legal_ai.EvidenceMatrix(
                facts=[legal_ai.MatrixItem(id="F1", statement="A parcela não foi paga.", status="supported", source_ids=[source_id], review_note="Conferir.", human_review_required=True)],
                evidence=[], legal_bases=[],
                requests=[legal_ai.MatrixItem(id="P1", statement="Avaliar cobrança.", status="supported", source_ids=[source_id], review_note="Definir pedido.", human_review_required=True)],
                gaps=["Fonte jurídica oficial."], conflicts=[], limitations=["Análise documental."], human_review_required=True,
            )
            db, audit = ResearchDatabase(), AsyncMock()
            with (
                patch.object(research, "ensure_tenant_write_access", AsyncMock()),
                patch.object(research, "get_case", AsyncMock(return_value=case)),
                patch.object(research, "get_document", AsyncMock(return_value=document)),
                patch.object(research, "ai_available", return_value=True),
                patch.object(research, "reserve_request", AsyncMock()),
                patch.object(research, "generate_text", AsyncMock(return_value=response.model_dump_json())) as generate,
                patch.object(research, "_set_tenant_context", AsyncMock()),
                patch.object(research.AuditService, "log_action", audit),
            ):
                result = await research.create_evidence_matrix(
                    "case-a", research.EvidenceMatrixInput(
                        document_ids=["doc-a"], instructions="Analise a parcela não paga", consent=True,
                    ), self.user, db,
                )
            return result, db, audit, generate

        result, db, audit, generate = asyncio.run(run())
        self.assertFalse(result["saved"])
        self.assertTrue(result["review_required"])
        self.assertEqual(result["matrix"]["facts"][0]["source_ids"], [result["sources"][0]["id"]])
        self.assertEqual(db.added, [])
        self.assertEqual(db.commits, 2)
        self.assertEqual(audit.await_count, 2)
        self.assertEqual(generate.await_args.kwargs["purpose"], "legal")

    def test_guided_draft_rejects_stale_snapshot_before_provider_call(self):
        async def run():
            case = SimpleNamespace(id="case-a", title="Cobrança", number=self.valid_cnj, court="TJSP", status="open")
            document = SimpleNamespace(id="doc-a", case_id="case-a", title="Contrato", current_version=2, content_text="Texto atual.")
            matrix = legal_ai.EvidenceMatrix(
                facts=[legal_ai.MatrixItem(id="F1", statement="Fato.", status="supported", source_ids=["D1-N1"], review_note="Conferir.", human_review_required=True)],
                evidence=[], legal_bases=[],
                requests=[legal_ai.MatrixItem(id="P1", statement="Pedido.", status="supported", source_ids=["D1-N1"], review_note="Conferir.", human_review_required=True)],
                gaps=[], conflicts=[], limitations=["Revisar."], human_review_required=True,
            )
            provider = AsyncMock()
            with (
                patch.object(research, "ensure_tenant_write_access", AsyncMock()),
                patch.object(research, "get_case", AsyncMock(return_value=case)),
                patch.object(research, "get_document", AsyncMock(return_value=document)),
                patch.object(research, "ai_available", return_value=True),
                patch.object(research, "generate_text", provider),
            ):
                with self.assertRaises(HTTPException) as caught:
                    await research.create_guided_draft(
                        "case-a", research.GuidedDraftInput(
                            document_ids=["doc-a"],
                            snapshots=[legal_ai.DocumentSnapshot(document_id="doc-a", version=1, sha256="0" * 64)],
                            source_query="Analise o documento", matrix=matrix, approved_item_ids=["F1", "P1"],
                            piece_type="initial_petition", addressing="Juízo competente", instructions="Prepare a minuta", consent=True,
                        ), self.user, ResearchDatabase(),
                    )
            return caught.exception, provider

        error, provider = asyncio.run(run())
        self.assertEqual(error.status_code, 409)
        provider.assert_not_awaited()

    def test_guided_draft_runs_separate_verifier_and_returns_unsaved_draft(self):
        async def run():
            case = SimpleNamespace(id="case-a", title="Cobrança", number=self.valid_cnj, court="TJSP", status="open")
            document = SimpleNamespace(
                id="doc-a", case_id="case-a", title="Contrato", current_version=2,
                content_text="A parcela de agosto não foi paga.",
            )
            bundle = legal_ai.build_evidence_bundle([document], "Analise o inadimplemento")
            source_id = bundle["sources"][0].id
            matrix = legal_ai.EvidenceMatrix(
                facts=[legal_ai.MatrixItem(id="F1", statement="A parcela não foi paga.", status="supported", source_ids=[source_id], review_note="Conferir.", human_review_required=True)],
                evidence=[], legal_bases=[],
                requests=[legal_ai.MatrixItem(id="P1", statement="Avaliar cobrança.", status="supported", source_ids=[source_id], review_note="Definir pedido.", human_review_required=True)],
                gaps=["Fundamento oficial."], conflicts=[], limitations=["Revisar."], human_review_required=True,
            )
            draft = legal_ai.GeneratedDraft(
                title="Minuta de cobrança",
                sections=[legal_ai.DraftSection(heading="Dos fatos", body="A parcela não foi paga.", status="supported", source_ids=[source_id])],
                missing_information=["Fundamento jurídico oficial."], human_review_required=True,
            )
            verification = legal_ai.VerificationResult(
                verdict="needs_review", issues=[], checked_source_ids=[source_id],
                summary="Ainda exige revisão profissional.", human_review_required=True,
            )
            generate = AsyncMock(side_effect=[draft.model_dump_json(), verification.model_dump_json()])
            db, audit = ResearchDatabase(), AsyncMock()
            with (
                patch.object(research, "ensure_tenant_write_access", AsyncMock()),
                patch.object(research, "get_case", AsyncMock(return_value=case)),
                patch.object(research, "get_document", AsyncMock(return_value=document)),
                patch.object(research, "ai_available", return_value=True),
                patch.object(research, "reserve_request", AsyncMock()),
                patch.object(research, "generate_text", generate),
                patch.object(research, "_set_tenant_context", AsyncMock()),
                patch.object(research, "model_name", side_effect=lambda _settings, purpose="general": f"model-{purpose}"),
                patch.object(research.AuditService, "log_action", audit),
            ):
                result = await research.create_guided_draft(
                    "case-a", research.GuidedDraftInput(
                        document_ids=["doc-a"], snapshots=bundle["snapshots"], source_query="Analise o inadimplemento",
                        matrix=matrix, approved_item_ids=["F1", "P1"], piece_type="initial_petition",
                        addressing="Juízo competente", instructions="Prepare uma minuta objetiva", consent=True,
                    ), self.user, db,
                )
            return result, db, audit, generate

        result, db, audit, generate = asyncio.run(run())
        self.assertFalse(result["saved"])
        self.assertTrue(result["model_independent"])
        self.assertIn("RASCUNHO GERADO COM IA", result["content_markdown"])
        self.assertEqual([entry.kwargs["purpose"] for entry in generate.await_args_list], ["legal", "deep"])
        self.assertEqual(db.added, [])
        self.assertEqual(db.commits, 2)
        self.assertEqual(audit.await_count, 2)


if __name__ == "__main__":
    unittest.main()
