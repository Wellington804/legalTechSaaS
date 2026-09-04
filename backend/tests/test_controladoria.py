import asyncio
import json
import unittest
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
import httpx

from app.api.v1.endpoints import controladoria
from app.models.workspace import WorkspaceCase, WorkspaceTask
from app.schemas.controladoria import JudicialEventCreate, MonitoringSubscriptionFromNumberCreate
from app.services import controladoria_service as service
from app.services.controladoria_provider import (
    CredentialedCommunicationProvider,
    DataJudMonitoringProvider,
    DjenMonitoringProvider,
    EscavadorMonitoringProvider,
    JudicialProviderError,
    JudicialProviderRateLimited,
    monitoring_provider,
    parse_escavador_callback,
    parse_escavador_movement,
    provider_configuration_status,
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

    def test_monitoring_from_number_creates_one_canonical_case_for_current_lawyer(self):
        class Database(FakeDatabase):
            async def flush(self):
                await super().flush()
                for record in self.added:
                    if isinstance(record, WorkspaceCase) and record.id is None:
                        record.id = "case-new"

        async def run():
            db = Database((None,))
            payload = MonitoringSubscriptionFromNumberCreate(
                client_id="client-a",
                process_number="0000000-00.0000.8.26.0000",
                source_kind="djen",
            )
            subscription = SimpleNamespace(id="subscription-new")
            with (
                patch.object(service, "get_client", AsyncMock()),
                patch.object(service, "lock_workspace_tenant", AsyncMock()),
                patch.object(
                    service,
                    "create_monitoring_subscription",
                    AsyncMock(return_value=(subscription, True)),
                ) as create_subscription,
            ):
                result = await service.create_monitoring_subscription_from_number(
                    db, self.user, payload, source_kind="djen"
                )
            return db, result, create_subscription

        db, (case, case_created, subscription, subscription_created), create_subscription = asyncio.run(run())
        self.assertTrue(case_created)
        self.assertTrue(subscription_created)
        self.assertEqual(case.number, "0000000-00.0000.8.26.0000")
        self.assertEqual(case.responsible_user_id, self.user.id)
        self.assertEqual(case.client_id, "client-a")
        self.assertEqual(case.court, "TJSP")
        self.assertEqual(subscription.id, "subscription-new")
        self.assertEqual(len(db.added), 1)
        self.assertEqual(create_subscription.await_count, 1)

    def test_monitoring_from_number_reuses_an_accessible_case_instead_of_duplicating_it(self):
        existing_case = SimpleNamespace(
            id="case-existing",
            client_id="client-a",
            responsible_user_id="lawyer-a",
            archived_at=None,
            status="open",
        )

        async def run():
            db = FakeDatabase((existing_case,))
            payload = MonitoringSubscriptionFromNumberCreate(
                client_id="client-a",
                process_number="00000000000008260000",
                title="Titulo que nao deve substituir o cadastro",
            )
            subscription = SimpleNamespace(id="subscription-existing")
            with (
                patch.object(service, "get_client", AsyncMock()),
                patch.object(service, "lock_workspace_tenant", AsyncMock()),
                patch.object(service, "get_case", AsyncMock(return_value=existing_case)),
                patch.object(
                    service,
                    "create_monitoring_subscription",
                    AsyncMock(return_value=(subscription, False)),
                ),
            ):
                result = await service.create_monitoring_subscription_from_number(
                    db, self.user, payload, source_kind="djen"
                )
            return db, result

        db, (case, case_created, subscription, subscription_created) = asyncio.run(run())
        self.assertIs(case, existing_case)
        self.assertFalse(case_created)
        self.assertFalse(subscription_created)
        self.assertEqual(subscription.id, "subscription-existing")
        self.assertEqual(db.added, [])

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

    def test_user_cannot_spoof_an_automatic_judicial_source(self):
        payload = JudicialEventCreate(
            case_id="case-a",
            subscription_id="subscription-a",
            source_kind="djen",
            source_event_id="official-looking-id",
            source_url="https://comunicaapi.pje.jus.br/api/v1/comunicacao",
            title="Intimacao inventada",
        )

        async def run():
            with patch.object(service, "get_case", AsyncMock(return_value=self.case)):
                await service.record_judicial_event(FakeDatabase(), self.user, payload)

        with self.assertRaises(HTTPException) as caught:
            asyncio.run(run())
        self.assertEqual(caught.exception.status_code, 422)

    def test_only_distinct_second_approval_creates_manually_reviewed_deadline_task(self):
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
                approval_policy_version=2,
                first_approved_by_user_id=None,
                first_approved_at=None,
                first_approval_note=None,
                second_approved_by_user_id=None,
                second_approved_at=None,
                second_approval_note=None,
                first_approval_calculation_sha256=None,
                second_approval_calculation_sha256=None,
                source_stale_at=None,
                source_stale_event_id=None,
                rule_id="rule-a",
                rule_version=1,
                calculation_revision=1,
                calculation={"due_date": "2026-09-03"},
            )
            db = FakeDatabase()
            with (
                patch.object(service, "get_deadline_review", AsyncMock(return_value=review)),
                patch.object(service, "get_case", AsyncMock(return_value=self.case)),
            ):
                first_result, first_task = await service.approve_deadline_and_create_task(
                    db, self.user, "review-a", note="Conferido pelo responsavel.",
                    expected_calculation_revision=1,
                )
                second_user = SimpleNamespace(id="partner-b", tenant_id="tenant-a", role="partner")
                result, task = await service.approve_deadline_and_create_task(
                    db, second_user, "review-a", note="Segunda conferencia independente.",
                    expected_calculation_revision=1,
                )
            return db, first_result, first_task, result, task

        db, first_review, first_task, review, task = asyncio.run(run())
        self.assertIsNone(first_task)
        self.assertEqual(first_review.first_approved_by_user_id, "lawyer-a")
        self.assertEqual(review.status, "approved")
        self.assertEqual(review.second_approved_by_user_id, "partner-b")
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
        self.assertEqual(events[0].source_content, "Juntada de petição")
        self.assertEqual(events[0].source_metadata["court"], "TJSP")
        self.assertEqual(events[0].source_metadata["ingestion_method"], "poll")
        self.assertEqual(len(events[0].source_metadata["provider_payload_sha256"]), 64)

    def test_escavador_monitor_is_created_with_bounded_fixed_contract(self):
        async def run():
            def handler(request: httpx.Request):
                self.assertEqual(request.url, httpx.URL("https://api.escavador.com/api/v2/monitoramentos/processos"))
                self.assertEqual(request.headers["Authorization"], "Bearer test-token")
                self.assertEqual(json.loads(request.content), {
                    "numero": "0000000-00.0000.0.00.0000",
                    "tribunal": "TJSP",
                    "frequencia": "DIARIA",
                    "documentos_publicos": False,
                })
                return httpx.Response(201, json={"id": 1567024})

            transport = httpx.MockTransport(handler)
            provider = EscavadorMonitoringProvider(
                "test-token",
                client_factory=lambda **kwargs: httpx.AsyncClient(transport=transport, **kwargs),
            )
            return await provider.ensure_monitor(
                tribunal="tjsp", process_number="00000000000000000000"
            )

        self.assertEqual(asyncio.run(run()), "1567024")

    def test_escavador_poll_and_callback_share_event_identity_for_deduplication(self):
        movement = {
            "id": 23895909833,
            "data": "2026-09-01",
            "tipo": "PUBLICACAO",
            "conteudo": "Intimação publicada",
            "fonte": {"sigla": "TJSP", "grau_formatado": "Primeiro grau"},
        }
        callback = parse_escavador_callback({
            "event": "nova_movimentacao",
            "monitoramento": {"id": 1567024, "numero": "0000000-00.0000.0.00.0000"},
            "movimentacao": movement,
            "uuid": "callback-uuid-a",
        })
        polled = parse_escavador_movement(
            movement,
            process_number="00000000000000000000",
            retrieved_at=datetime(2026, 9, 1, 12, tzinfo=timezone.utc),
            ingestion_method="poll",
        )
        callback_payload = JudicialEventCreate(
            case_id="case-a", subscription_id="subscription-a", source_kind="escavador",
            source_event_id=callback.event.source_event_id, source_url=callback.event.source_url,
            title=callback.event.title, source_content=callback.event.source_content,
            source_metadata=callback.event.source_metadata, occurred_at=callback.event.occurred_at,
            retrieved_at=callback.event.retrieved_at,
        )
        polled_payload = callback_payload.model_copy(update={
            "source_metadata": polled.source_metadata,
            "retrieved_at": polled.retrieved_at,
        })
        self.assertEqual(callback.provider_subscription_id, "1567024")
        self.assertEqual(callback.event.source_metadata["provider_subscription_id"], "1567024")
        self.assertEqual(callback.event.source_metadata["suggested_action"], "Revisar publicação e avaliar providência ou prazo")
        self.assertEqual(
            service.event_dedupe_key("case-a", callback_payload),
            service.event_dedupe_key("case-a", polled_payload),
        )

    def test_djen_public_provider_uses_official_contract_cursor_and_stable_publication_identity(self):
        requests = []

        async def run():
            def handler(request: httpx.Request):
                requests.append(request)
                return httpx.Response(200, json={"items": [{
                    "id": 99,
                    "numeroComunicacao": 2026000123,
                    "numero_processo": "0000000-00.0000.0.00.0000",
                    "data_disponibilizacao": "2026-09-04",
                    "siglaTribunal": "TJSP",
                    "tipoComunicacao": "Intimacao",
                    "texto": "Intimacao para manifestacao.",
                    "link": "https://comunica.pje.jus.br/consulta/2026000123",
                }]})

            transport = httpx.MockTransport(handler)
            provider = DjenMonitoringProvider(
                client_factory=lambda **kwargs: httpx.AsyncClient(transport=transport, **kwargs)
            )
            return await provider.fetch_page(
                tribunal="tjsp", process_number="00000000000000000000", cursor=None
            )

        first = asyncio.run(run())
        second = asyncio.run(run())
        self.assertEqual(requests[0].url.host, "comunicaapi.pje.jus.br")
        self.assertEqual(requests[0].url.params["numeroProcesso"], "00000000000000000000")
        self.assertEqual(requests[0].url.params["itensPorPagina"], "100")
        self.assertEqual(first.next_cursor, None)
        self.assertEqual(first.events[0].source_event_id, "2026000123")
        self.assertEqual(first.events[0].source_event_id, second.events[0].source_event_id)
        self.assertEqual(first.events[0].source_metadata["provider_source"], "djen")
        self.assertEqual(len(first.events[0].source_metadata["provider_payload_sha256"]), 64)
        first_payload = JudicialEventCreate(
            case_id="case-a", subscription_id="subscription-a", source_kind="djen",
            source_event_id=first.events[0].source_event_id, source_url=first.events[0].source_url,
            title=first.events[0].title, source_content=first.events[0].source_content,
            source_metadata=first.events[0].source_metadata, occurred_at=first.events[0].occurred_at,
            retrieved_at=first.events[0].retrieved_at,
        )
        corrected_payload = first_payload.model_copy(update={"title": "Texto corrigido pelo DJEN"})
        self.assertNotEqual(
            service.event_dedupe_key("case-a", first_payload),
            service.event_dedupe_key("case-a", corrected_payload),
        )

    def test_automatic_source_revision_is_preserved_and_marks_deadline_stale(self):
        previous = SimpleNamespace(
            id="event-old", created_at=datetime(2026, 9, 3, tzinfo=timezone.utc)
        )
        review = SimpleNamespace(
            id="review-a", task_id=None, source_stale_at=None, source_stale_event_id=None
        )

        class ScalarRows:
            def scalars(self):
                return self

            def all(self):
                return [review]

        class Database(FakeDatabase):
            def __init__(self):
                super().__init__((None, previous))

            async def execute(self, _statement):
                return ScalarRows()

            async def flush(self):
                await super().flush()
                for record in self.added:
                    if record.__class__.__name__ == "ControladoriaJudicialEvent" and record.id is None:
                        record.id = "event-new"

        payload = JudicialEventCreate(
            case_id="case-a",
            subscription_id="subscription-a",
            source_kind="djen",
            source_event_id="publication-a",
            source_url="https://comunica.pje.jus.br/publication-a",
            title="Intimacao corrigida",
            source_content="Novo conteudo oficial.",
            source_metadata={"provider_payload_sha256": "b" * 64},
        )

        async def run():
            db = Database()
            subscription = SimpleNamespace(case_id="case-a", source_kind="djen", status="active")
            with (
                patch.object(service, "get_case", AsyncMock(return_value=self.case)),
                patch.object(service, "get_subscription", AsyncMock(return_value=subscription)),
            ):
                event, created = await service.record_judicial_event(
                    db, self.user, payload, trusted_provider=True
                )
            return event, created

        event, created = asyncio.run(run())
        self.assertTrue(created)
        self.assertEqual(event.source_metadata["supersedes_event_id"], "event-old")
        self.assertEqual(review.source_stale_event_id, "event-new")
        self.assertIsNotNone(review.source_stale_at)

    def test_djen_rejects_a_response_without_the_bound_process_number(self):
        async def run():
            transport = httpx.MockTransport(
                lambda _request: httpx.Response(
                    200,
                    json={"items": [{"numeroComunicacao": 1, "texto": "Intimacao"}]},
                )
            )
            provider = DjenMonitoringProvider(
                client_factory=lambda **kwargs: httpx.AsyncClient(transport=transport, **kwargs)
            )
            return await provider.fetch_page(
                tribunal="tjsp", process_number="00000000000000000000"
            )

        with self.assertRaises(JudicialProviderError):
            asyncio.run(run())

    def test_djen_rate_limit_defers_without_rapid_retry(self):
        calls = 0

        async def run():
            nonlocal calls

            def handler(_request: httpx.Request):
                nonlocal calls
                calls += 1
                return httpx.Response(429)

            provider = DjenMonitoringProvider(
                client_factory=lambda **kwargs: httpx.AsyncClient(
                    transport=httpx.MockTransport(handler), **kwargs
                )
            )
            from app.services.controladoria_tasks import _fetch_with_backoff

            await _fetch_with_backoff(
                provider,
                tribunal="tjsp",
                process_number="00000000000000000000",
                cursor=None,
            )

        with self.assertRaises(JudicialProviderRateLimited):
            asyncio.run(run())
        self.assertEqual(calls, 1)

    def test_credentialed_sources_fail_closed_until_endpoint_and_token_exist(self):
        config = SimpleNamespace()
        with self.assertRaises(JudicialProviderError):
            monitoring_provider("domicilio", config, tribunal="tjsp")
        statuses = {item["source_kind"]: item for item in provider_configuration_status(config)}
        self.assertTrue(statuses["djen"]["configured"])
        self.assertFalse(statuses["domicilio"]["configured"])
        self.assertTrue(statuses["domicilio"]["homologation_required"])
        credentials_without_homologation = SimpleNamespace(
            DOMICILIO_JUDICIAL_API_URL="https://domicilio.example/api/v1/comunicacoes",
            DOMICILIO_JUDICIAL_API_TOKEN="secret",
            DOMICILIO_JUDICIAL_HOMOLOGATED=False,
        )
        with self.assertRaises(JudicialProviderError):
            monitoring_provider("domicilio", credentials_without_homologation, tribunal="tjsp")

    def test_contracted_tribunal_adapter_uses_configured_https_endpoint_without_redirects(self):
        async def run():
            def handler(request: httpx.Request):
                self.assertEqual(request.url.host, "api.tjsp.example")
                self.assertEqual(request.headers["X-API-Key"], "contract-token")
                return httpx.Response(200, json={"items": [], "next_cursor": "cursor-2"})

            transport = httpx.MockTransport(handler)
            provider = CredentialedCommunicationProvider(
                source_kind="tribunal_api",
                endpoint="https://api.tjsp.example/comunicacoes",
                token="contract-token",
                token_header="X-API-Key",
                client_factory=lambda **kwargs: httpx.AsyncClient(transport=transport, **kwargs),
            )
            return await provider.fetch_page(
                tribunal="tjsp", process_number="00000000000000000000"
            )

        page = asyncio.run(run())
        self.assertEqual(page.events, [])
        self.assertEqual(page.next_cursor, "cursor-2")

    def test_deadline_payload_carries_persisted_event_evidence_for_approval(self):
        async def run():
            now = datetime(2026, 8, 29, 12, tzinfo=timezone.utc)
            review = SimpleNamespace(
                id="review-a", case_id="case-a", event_id="event-a", title="Protocolar manifestacao",
                suggested_due_at=now, suggested_basis="Conferencia humana pendente.", assigned_user_id=None,
                status="suggested", suggested_by_user_id="lawyer-a", reviewed_by_user_id=None,
                reviewed_at=None, review_note=None, task_id=None, created_at=now, updated_at=now,
                rule_id=None, rule_version=None, calculation=None, calculation_revision=1,
                approval_policy_version=2, first_approved_by_user_id=None, first_approved_at=None,
                first_approval_note=None, second_approved_by_user_id=None, second_approved_at=None,
                second_approval_note=None, first_approval_calculation_sha256=None,
                second_approval_calculation_sha256=None, source_stale_at=None,
                source_stale_event_id=None,
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
