"""Bounded DataJud evidence fetcher for a future monitor worker.

It is deliberately side-effect free: callers must persist each returned event
through ``record_judicial_event`` and must set the PostgreSQL tenant context
before doing so. Deadlines are never interpreted here.
"""

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

import httpx

from app.schemas.controladoria import SUPPORTED_DATAJUD_TRIBUNALS


DATAJUD_HOST = "api-publica.datajud.cnj.jus.br"
ESCAVADOR_HOST = "api.escavador.com"
MAX_RESPONSE_BYTES = 2_000_000
MAX_HITS = 10
MAX_MOVEMENTS_PER_HIT = 1_000
MAX_EVENTS_PER_FETCH = 500


class JudicialProviderError(RuntimeError):
    """The source could not be safely interpreted; no partial result is valid."""


@dataclass(frozen=True)
class ProviderJudicialEvent:
    source_event_id: str
    source_url: str
    title: str
    source_content: str | None
    source_metadata: dict[str, Any]
    occurred_at: datetime | None
    retrieved_at: datetime


@dataclass(frozen=True)
class EscavadorCallbackDelivery:
    process_number: str
    provider_subscription_id: str
    event: ProviderJudicialEvent


def _payload_digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _format_cnj(number: str) -> str:
    return f"{number[:7]}-{number[7:9]}.{number[9:13]}.{number[13]}.{number[14:16]}.{number[16:]}"


def _escavador_movements_url(number: str) -> str:
    return f"https://{ESCAVADOR_HOST}/api/v2/processos/numero_cnj/{number}/movimentacoes"


def parse_escavador_movement(
    item: dict[str, Any],
    *,
    process_number: str,
    retrieved_at: datetime,
    ingestion_method: str,
    callback_uuid: str | None = None,
    delivery_sha256: str | None = None,
    provider_subscription_id: str | None = None,
) -> ProviderJudicialEvent:
    """Normalize one movement identically for polling and callback ingestion."""
    if not isinstance(item, dict):
        raise JudicialProviderError("movimento Escavador invalido")
    content = str(item.get("conteudo", "")).strip()
    raw_date = str(item.get("data", "")).strip()
    if not content or len(content) > 100_000:
        raise JudicialProviderError("conteudo Escavador invalido")
    try:
        occurred_at = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
        if occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=timezone.utc)
        else:
            occurred_at = occurred_at.astimezone(timezone.utc)
    except ValueError:
        occurred_at = None
    source = item.get("fonte") if isinstance(item.get("fonte"), dict) else {}
    classification = item.get("classificacao_predita") if isinstance(item.get("classificacao_predita"), dict) else {}
    raw_id = str(item.get("id", "")).strip()
    source_event_id = raw_id or hashlib.sha256(
        f"{raw_date}\x1f{content}\x1f{source.get('fonte_id', '')}".encode("utf-8")
    ).hexdigest()
    movement_type = str(item.get("tipo", "")).strip().upper()[:100] or None
    metadata: dict[str, Any] = {
        "type": movement_type,
        "court": str(source.get("sigla", ""))[:20] or None,
        "degree": str(source.get("grau_formatado", ""))[:100] or None,
        "occurred_at_raw": raw_date or None,
        "ingestion_method": ingestion_method,
        "provider_payload_sha256": _payload_digest(item),
        "suggested_action": (
            "Revisar publicação e avaliar providência ou prazo"
            if movement_type == "PUBLICACAO"
            else "Revisar andamento e definir providência"
        ),
    }
    if classification:
        metadata["classification"] = str(classification.get("nome", ""))[:200] or None
        metadata["classification_path"] = str(classification.get("hierarquia", ""))[:500] or None
    if callback_uuid:
        metadata["callback_uuid"] = callback_uuid
    if delivery_sha256:
        metadata["delivery_sha256"] = delivery_sha256
    if provider_subscription_id:
        metadata["provider_subscription_id"] = provider_subscription_id
    return ProviderJudicialEvent(
        source_event_id=source_event_id[:200],
        source_url=_escavador_movements_url(process_number),
        title=content[:500],
        source_content=content[:20_000],
        source_metadata=metadata,
        occurred_at=occurred_at,
        retrieved_at=retrieved_at,
    )


def parse_escavador_callback(payload: dict[str, Any]) -> EscavadorCallbackDelivery:
    if not isinstance(payload, dict) or payload.get("event") != "nova_movimentacao":
        raise JudicialProviderError("callback Escavador nao suportado")
    monitor = payload.get("monitoramento")
    movement = payload.get("movimentacao")
    callback_uuid = str(payload.get("uuid", "")).strip()
    if not isinstance(monitor, dict) or not isinstance(movement, dict) or not callback_uuid or len(callback_uuid) > 128:
        raise JudicialProviderError("callback Escavador invalido")
    number = re.sub(r"\D", "", str(monitor.get("numero", "")))
    provider_subscription_id = str(monitor.get("id", "")).strip()
    if len(number) != 20 or not provider_subscription_id or len(provider_subscription_id) > 128:
        raise JudicialProviderError("monitoramento Escavador invalido")
    retrieved_at = datetime.now(timezone.utc)
    return EscavadorCallbackDelivery(
        process_number=number,
        provider_subscription_id=provider_subscription_id,
        event=parse_escavador_movement(
            movement,
            process_number=number,
            retrieved_at=retrieved_at,
            ingestion_method="callback",
            callback_uuid=callback_uuid,
            delivery_sha256=_payload_digest(payload),
            provider_subscription_id=provider_subscription_id,
        ),
    )


class DataJudMonitoringProvider:
    """Fixed-host client with injectable transport for isolated tests."""

    def __init__(self, api_key: str, client_factory: Callable[..., httpx.AsyncClient] = httpx.AsyncClient):
        if not api_key:
            raise ValueError("api_key DataJud e obrigatoria")
        self._api_key = api_key
        self._client_factory = client_factory

    async def fetch(self, *, tribunal: str, process_number: str) -> list[ProviderJudicialEvent]:
        tribunal = tribunal.lower()
        number = re.sub(r"\D", "", process_number)
        if tribunal not in SUPPORTED_DATAJUD_TRIBUNALS or len(number) != 20:
            raise JudicialProviderError("assinatura DataJud invalida")
        endpoint = f"https://{DATAJUD_HOST}/api_publica_{tribunal}/_search"
        try:
            async with self._client_factory(timeout=15, follow_redirects=False) as client:
                response = await client.post(
                    endpoint,
                    headers={"Authorization": f"APIKey {self._api_key}"},
                    json={"size": MAX_HITS, "query": {"match": {"numeroProcesso": number}}},
                )
            if not response.is_success or len(response.content) > MAX_RESPONSE_BYTES:
                raise JudicialProviderError("resposta DataJud invalida")
            hits = response.json()["hits"]["hits"]
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise JudicialProviderError("fonte DataJud indisponivel ou resposta invalida") from exc
        if not isinstance(hits, list) or len(hits) > MAX_HITS:
            raise JudicialProviderError("volume de resultados DataJud invalido")

        retrieved_at = datetime.now(timezone.utc)
        events: list[ProviderJudicialEvent] = []
        for hit in hits:
            source = hit.get("_source") if isinstance(hit, dict) else None
            if not isinstance(source, dict):
                raise JudicialProviderError("registro DataJud invalido")
            if re.sub(r"\D", "", str(source.get("numeroProcesso", ""))) != number:
                continue
            movements = source.get("movimentos", [])
            if not isinstance(movements, list) or len(movements) > MAX_MOVEMENTS_PER_HIT:
                raise JudicialProviderError("volume de movimentos requer revisao humana")
            for movement in movements:
                if not isinstance(movement, dict):
                    continue
                name = str(movement.get("nome", "")).strip()
                raw_timestamp = str(movement.get("dataHora", ""))
                if not name:
                    continue
                try:
                    occurred_at = datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00"))
                    if occurred_at.tzinfo is None:
                        raise ValueError
                    occurred_at = occurred_at.astimezone(timezone.utc)
                except ValueError:
                    continue
                code = str(movement.get("codigo", "")).strip() or None
                source_event_id = hashlib.sha256(
                    f"{code or ''}\x1f{raw_timestamp}\x1f{name}".encode("utf-8")
                ).hexdigest()
                source_content = str(movement.get("complemento", "")).strip() or None
                events.append(
                    ProviderJudicialEvent(
                        source_event_id=source_event_id,
                        source_url=endpoint,
                        title=name[:500],
                        source_content=source_content[:20_000] if source_content else None,
                        source_metadata={
                            "code": code,
                            "occurred_at_raw": raw_timestamp,
                            "ingestion_method": "poll",
                            "provider_payload_sha256": _payload_digest(movement),
                            "suggested_action": "Revisar andamento e definir providência",
                        },
                        occurred_at=occurred_at,
                        retrieved_at=retrieved_at,
                    )
                )
                if len(events) >= MAX_EVENTS_PER_FETCH:
                    return events
        return events


class EscavadorMonitoringProvider:
    """Read-only access to already indexed public movements in Escavador v2."""

    def __init__(self, api_token: str, client_factory: Callable[..., httpx.AsyncClient] = httpx.AsyncClient):
        if not api_token:
            raise ValueError("token Escavador e obrigatorio")
        self._api_token = api_token
        self._client_factory = client_factory

    async def ensure_monitor(self, *, tribunal: str, process_number: str) -> str:
        number = re.sub(r"\D", "", process_number)
        if len(number) != 20:
            raise JudicialProviderError("numero CNJ invalido")
        endpoint = f"https://{ESCAVADOR_HOST}/api/v2/monitoramentos/processos"
        try:
            async with self._client_factory(timeout=20, follow_redirects=False) as client:
                response = await client.post(
                    endpoint,
                    headers={
                        "Authorization": f"Bearer {self._api_token}",
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    },
                    json={
                        "numero": _format_cnj(number),
                        "tribunal": tribunal.upper(),
                        "frequencia": "DIARIA",
                        "documentos_publicos": False,
                    },
                )
            if not response.is_success or len(response.content) > MAX_RESPONSE_BYTES:
                raise JudicialProviderError("monitoramento Escavador nao provisionado")
            payload = response.json()
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            if isinstance(exc, JudicialProviderError):
                raise
            raise JudicialProviderError("fonte Escavador indisponivel ou resposta invalida") from exc
        provider_subscription_id = str(payload.get("id", "")).strip() if isinstance(payload, dict) else ""
        if not provider_subscription_id or len(provider_subscription_id) > 128:
            raise JudicialProviderError("identificador de monitoramento Escavador invalido")
        return provider_subscription_id

    async def fetch(self, *, tribunal: str, process_number: str) -> list[ProviderJudicialEvent]:
        del tribunal  # Escavador resolves the court from the CNJ number.
        number = re.sub(r"\D", "", process_number)
        if len(number) != 20:
            raise JudicialProviderError("numero CNJ invalido")
        endpoint = _escavador_movements_url(number)
        try:
            async with self._client_factory(timeout=20, follow_redirects=False) as client:
                response = await client.get(
                    endpoint,
                    headers={
                        "Authorization": f"Bearer {self._api_token}",
                        "Accept": "application/json",
                        "X-Requested-With": "XMLHttpRequest",
                    },
                    params={"limit": 100, "ordem": "desc"},
                )
            if not response.is_success or len(response.content) > MAX_RESPONSE_BYTES:
                raise JudicialProviderError("resposta Escavador invalida")
            payload = response.json()
            items = payload.get("items") if isinstance(payload, dict) else None
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            if isinstance(exc, JudicialProviderError):
                raise
            raise JudicialProviderError("fonte Escavador indisponivel ou resposta invalida") from exc
        if not isinstance(items, list) or len(items) > 100:
            raise JudicialProviderError("volume de movimentos Escavador invalido")

        retrieved_at = datetime.now(timezone.utc)
        events: list[ProviderJudicialEvent] = []
        for item in items:
            events.append(parse_escavador_movement(
                item,
                process_number=number,
                retrieved_at=retrieved_at,
                ingestion_method="poll",
            ))
        return events


def monitoring_provider(source_kind: str, config):
    if source_kind == "datajud" and getattr(config, "DATAJUD_ENABLED", False) and getattr(config, "DATAJUD_API_KEY", None):
        return DataJudMonitoringProvider(config.DATAJUD_API_KEY)
    if source_kind == "escavador" and getattr(config, "ESCAVADOR_ENABLED", False) and getattr(config, "ESCAVADOR_API_TOKEN", None):
        return EscavadorMonitoringProvider(config.ESCAVADOR_API_TOKEN)
    raise JudicialProviderError("provedor judicial nao configurado")
