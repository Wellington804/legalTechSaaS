"""Bounded adapters for configured judicial evidence sources.

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
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import httpx

from app.schemas.controladoria import SUPPORTED_DATAJUD_TRIBUNALS


DATAJUD_HOST = "api-publica.datajud.cnj.jus.br"
ESCAVADOR_HOST = "api.escavador.com"
DJEN_HOSTS = frozenset({"comunicaapi.pje.jus.br", "hcomunicaapi.cnj.jus.br"})
DJEN_ENDPOINT = "https://comunicaapi.pje.jus.br/api/v1/comunicacao"
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
class ProviderFetchPage:
    events: list[ProviderJudicialEvent]
    next_cursor: str | None = None


@dataclass(frozen=True)
class EscavadorCallbackDelivery:
    process_number: str
    provider_subscription_id: str
    event: ProviderJudicialEvent


def _payload_digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _normalize_process_number(value: Any) -> str:
    return re.sub(r"\D", "", str(value or ""))


def _parse_source_datetime(value: Any, *, timezone_name: str = "America/Sao_Paulo") -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=ZoneInfo(timezone_name))
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _safe_http_url(value: Any, fallback: str) -> str:
    candidate = str(value or "").strip()
    parsed = urlsplit(candidate)
    if parsed.scheme in {"https", "http"} and parsed.netloc and not parsed.username and not parsed.password:
        return candidate[:2048]
    return fallback


def _configured_https_endpoint(value: Any, *, allowed_hosts: frozenset[str] | None = None) -> str:
    endpoint = str(value or "").strip()
    parsed = urlsplit(endpoint)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise JudicialProviderError("endpoint judicial HTTPS nao configurado")
    if allowed_hosts is not None and parsed.hostname not in allowed_hosts:
        raise JudicialProviderError("host judicial nao autorizado")
    return endpoint.rstrip("/")


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

    async def fetch_page(
        self, *, tribunal: str, process_number: str, cursor: str | None = None
    ) -> ProviderFetchPage:
        del cursor
        return ProviderFetchPage(await self.fetch(tribunal=tribunal, process_number=process_number))


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

    async def fetch_page(
        self, *, tribunal: str, process_number: str, cursor: str | None = None
    ) -> ProviderFetchPage:
        del cursor
        return ProviderFetchPage(await self.fetch(tribunal=tribunal, process_number=process_number))


def _communication_event(
    item: dict[str, Any],
    *,
    source_kind: str,
    endpoint: str,
    process_number: str,
    retrieved_at: datetime,
) -> ProviderJudicialEvent | None:
    item_number = _normalize_process_number(
        item.get("numero_processo") or item.get("numeroProcesso") or item.get("process_number")
    )
    if len(item_number) != 20:
        raise JudicialProviderError("comunicacao judicial sem numero CNJ vinculante")
    if item_number != process_number:
        raise JudicialProviderError("comunicacao judicial nao corresponde ao processo consultado")
    content = str(
        item.get("texto") or item.get("conteudo") or item.get("content") or item.get("assunto") or ""
    ).strip()
    if not content or len(content) > 100_000:
        raise JudicialProviderError("comunicacao judicial sem conteudo valido")
    raw_date = (
        item.get("data_disponibilizacao")
        or item.get("dataDisponibilizacao")
        or item.get("dataEnvio")
        or item.get("published_at")
        or item.get("data")
    )
    occurred_at = _parse_source_datetime(raw_date)
    raw_id = str(
        item.get("hash")
        or item.get("numeroComunicacao")
        or item.get("numero_comunicacao")
        or item.get("id")
        or ""
    ).strip()
    source_event_id = raw_id or hashlib.sha256(
        f"{process_number}\x1f{raw_date or ''}\x1f{content}".encode("utf-8")
    ).hexdigest()
    kind = str(
        item.get("tipoComunicacao") or item.get("tipo_comunicacao") or item.get("tipo") or "COMUNICACAO"
    ).strip()[:100]
    source_url = _safe_http_url(item.get("link") or item.get("url"), endpoint)
    return ProviderJudicialEvent(
        source_event_id=source_event_id[:200],
        source_url=source_url,
        title=(kind.title() + ": " + content)[:500],
        source_content=content[:20_000],
        source_metadata={
            "type": kind.upper(),
            "court": str(item.get("siglaTribunal") or item.get("tribunal") or "")[:20] or None,
            "communication_number": str(
                item.get("numeroComunicacao") or item.get("numero_comunicacao") or ""
            )[:100] or None,
            "document_type": str(item.get("tipoDocumento") or item.get("tipo_documento") or "")[:100] or None,
            "court_unit": str(item.get("nomeOrgao") or item.get("orgao") or "")[:200] or None,
            "occurred_at_raw": str(raw_date or "")[:100] or None,
            "ingestion_method": "poll",
            "provider_payload_sha256": _payload_digest(item),
            "provider_source": source_kind,
            "active": item.get("ativo") if isinstance(item.get("ativo"), bool) else None,
            "suggested_action": "Revisar comunicacao e avaliar providencia ou prazo",
        },
        occurred_at=occurred_at,
        retrieved_at=retrieved_at,
    )


class DjenMonitoringProvider:
    """Official public DJEN API (CNJ), queried by CNJ process number."""

    def __init__(
        self,
        endpoint: str = DJEN_ENDPOINT,
        client_factory: Callable[..., httpx.AsyncClient] = httpx.AsyncClient,
    ):
        self._endpoint = _configured_https_endpoint(endpoint, allowed_hosts=DJEN_HOSTS)
        self._client_factory = client_factory

    async def fetch_page(
        self, *, tribunal: str, process_number: str, cursor: str | None = None
    ) -> ProviderFetchPage:
        number = _normalize_process_number(process_number)
        if tribunal.lower() not in SUPPORTED_DATAJUD_TRIBUNALS or len(number) != 20:
            raise JudicialProviderError("assinatura DJEN invalida")
        try:
            page = int(cursor or "1")
        except ValueError as exc:
            raise JudicialProviderError("cursor DJEN invalido") from exc
        if not 1 <= page <= 100_000:
            raise JudicialProviderError("cursor DJEN fora do limite")
        try:
            async with self._client_factory(timeout=20, follow_redirects=False) as client:
                response = await client.get(
                    self._endpoint,
                    headers={"Accept": "application/json"},
                    params={
                        "numeroProcesso": number,
                        "siglaTribunal": tribunal.upper(),
                        "pagina": page,
                        "itensPorPagina": 100,
                        "meio": "D",
                    },
                )
            if not response.is_success or len(response.content) > MAX_RESPONSE_BYTES:
                raise JudicialProviderError("resposta DJEN invalida")
            payload = response.json()
            items = payload.get("items") if isinstance(payload, dict) else None
        except (httpx.HTTPError, TypeError, ValueError) as exc:
            if isinstance(exc, JudicialProviderError):
                raise
            raise JudicialProviderError("fonte DJEN indisponivel ou resposta invalida") from exc
        if not isinstance(items, list) or len(items) > 100:
            raise JudicialProviderError("volume de comunicacoes DJEN invalido")
        if any(not isinstance(item, dict) for item in items):
            raise JudicialProviderError("registro DJEN invalido")
        retrieved_at = datetime.now(timezone.utc)
        events = [
            event
            for item in items
            for event in [
                _communication_event(
                    item,
                    source_kind="djen",
                    endpoint=self._endpoint,
                    process_number=number,
                    retrieved_at=retrieved_at,
                )
            ]
            if event is not None
        ]
        return ProviderFetchPage(events=events, next_cursor=str(page + 1) if len(items) == 100 else None)


class CredentialedCommunicationProvider:
    """Fail-closed adapter for contracted CNJ/tribunal communication endpoints.

    The configured endpoint must expose a bounded JSON collection in `items`,
    `content` or `comunicacoes`. Homologation remains an operational gate.
    """

    def __init__(
        self,
        *,
        source_kind: str,
        endpoint: str,
        token: str,
        token_header: str = "Authorization",
        client_factory: Callable[..., httpx.AsyncClient] = httpx.AsyncClient,
    ):
        if source_kind not in {"domicilio", "tribunal_api"} or not token:
            raise JudicialProviderError("credencial judicial nao configurada")
        if token_header not in {"Authorization", "X-API-Key"}:
            raise JudicialProviderError("cabecalho de credencial judicial nao permitido")
        self.source_kind = source_kind
        self._endpoint = _configured_https_endpoint(endpoint)
        self._token = token
        self._token_header = token_header
        self._client_factory = client_factory

    async def fetch_page(
        self, *, tribunal: str, process_number: str, cursor: str | None = None
    ) -> ProviderFetchPage:
        number = _normalize_process_number(process_number)
        if tribunal.lower() not in SUPPORTED_DATAJUD_TRIBUNALS or len(number) != 20:
            raise JudicialProviderError("assinatura de comunicacoes invalida")
        if cursor is not None and len(cursor) > 512:
            raise JudicialProviderError("cursor do provedor invalido")
        credential = f"Bearer {self._token}" if self._token_header == "Authorization" else self._token
        params = {"numeroProcesso": number, "limite": 100}
        if cursor:
            params["cursor"] = cursor
        try:
            async with self._client_factory(timeout=25, follow_redirects=False) as client:
                response = await client.get(
                    self._endpoint,
                    headers={self._token_header: credential, "Accept": "application/json"},
                    params=params,
                )
            if not response.is_success or len(response.content) > MAX_RESPONSE_BYTES:
                raise JudicialProviderError("resposta do conector judicial invalida")
            payload = response.json()
        except (httpx.HTTPError, TypeError, ValueError) as exc:
            if isinstance(exc, JudicialProviderError):
                raise
            raise JudicialProviderError("conector judicial indisponivel ou resposta invalida") from exc
        if not isinstance(payload, dict):
            raise JudicialProviderError("contrato do conector judicial invalido")
        if "items" in payload:
            items = payload["items"]
        elif "content" in payload:
            items = payload["content"]
        else:
            items = payload.get("comunicacoes")
        if not isinstance(items, list) or len(items) > 100:
            raise JudicialProviderError("volume do conector judicial invalido")
        if any(not isinstance(item, dict) for item in items):
            raise JudicialProviderError("registro do conector judicial invalido")
        next_cursor_value = payload.get("next_cursor") or payload.get("proximoCursor")
        next_cursor = str(next_cursor_value) if next_cursor_value not in (None, "") else None
        if next_cursor and len(next_cursor) > 512:
            raise JudicialProviderError("cursor retornado pelo conector invalido")
        retrieved_at = datetime.now(timezone.utc)
        events = [
            event
            for item in items
            for event in [
                _communication_event(
                    item,
                    source_kind=self.source_kind,
                    endpoint=self._endpoint,
                    process_number=number,
                    retrieved_at=retrieved_at,
                )
            ]
            if event is not None
        ]
        return ProviderFetchPage(events=events, next_cursor=next_cursor)


def _tribunal_connectors(config) -> dict[str, dict[str, Any]]:
    raw = getattr(config, "TRIBUNAL_SOURCE_CONNECTORS", None) or {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError as exc:
            raise JudicialProviderError("configuracao de fontes dos tribunais invalida") from exc
    if not isinstance(raw, dict):
        raise JudicialProviderError("configuracao de fontes dos tribunais invalida")
    return {str(key).lower(): value for key, value in raw.items() if isinstance(value, dict)}


def provider_configuration_status(config, tribunal: str | None = None) -> list[dict[str, Any]]:
    connectors = _tribunal_connectors(config)
    tribunal_config = connectors.get((tribunal or "").lower()) if tribunal else None
    tribunal_configured = bool(
        tribunal_config
        and tribunal_config.get("url")
        and tribunal_config.get("token")
        and tribunal_config.get("homologated") is True
    )
    if tribunal is None:
        tribunal_configured = any(
            item.get("url") and item.get("token") and item.get("homologated") is True
            for item in connectors.values()
        )
    return [
        {
            "source_kind": "datajud",
            "label": "DataJud",
            "configured": bool(getattr(config, "DATAJUD_ENABLED", False) and getattr(config, "DATAJUD_API_KEY", None)),
            "homologation_required": False,
            "detail": "API Publica do CNJ para dados processuais.",
        },
        {
            "source_kind": "escavador",
            "label": "Escavador",
            "configured": bool(getattr(config, "ESCAVADOR_ENABLED", False) and getattr(config, "ESCAVADOR_API_TOKEN", None)),
            "homologation_required": True,
            "detail": "Monitoramento contratado; requer token e callback homologado.",
        },
        {
            "source_kind": "djen",
            "label": "DJEN",
            "configured": True,
            "homologation_required": False,
            "detail": "Consulta publica oficial do Diario de Justica Eletronico Nacional.",
        },
        {
            "source_kind": "domicilio",
            "label": "Domicilio Judicial Eletronico",
            "configured": bool(
                getattr(config, "DOMICILIO_JUDICIAL_API_URL", None)
                and getattr(config, "DOMICILIO_JUDICIAL_API_TOKEN", None)
                and getattr(config, "DOMICILIO_JUDICIAL_HOMOLOGATED", False)
            ),
            "homologation_required": True,
            "detail": "Exige credenciais de interoperabilidade e homologacao fornecidas pelo CNJ.",
        },
        {
            "source_kind": "tribunal_api",
            "label": "API especifica do tribunal",
            "configured": tribunal_configured,
            "homologation_required": True,
            "detail": "Conector contratual por tribunal; indisponivel sem endpoint e credencial homologados.",
        },
    ]


def monitoring_provider(source_kind: str, config, *, tribunal: str | None = None):
    if source_kind == "datajud" and getattr(config, "DATAJUD_ENABLED", False) and getattr(config, "DATAJUD_API_KEY", None):
        return DataJudMonitoringProvider(config.DATAJUD_API_KEY)
    if source_kind == "escavador" and getattr(config, "ESCAVADOR_ENABLED", False) and getattr(config, "ESCAVADOR_API_TOKEN", None):
        return EscavadorMonitoringProvider(config.ESCAVADOR_API_TOKEN)
    if source_kind == "djen":
        return DjenMonitoringProvider(getattr(config, "DJEN_API_URL", None) or DJEN_ENDPOINT)
    if source_kind == "domicilio":
        if not getattr(config, "DOMICILIO_JUDICIAL_HOMOLOGATED", False):
            raise JudicialProviderError("Domicilio Judicial ainda nao homologado")
        return CredentialedCommunicationProvider(
            source_kind="domicilio",
            endpoint=getattr(config, "DOMICILIO_JUDICIAL_API_URL", None),
            token=getattr(config, "DOMICILIO_JUDICIAL_API_TOKEN", None),
            token_header=getattr(config, "DOMICILIO_JUDICIAL_TOKEN_HEADER", "Authorization"),
        )
    if source_kind == "tribunal_api" and tribunal:
        connector = _tribunal_connectors(config).get(tribunal.lower()) or {}
        if connector.get("homologated") is not True:
            raise JudicialProviderError("fonte especifica do tribunal ainda nao homologada")
        return CredentialedCommunicationProvider(
            source_kind="tribunal_api",
            endpoint=connector.get("url"),
            token=connector.get("token"),
            token_header=connector.get("token_header", "Authorization"),
        )
    raise JudicialProviderError("provedor judicial nao configurado")
