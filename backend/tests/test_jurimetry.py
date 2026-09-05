import asyncio
import json
import unittest
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import HTTPException
from pydantic import ValidationError

from app.api.v1.endpoints import jurimetria
from app.schemas.jurimetry import JurimetryAnalysisRequest, JurimetryFilters
from app.services import jurimetry


REAL_ASYNC_CLIENT = httpx.AsyncClient


def analysis_request(**changes):
    values = {
        "request_id": "0e8f9f5e-e361-49df-9f5a-8387f779d006",
        "tribunal": "tjsp",
        "filters": {
            "date_from": "2026-01-01",
            "date_to": "2026-03-31",
            "degree": "g1",
            "class_code": 1116,
        },
        "sample_limit": 50,
        "persist_snapshot": False,
    }
    values.update(changes)
    return JurimetryAnalysisRequest.model_validate(values)


def sample(hits=None):
    return jurimetry.DataJudSample(
        source_url="https://api-publica.datajud.cnj.jus.br/api_publica_tjsp/_search",
        queried_at=datetime(2026, 4, 1, 12, tzinfo=timezone.utc),
        hits=hits or [],
        total_matches=len(hits or []),
        total_relation="eq",
    )


class FakeDatabase:
    bind = None

    def __init__(self):
        self.added = []
        self.commits = 0
        self.rollbacks = 0
        self.existing = None
        self.statements = []

    async def scalar(self, statement):
        self.statements.append(statement)
        return self.existing

    def add(self, item):
        self.added.append(item)

    async def flush(self):
        return None

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1

    @asynccontextmanager
    async def begin_nested(self):
        yield self


class JurimetryTests(unittest.TestCase):
    user = SimpleNamespace(id="user-a", tenant_id="tenant-a", role="lawyer")

    def test_filters_are_bounded_and_tenant_cannot_be_supplied(self):
        with self.assertRaises(ValidationError):
            JurimetryFilters(date_from=date(2025, 1, 1), date_to=date(2026, 1, 2))
        with self.assertRaises(ValidationError):
            analysis_request(tribunal="metadata")
        with self.assertRaises(ValidationError):
            analysis_request(tenant_id="tenant-b")

    def test_provider_uses_fixed_datajud_contract_and_describes_only_returned_sample(self):
        requests = []

        def handler(request):
            requests.append(request)
            self.assertEqual(request.url.host, "api-publica.datajud.cnj.jus.br")
            self.assertEqual(request.headers["Authorization"], "APIKey test-key")
            payload = json.loads(request.content)
            self.assertEqual(payload["size"], 50)
            self.assertTrue(payload["track_total_hits"])
            self.assertNotIn("movimentos", payload["_source"])
            self.assertEqual(payload["sort"], [{"@timestamp": {"order": "desc"}}])
            self.assertIn({"match": {"classe.codigo": 1116}}, payload["query"]["bool"]["filter"])
            return httpx.Response(
                200,
                json={
                    "timed_out": False,
                    "_shards": {"failed": 0},
                    "hits": {
                        "total": {"value": 3, "relation": "eq"},
                        "hits": [
                            {"_source": {
                                "dataAjuizamento": "2026-01-10T10:00:00Z",
                                "grau": "G1",
                                "classe": {"codigo": 1116, "nome": "Execução Fiscal"},
                                "assuntos": [[{"codigo": 6017, "nome": "Dívida Ativa"}]],
                                "orgaoJulgador": {"codigo": 10, "nome": "Vara A"},
                                "dataHoraUltimaAtualizacao": "2026-03-01T10:00:00Z",
                                "@timestamp": "2026-03-02T10:00:00Z",
                            }},
                            {"_source": {
                                "dataAjuizamento": "2026-01-20T10:00:00Z",
                                "grau": "G1",
                                "classe": {"codigo": 1116, "nome": "Execução Fiscal"},
                                "assuntos": [{"codigo": 6017, "nome": "Dívida Ativa"}],
                                "orgaoJulgador": {"codigo": 20, "nome": "Vara B"},
                                "@timestamp": "2026-03-03T10:00:00Z",
                            }},
                        ],
                    },
                },
            )

        def client_factory(**kwargs):
            self.assertEqual(kwargs, {"timeout": 15, "follow_redirects": False})
            return REAL_ASYNC_CLIENT(transport=httpx.MockTransport(handler))

        request = analysis_request()
        provider = jurimetry.DataJudJurimetryProvider("test-key", client_factory=client_factory)
        provider_sample = asyncio.run(provider.query(request))
        result = jurimetry.analysis_response(request, provider_sample)

        self.assertEqual(len(requests), 1)
        self.assertEqual(result.sample_size, 2)
        self.assertEqual(result.total_matches, 3)
        self.assertEqual(result.metrics.cases_by_class[0].count, 2)
        self.assertEqual(result.metrics.subject_occurrences[0].count, 2)
        self.assertEqual(result.metrics.coverage.source_update, 2)
        self.assertEqual(result.source_updated_at, datetime(2026, 3, 3, 10, tzinfo=timezone.utc))
        keys = json.dumps(result.model_dump(mode="json"), ensure_ascii=False).lower()
        for forbidden in ("judge_name", "grant_rate", "average_days", "success_rate", "recommendation"):
            self.assertNotIn(forbidden, keys)
        self.assertIn("não estimam resultado", keys)

    def test_zero_results_contains_no_fabricated_metrics(self):
        result = jurimetry.analysis_response(analysis_request(), sample())
        self.assertEqual(result.sample_size, 0)
        self.assertEqual(result.total_matches, 0)
        self.assertEqual(result.metrics.filings_by_month, [])
        self.assertEqual(result.metrics.cases_by_degree, [])
        self.assertEqual(result.metrics.cases_by_class, [])
        self.assertEqual(result.metrics.subject_occurrences, [])
        self.assertEqual(result.metrics.cases_by_court_unit, [])
        self.assertTrue(all(value == 0 for value in result.metrics.coverage.model_dump().values()))

    def test_unavailable_provider_fails_before_rate_limit(self):
        async def run():
            reserve = AsyncMock()
            with (
                patch.object(jurimetria, "settings", SimpleNamespace(DATAJUD_ENABLED=False, DATAJUD_API_KEY=None)),
                patch.object(jurimetria, "ensure_tenant_write_access", AsyncMock()),
                patch.object(jurimetria, "_reserve_inflight_query", AsyncMock()),
                patch.object(jurimetria, "reserve_request", reserve),
            ):
                with self.assertRaises(HTTPException) as caught:
                    await jurimetria.analyze(analysis_request(), self.user, FakeDatabase())
            return caught.exception, reserve

        error, reserve = asyncio.run(run())
        self.assertEqual(error.status_code, 503)
        reserve.assert_not_awaited()

    def test_concurrent_request_id_is_rejected_before_calling_datajud(self):
        async def run():
            client = SimpleNamespace(set=AsyncMock(return_value=False))
            with patch.object(jurimetria.cache_manager, "redis_client", client):
                with self.assertRaises(HTTPException) as caught:
                    await jurimetria._reserve_inflight_query("tenant-a", "request-a")
            return client, caught.exception

        client, error = asyncio.run(run())
        self.assertEqual(error.status_code, 409)
        client.set.assert_awaited_once_with(
            "legaltech:jurimetry:inflight:tenant-a:request-a", "1", ex=120, nx=True
        )

    def test_authenticated_ids_are_captured_before_transaction_release(self):
        async def run():
            db = FakeDatabase()

            class ExpiringUser:
                role = "lawyer"

                @property
                def tenant_id(self):
                    if db.rollbacks:
                        raise AssertionError("tenant_id was read after rollback")
                    return "tenant-a"

                @property
                def id(self):
                    if db.rollbacks:
                        raise AssertionError("user id was read after rollback")
                    return "user-a"

            with (
                patch.object(jurimetria, "settings", SimpleNamespace(DATAJUD_ENABLED=True, DATAJUD_API_KEY="test-key")),
                patch.object(jurimetria, "ensure_tenant_write_access", AsyncMock()),
                patch.object(jurimetria, "_reserve_inflight_query", AsyncMock()),
                patch.object(jurimetria, "reserve_request", AsyncMock()),
                patch.object(jurimetry.DataJudJurimetryProvider, "query", AsyncMock(return_value=sample())),
                patch.object(jurimetria, "_set_tenant_context", AsyncMock()),
                patch.object(jurimetria.AuditService, "log_action", AsyncMock()),
            ):
                return await jurimetria.analyze(analysis_request(), ExpiringUser(), db)

        result = asyncio.run(run())
        self.assertEqual(result.sample_size, 0)

    def test_persisted_snapshot_is_tenant_scoped_audited_and_idempotent(self):
        async def run():
            db = FakeDatabase()
            request = analysis_request(persist_snapshot=True)
            async def provider_result(_request):
                self.assertEqual(db.rollbacks, 1, "the database transaction must be closed before DataJud")
                return sample([{
                    "dataAjuizamento": "2026-02-01T10:00:00Z",
                    "grau": "G1",
                    "@timestamp": "2026-03-01T10:00:00Z",
                }])
            provider_query = AsyncMock(side_effect=provider_result)
            audit = AsyncMock()
            with (
                patch.object(jurimetria, "settings", SimpleNamespace(DATAJUD_ENABLED=True, DATAJUD_API_KEY="test-key")),
                patch.object(jurimetria, "ensure_tenant_write_access", AsyncMock()),
                patch.object(jurimetria, "_reserve_inflight_query", AsyncMock()),
                patch.object(jurimetria, "reserve_request", AsyncMock()),
                patch.object(jurimetry.DataJudJurimetryProvider, "query", provider_query),
                patch.object(jurimetria, "_set_tenant_context", AsyncMock()),
                patch.object(jurimetria.AuditService, "log_action", audit),
            ):
                first = await jurimetria.analyze(request, self.user, db)
                db.existing = db.added[0]
                replay = await jurimetria.analyze(request, self.user, db)
                with self.assertRaises(HTTPException) as caught:
                    await jurimetria.analyze(
                        analysis_request(
                            persist_snapshot=True,
                            filters={"date_from": "2026-02-01", "date_to": "2026-03-31"},
                        ),
                        self.user,
                        db,
                    )
            return db, first, replay, provider_query, audit, caught.exception

        db, first, replay, provider_query, audit, conflict = asyncio.run(run())
        snapshot = db.added[0]
        self.assertEqual(snapshot.tenant_id, "tenant-a")
        self.assertEqual(snapshot.created_by_user_id, "user-a")
        self.assertTrue(first.persisted)
        self.assertEqual(replay.snapshot_id, first.snapshot_id)
        self.assertEqual(provider_query.await_count, 1)
        self.assertEqual(audit.await_count, 1)
        self.assertEqual(db.commits, 1)
        self.assertEqual(conflict.status_code, 409)

    def test_snapshot_lookup_always_filters_by_authenticated_tenant(self):
        async def run():
            db = FakeDatabase()
            with self.assertRaises(HTTPException) as caught:
                await jurimetria.get_snapshot("snapshot-b", self.user, db)
            return db, caught.exception

        db, error = asyncio.run(run())
        self.assertEqual(error.status_code, 404)
        statement = db.statements[0].compile()
        self.assertIn("jurimetry_snapshots.tenant_id", str(statement))
        self.assertIn("tenant-a", statement.params.values())
        self.assertIn("snapshot-b", statement.params.values())


if __name__ == "__main__":
    unittest.main()
