import asyncio
import unittest
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
import httpx

from app.api.v1.endpoints import controladoria
from app.models.workspace import WorkspaceTask
from app.schemas.controladoria import JudicialEventCreate
from app.services import controladoria_service as service
from app.services.controladoria_provider import (
    DataJudMonitoringProvider,
    EscavadorMonitoringProvider,
    JudicialProviderError,
)


class FakeDatabase:
    def __init__(self, scalar_results=()):
        self.scalar_results = list(scalar_results)
        self.added = []
        self.statements = []

    async def scalar(self, statement):
        self.statements.append(statement)
        return self.scalar_results.pop(0) if self.scalar_results else None

    def add(self, record):
        self.added.append(record)

    async def flush(self):
        for record in self.added:
            if isinstance(record, WorkspaceTask) and record.id is None:
                record.id = "task-approved"

    @asynccontextmanager
    async def begin_nested(self):
        yield self


class ControladoriaServiceTests(unittest.TestCase):
    user = SimpleNamespace(id="lawyer-a", tenant_id="tenant-a", role="lawyer")
    case = SimpleNamespace(id="case-a", responsible_user_id="lawyer-a", number="00000000000000000000")

    def test_datajud_tribunal_is_inferred_from_cnj_number_or_known_court(self):
        cnj = lambda justice, region: "0" * 13 + justice + region + "0" * 4
        self.assertEqual(service.infer_datajud_tribunal(cnj("8", "26")), "tjsp")
        self.assertEqual(service.infer_datajud_tribunal(cnj("4", "01")), "trf1")
        self.assertEqual(service.infer_datajud_tribunal(cnj("5", "02")), "trt2")
        self.assertEqual(service.infer_datajud_tribunal(None, "Tribunal de Justiça do Paraná - TJPR"), "tjpr")
        self.assertIsNone(service.infer_datajud_tribunal("invalido", "Tribunal desconhecido"))

    def test_event_deduplication_returns_existing_source_event(self):
        async def run():
            payload = JudicialEventCreate(
                case_id="case-a",
                source_kind="manual",
                source_event_id="source-event-9",
                source_url="https://court.example.test/events/9",
                title="Intimacao publicada",
                occurred_at=datetime(2026, 8, 29, 12, tzinfo=timezone.utc),
            )
            with patch.object(service, "get_case", AsyncMock(return_value=self.case)):
                created_db = FakeDatabase()
                created, was_created = await service.record_judicial_event(created_db, self.user, payload)
                duplicate_db = FakeDatabase((created,))
                duplicate, was_duplicate_created = await service.record_judicial_event(
                    duplicate_db, self.user, payload
                )
            return created_db, created, was_created, duplicate_db, duplicate, was_duplicate_created

        created_db, created, was_created, duplicate_db, duplicate, was_duplicate_created = asyncio.run(run())
        self.assertTrue(was_created)
        self.assertEqual(len(created_db.added), 1)
        self.assertEqual(len(created.dedupe_key), 64)
        self.assertFalse(was_duplicate_created)
        self.assertIs(duplicate, created)
        self.assertEqual(duplicate_db.added, [])

    def test_only_explicit_approval_creates_manually_reviewed_deadline_task(self):
        async def run():
            review = SimpleNamespace(
                id="review-a",
                case_id="case-a",
                title="Protocolar manifestacao",
                suggested_due_at=datetime(2026, 9, 3, 18, tzinfo=timezone.utc),
                suggested_basis="Prazo sugerido a partir da intimacao revisada.",
                assigned_user_id=None,
                status="suggested",
                task_id=None,
                review_note=None,
                reviewed_by_user_id=None,
                reviewed_at=None,
            )
            db = FakeDatabase()
            with (
                patch.object(service, "get_deadline_review", AsyncMock(return_value=review)),
                patch.object(service, "get_case", AsyncMock(return_value=self.case)),
            ):
                result, task = await service.approve_deadline_and_create_task(
                    db, self.user, "review-a", note="Conferido pelo responsavel."
                )
            return db, result, task

        db, review, task = asyncio.run(run())
        self.assertEqual(review.status, "approved")
        self.assertEqual(review.task_id, "task-approved")
        self.assertEqual(len(db.added), 1)
        self.assertIs(db.added[0], task)
        self.assertEqual(task.kind, "deadline")
        self.assertTrue(task.manually_reviewed)
        self.assertEqual(task.due_at, review.suggested_due_at)

    def test_event_lookup_is_tenant_and_case_acl_scoped(self):
        async def run():
            db = FakeDatabase()
            with patch.object(service, "get_case", AsyncMock()) as get_case:
                with self.assertRaises(HTTPException) as caught:
                    await service.get_event(db, self.user, "event-owned-by-another-case")
            return db, get_case, caught.exception

        db, get_case, error = asyncio.run(run())
        self.assertEqual(error.status_code, 404)
        self.assertEqual(get_case.await_count, 0)
        compiled = str(db.statements[0])
        self.assertIn("controladoria_judicial_events.tenant_id", compiled)
        self.assertIn("workspace_cases.restricted", compiled)

    def test_provider_rejects_untrusted_tribunal_without_a_network_call(self):
        async def run():
            calls = []

            def client_factory(**_kwargs):
                calls.append(True)
                raise AssertionError("network client must not be created")

            provider = DataJudMonitoringProvider("test-key", client_factory=client_factory)
            with self.assertRaises(JudicialProviderError):
                await provider.fetch(tribunal="metadata", process_number="00000000000000000000")
            return calls

        self.assertEqual(asyncio.run(run()), [])

    def test_escavador_provider_uses_fixed_host_and_normalizes_movement(self):
        async def run():
            def handler(request: httpx.Request):
                self.assertEqual(request.url.host, "api.escavador.com")
                self.assertEqual(request.headers["Authorization"], "Bearer test-token")
                return httpx.Response(200, json={"items": [{
                    "id": 91,
                    "data": "2026-09-01",
                    "tipo": "Movimentação",
                    "conteudo": "Juntada de petição",
                    "fonte": {"sigla": "TJSP", "grau_formatado": "Primeiro grau"},
                }]})

            transport = httpx.MockTransport(handler)
            provider = EscavadorMonitoringProvider(
                "test-token",
                client_factory=lambda **kwargs: httpx.AsyncClient(transport=transport, **kwargs),
            )
            return await provider.fetch(
                tribunal="tjsp", process_number="0000000-00.0000.0.00.0000"
            )

        events = asyncio.run(run())
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].source_event_id, "91")
        self.assertEqual(events[0].title, "Juntada de petição")
        self.assertEqual(events[0].source_metadata["court"], "TJSP")

    def test_deadline_payload_carries_persisted_event_evidence_for_approval(self):
        async def run():
            now = datetime(2026, 8, 29, 12, tzinfo=timezone.utc)
            review = SimpleNamespace(
                id="review-a", case_id="case-a", event_id="event-a", title="Protocolar manifestacao",
                suggested_due_at=now, suggested_basis="Conferencia humana pendente.", assigned_user_id=None,
                status="suggested", suggested_by_user_id="lawyer-a", reviewed_by_user_id=None,
                reviewed_at=None, review_note=None, task_id=None, created_at=now, updated_at=now,
            )
            event = SimpleNamespace(
                id="event-a", case_id="case-a", subscription_id="subscription-a", source_kind="datajud",
                source_event_id="movement-a", source_url="https://api-publica.datajud.cnj.jus.br/api_publica_tjsp/_search",
                title="Intimacao", source_content="Conteudo devolvido pela fonte.", source_metadata={"code": "123"},
                occurred_at=now, retrieved_at=now, triage_status="reviewed", triage_note=None,
                triaged_at=now, triaged_by_user_id="lawyer-a", created_at=now, updated_at=now,
            )
            with patch.object(controladoria, "get_event", AsyncMock(return_value=event)):
                return await controladoria.deadline_review_payload(None, self.user, review)

        payload = asyncio.run(run())
        self.assertEqual(payload.event.source_content, "Conteudo devolvido pela fonte.")
        self.assertEqual(payload.event.source_metadata, {"code": "123"})

    def test_manual_refresh_is_limited_per_subscription(self):
        class Redis:
            def __init__(self):
                self.keys = set()

            async def set(self, key, _value, *, ex, nx):
                self.arguments = (ex, nx)
                if key in self.keys:
                    return False
                self.keys.add(key)
                return True

        async def run():
            from app.core.redis_cache import cache_manager

            redis = Redis()
            with patch.object(cache_manager, "redis_client", redis):
                key = await controladoria.reserve_manual_refresh("tenant-a", "subscription-a")
                with self.assertRaises(HTTPException) as caught:
                    await controladoria.reserve_manual_refresh("tenant-a", "subscription-a")
            return redis, key, caught.exception

        redis, key, error = asyncio.run(run())
        self.assertEqual(redis.arguments, (300, True))
        self.assertEqual(key, "legaltech:controladoria:manual:tenant-a:subscription-a")
        self.assertEqual(error.status_code, 429)


if __name__ == "__main__":
    unittest.main()
