"""Bounded DataJud queries and local descriptive aggregation."""

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from typing import Any, Callable, Iterable

import httpx

from app.models.jurimetry import JurimetrySnapshot
from app.schemas.controladoria import SUPPORTED_DATAJUD_TRIBUNALS
from app.schemas.jurimetry import (
    DescriptiveMetrics,
    JurimetryAnalysisRequest,
    JurimetryAnalysisResponse,
    MetricBucket,
    MetricCoverage,
)
from app.services.controladoria_provider import (
    DATAJUD_HOST,
    MAX_RESPONSE_BYTES,
    JudicialProviderError,
    JudicialProviderRateLimited,
)


SOURCE_NAME = "DataJud — API Pública do CNJ"
SOURCE_DOCUMENTATION_URL = "https://datajud-wiki.cnj.jus.br/api-publica/"
MAX_BUCKETS = 10
MAX_SUBJECT_NODES_PER_CASE = 1_000


@dataclass(frozen=True)
class DataJudSample:
    source_url: str
    queried_at: datetime
    hits: list[dict[str, Any]]
    total_matches: int | None
    total_relation: str


def request_fingerprint(request: JurimetryAnalysisRequest) -> str:
    payload = request.model_dump(mode="json", exclude={"persist_snapshot"})
    payload.pop("request_id", None)
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def datajud_query(request: JurimetryAnalysisRequest) -> dict[str, Any]:
    filters: list[dict[str, Any]] = [
        {
            "range": {
                "dataAjuizamento": {
                    "gte": datetime.combine(request.filters.date_from, time.min, tzinfo=timezone.utc).isoformat(),
                    "lte": datetime.combine(request.filters.date_to, time.max, tzinfo=timezone.utc).isoformat(),
                }
            }
        }
    ]
    for field, value in (
        ("grau", request.filters.degree),
        ("classe.codigo", request.filters.class_code),
        ("assuntos.codigo", request.filters.subject_code),
        ("orgaoJulgador.codigo", request.filters.court_unit_code),
    ):
        if value is not None:
            filters.append({"match": {field: value}})
    return {
        "size": request.sample_limit,
        "track_total_hits": True,
        "_source": [
            "dataAjuizamento",
            "grau",
            "classe",
            "assuntos",
            "orgaoJulgador",
            "dataHoraUltimaAtualizacao",
            "@timestamp",
        ],
        "query": {"bool": {"filter": filters}},
        "sort": [{"@timestamp": {"order": "desc"}}],
    }


class DataJudJurimetryProvider:
    """Fixed-host DataJud client with injectable transport for isolated tests."""

    def __init__(self, api_key: str, client_factory: Callable[..., httpx.AsyncClient] = httpx.AsyncClient):
        if not api_key:
            raise ValueError("api_key DataJud é obrigatória")
        self._api_key = api_key
        self._client_factory = client_factory

    async def query(self, request: JurimetryAnalysisRequest) -> DataJudSample:
        if request.tribunal not in SUPPORTED_DATAJUD_TRIBUNALS:
            raise JudicialProviderError("tribunal DataJud inválido")
        endpoint = f"https://{DATAJUD_HOST}/api_publica_{request.tribunal}/_search"
        try:
            async with self._client_factory(timeout=15, follow_redirects=False) as client:
                response = await client.post(
                    endpoint,
                    headers={"Authorization": f"APIKey {self._api_key}"},
                    json=datajud_query(request),
                )
            if response.status_code == 429:
                raise JudicialProviderRateLimited("limite temporário da fonte judicial")
            if not response.is_success or len(response.content) > MAX_RESPONSE_BYTES:
                raise JudicialProviderError("resposta DataJud inválida")
            payload = response.json()
            if payload.get("timed_out") is True or int(payload.get("_shards", {}).get("failed", 0)) > 0:
                raise JudicialProviderError("consulta DataJud parcial ou expirada")
            hits_node = payload["hits"]
            raw_hits = hits_node["hits"]
            total_matches, total_relation = _total(hits_node.get("total"))
        except JudicialProviderError:
            raise
        except (httpx.HTTPError, AttributeError, KeyError, TypeError, ValueError) as exc:
            raise JudicialProviderError("fonte DataJud indisponível ou resposta inválida") from exc
        if not isinstance(raw_hits, list) or len(raw_hits) > request.sample_limit:
            raise JudicialProviderError("volume de resultados DataJud inválido")
        if total_matches is not None and total_matches < len(raw_hits):
            raise JudicialProviderError("total DataJud incompatível com a amostra")
        hits: list[dict[str, Any]] = []
        for hit in raw_hits:
            source = hit.get("_source") if isinstance(hit, dict) else None
            if not isinstance(source, dict):
                raise JudicialProviderError("registro DataJud inválido")
            hits.append(source)
        return DataJudSample(endpoint, datetime.now(timezone.utc), hits, total_matches, total_relation)


def _total(value: Any) -> tuple[int | None, str]:
    if isinstance(value, int) and value >= 0:
        return value, "eq"
    if not isinstance(value, dict):
        return None, "unknown"
    total = value.get("value")
    relation = value.get("relation")
    if not isinstance(total, int) or total < 0 or relation not in {"eq", "gte"}:
        return None, "unknown"
    return total, relation


def _datetime(value: Any) -> datetime | None:
    try:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            seconds = value / 1000 if value > 10_000_000_000 else value
            return datetime.fromtimestamp(seconds, tz=timezone.utc)
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(timezone.utc)
    except (OSError, OverflowError, TypeError, ValueError):
        return None


def _records(value: Any) -> Iterable[dict[str, Any]]:
    pending = [value]
    visited = 0
    while pending:
        visited += 1
        if visited > MAX_SUBJECT_NODES_PER_CASE:
            raise JudicialProviderError("volume de assuntos DataJud inválido")
        item = pending.pop()
        if isinstance(item, dict):
            yield item
        elif isinstance(item, list):
            pending.extend(reversed(item))


def _label(value: Any) -> str | None:
    normalized = " ".join(str(value or "").split())
    return normalized[:200] or None


def _dimension(record: Any) -> tuple[str, str | None] | None:
    if not isinstance(record, dict):
        return None
    code = _label(record.get("codigo"))
    name = _label(record.get("nome"))
    if not code and not name:
        return None
    return name or f"Código {code}", code


def _buckets(counter: Counter[tuple[str, str | None]], sample_size: int) -> list[MetricBucket]:
    return [
        MetricBucket(
            label=label,
            code=code,
            count=count,
            sample_share_percent=round((count / sample_size) * 100, 2) if sample_size else 0,
        )
        for (label, code), count in sorted(
            counter.items(), key=lambda item: (-item[1], item[0][0].casefold(), item[0][1] or "")
        )[:MAX_BUCKETS]
    ]


def descriptive_metrics(hits: list[dict[str, Any]]) -> tuple[DescriptiveMetrics, datetime | None]:
    months: Counter[tuple[str, str | None]] = Counter()
    degrees: Counter[tuple[str, str | None]] = Counter()
    classes: Counter[tuple[str, str | None]] = Counter()
    subjects: Counter[tuple[str, str | None]] = Counter()
    courts: Counter[tuple[str, str | None]] = Counter()
    coverage = Counter()
    source_updates: list[datetime] = []

    for source in hits:
        filed_at = _datetime(source.get("dataAjuizamento"))
        if filed_at:
            months[(filed_at.strftime("%Y-%m"), None)] += 1
            coverage["filing_date"] += 1
        degree = _label(source.get("grau"))
        if degree:
            degrees[(degree, None)] += 1
            coverage["degree"] += 1
        case_class = _dimension(source.get("classe"))
        if case_class:
            classes[case_class] += 1
            coverage["case_class"] += 1
        court = _dimension(source.get("orgaoJulgador"))
        if court:
            courts[court] += 1
            coverage["court_unit"] += 1
        case_subjects = {_dimension(item) for item in _records(source.get("assuntos"))}
        case_subjects.discard(None)
        if case_subjects:
            coverage["subjects"] += 1
            subjects.update(case_subjects)
        record_updates = [
            value
            for value in (
                _datetime(source.get("dataHoraUltimaAtualizacao")),
                _datetime(source.get("@timestamp")),
            )
            if value is not None
        ]
        if record_updates:
            source_updates.append(max(record_updates))
            coverage["source_update"] += 1

    sample_size = len(hits)
    metrics = DescriptiveMetrics(
        filings_by_month=_buckets(months, sample_size),
        cases_by_degree=_buckets(degrees, sample_size),
        cases_by_class=_buckets(classes, sample_size),
        subject_occurrences=_buckets(subjects, sample_size),
        cases_by_court_unit=_buckets(courts, sample_size),
        coverage=MetricCoverage(
            filing_date=coverage["filing_date"],
            degree=coverage["degree"],
            case_class=coverage["case_class"],
            subjects=coverage["subjects"],
            court_unit=coverage["court_unit"],
            source_update=coverage["source_update"],
        ),
    )
    return metrics, max(source_updates, default=None)


def analysis_response(request: JurimetryAnalysisRequest, sample: DataJudSample) -> JurimetryAnalysisResponse:
    metrics, source_updated_at = descriptive_metrics(sample.hits)
    sample_size = len(sample.hits)
    filters = request.filters
    universe = (
        f"Metadados públicos do {request.tribunal.upper()} com data de ajuizamento entre "
        f"{filters.date_from.isoformat()} e {filters.date_to.isoformat()}, após os filtros informados."
    )
    limitations = [
        "A API Pública do DataJud não garante precisão, integridade ou atualidade; confirme informações relevantes na fonte oficial.",
        f"A consulta foi limitada a {request.sample_limit} processos, ordenados pela atualização do índice; a amostra não é aleatória nem necessariamente representativa do universo.",
        "Percentuais usam o tamanho da amostra como denominador. Um processo pode ter vários assuntos, por isso os percentuais de assuntos não devem ser somados.",
        "Os indicadores são exclusivamente descritivos e não estimam resultado, duração, estratégia ou probabilidade de êxito de processos.",
    ]
    return JurimetryAnalysisResponse(
        request_id=request.request_id,
        persisted=False,
        tribunal=request.tribunal,
        filters=filters,
        sample_limit=request.sample_limit,
        sample_size=sample_size,
        total_matches=sample.total_matches,
        total_relation=sample.total_relation,
        source_name=SOURCE_NAME,
        source_url=sample.source_url,
        queried_at=sample.queried_at,
        source_updated_at=source_updated_at,
        universe=universe,
        metrics=metrics,
        limitations=limitations,
    )


def snapshot_response(snapshot: JurimetrySnapshot) -> JurimetryAnalysisResponse:
    return JurimetryAnalysisResponse(
        request_id=snapshot.request_id,
        snapshot_id=snapshot.id,
        persisted=True,
        tribunal=snapshot.tribunal,
        filters=snapshot.filters,
        sample_limit=snapshot.sample_limit,
        sample_size=snapshot.sample_size,
        total_matches=snapshot.total_matches,
        total_relation=snapshot.total_relation,
        source_name=snapshot.source_name,
        source_url=snapshot.source_url,
        queried_at=snapshot.queried_at,
        source_updated_at=snapshot.source_updated_at,
        universe=snapshot.universe,
        metrics=snapshot.metrics,
        limitations=snapshot.limitations,
    )


def snapshot_from_response(
    response: JurimetryAnalysisResponse,
    *,
    tenant_id: str,
    user_id: str,
    fingerprint: str,
) -> JurimetrySnapshot:
    return JurimetrySnapshot(
        tenant_id=tenant_id,
        request_id=str(response.request_id),
        request_fingerprint=fingerprint,
        tribunal=response.tribunal,
        filters=response.filters.model_dump(mode="json"),
        sample_limit=response.sample_limit,
        sample_size=response.sample_size,
        total_matches=response.total_matches,
        total_relation=response.total_relation,
        source_name=response.source_name,
        source_url=response.source_url,
        queried_at=response.queried_at,
        source_updated_at=response.source_updated_at,
        universe=response.universe,
        metrics=response.metrics.model_dump(mode="json"),
        limitations=response.limitations,
        created_by_user_id=user_id,
    )
