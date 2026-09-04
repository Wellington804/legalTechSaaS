"""Narrow Clicksign API v3 adapter.

Only immutable PDF bytes and signer identity are sent. Certificate material and
PINs are handled by Clicksign's ICP-Brasil ceremony and never enter LexFlow.
"""

import base64
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal
from urllib.parse import urljoin, urlsplit

import httpx


CLICKSIGN_BASE_URLS = {
    "clicksign": "https://app.clicksign.com/api/v3/",
    "clicksign-sandbox": "https://sandbox.clicksign.com/api/v3/",
}
MAX_SIGNED_PDF_BYTES = 25 * 1024 * 1024


class ClicksignDispatchError(RuntimeError):
    """Safe provider error with enough state to prevent blind redispatch."""

    def __init__(
        self,
        message: str,
        *,
        ambiguous: bool,
        envelope_id: str | None = None,
        document_id: str | None = None,
    ):
        super().__init__(message)
        self.ambiguous = ambiguous
        self.envelope_id = envelope_id
        self.document_id = document_id


@dataclass(frozen=True)
class ClicksignSigner:
    name: str
    email: str
    cpf: str | None
    authentication: Literal["email", "icp_brasil"]


@dataclass(frozen=True)
class ClicksignSubmission:
    envelope_id: str
    document_id: str
    signer_id: str


@dataclass(frozen=True)
class ClicksignWebhook:
    account_reference: str
    event_id: str
    event_name: str
    event_type: Literal["envelope.signed", "envelope.declined", "envelope.expired"] | None
    local_envelope_id: str | None
    provider_document_id: str | None


def provider_base_url(provider: str) -> str:
    try:
        return CLICKSIGN_BASE_URLS[provider]
    except KeyError as exc:
        raise ValueError("unsupported Clicksign provider") from exc


def format_cpf(value: str | None) -> str | None:
    if value is None:
        return None
    digits = re.sub(r"\D", "", value)
    if len(digits) != 11:
        raise ValueError("CPF must contain 11 digits")
    return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"


def _provider_detail(payload: Any) -> str:
    if not isinstance(payload, dict):
        return "Resposta inválida do serviço de assinatura."
    errors = payload.get("errors")
    if isinstance(errors, list) and errors and isinstance(errors[0], dict):
        detail = errors[0].get("detail") or errors[0].get("title")
        if isinstance(detail, str) and detail.strip():
            return detail.strip()[:300]
    return "O serviço de assinatura recusou a operação."


class ClicksignClient:
    """HTTPS client pinned to one reviewed Clicksign API host."""

    def __init__(self, provider: str, access_token: str):
        self.base_url = provider_base_url(provider)
        self.host = urlsplit(self.base_url).netloc.casefold()
        self.headers = {
            "Authorization": access_token.strip(),
            "Accept": "application/vnd.api+json",
            "Content-Type": "application/vnd.api+json",
        }

    async def request_json(self, method: str, path: str, payload: dict | None = None) -> dict:
        if method not in {"GET", "POST", "PATCH"}:
            raise ValueError("unsupported Clicksign method")
        if not path.startswith("/") or path.startswith("//"):
            raise ValueError("Clicksign path must be absolute and hostless")
        target = urljoin(self.base_url, path.lstrip("/"))
        if urlsplit(target).netloc.casefold() != self.host:
            raise ValueError("Clicksign path escaped fixed host")
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=5.0), follow_redirects=False) as client:
                response = await client.request(method, target, json=payload, headers=self.headers)
        except httpx.RequestError as exc:
            raise ClicksignDispatchError("Clicksign não confirmou a operação.", ambiguous=True) from exc
        if 300 <= response.status_code < 400:
            raise ClicksignDispatchError("Redirecionamento inesperado da Clicksign.", ambiguous=True)
        try:
            body = response.json()
        except ValueError as exc:
            raise ClicksignDispatchError("Resposta inválida da Clicksign.", ambiguous=response.status_code >= 500) from exc
        if not 200 <= response.status_code < 300:
            raise ClicksignDispatchError(_provider_detail(body), ambiguous=response.status_code >= 500)
        if not isinstance(body, dict):
            raise ClicksignDispatchError("Resposta inválida da Clicksign.", ambiguous=True)
        return body


def _data_id(payload: dict, resource: str) -> str:
    data = payload.get("data")
    value = data.get("id") if isinstance(data, dict) else None
    if not isinstance(value, str) or not value:
        raise ClicksignDispatchError(f"Clicksign não retornou o identificador de {resource}.", ambiguous=True)
    return value


def _relationships(document_id: str, signer_id: str) -> dict:
    return {
        "document": {"data": {"type": "documents", "id": document_id}},
        "signer": {"data": {"type": "signers", "id": signer_id}},
    }


async def submit_clicksign_envelope(
    *,
    provider: str,
    access_token: str,
    local_envelope_id: str,
    filename: str,
    pdf: bytes,
    pdf_sha256: str,
    signer: ClicksignSigner,
    expires_at: datetime | None,
    client: ClicksignClient | None = None,
) -> ClicksignSubmission:
    """Create, populate, activate and notify one Clicksign v3 envelope."""

    if len(pdf) > MAX_SIGNED_PDF_BYTES or not pdf.startswith(b"%PDF-"):
        raise ValueError("signature source must be a PDF up to 25 MB")
    if hashlib.sha256(pdf).hexdigest() != pdf_sha256:
        raise ValueError("signature source hash mismatch")
    transport = client or ClicksignClient(provider, access_token)
    envelope_id = None
    document_id = None
    try:
        envelope_attributes: dict[str, Any] = {
            "name": f"LexFlow — {filename}"[:255],
            "locale": "pt-BR",
            "auto_close": True,
            "remind_interval": 3,
            "block_after_refusal": True,
        }
        if expires_at:
            envelope_attributes["deadline_at"] = expires_at.isoformat()
        envelope_id = _data_id(
            await transport.request_json(
                "POST",
                "/envelopes",
                {"data": {"type": "envelopes", "attributes": envelope_attributes}},
            ),
            "envelope",
        )
        document_id = _data_id(
            await transport.request_json(
                "POST",
                f"/envelopes/{envelope_id}/documents",
                {
                    "data": {
                        "type": "documents",
                        "attributes": {
                            "filename": filename,
                            "content_base64": "data:application/pdf;base64," + base64.b64encode(pdf).decode("ascii"),
                            "metadata": {
                                "lexflow_envelope_id": local_envelope_id,
                                "lexflow_source_sha256": pdf_sha256,
                            },
                        },
                    }
                },
            ),
            "documento",
        )
        signer_attributes: dict[str, Any] = {
            "name": signer.name,
            "email": signer.email,
            "has_documentation": signer.cpf is not None,
            "refusable": True,
            "communicate_events": {
                "signature_request": "email",
                "signature_reminder": "email",
                "document_signed": "email",
            },
        }
        if signer.cpf:
            signer_attributes["documentation"] = format_cpf(signer.cpf)
        signer_id = _data_id(
            await transport.request_json(
                "POST",
                f"/envelopes/{envelope_id}/signers",
                {"data": {"type": "signers", "attributes": signer_attributes}},
            ),
            "signatário",
        )
        relationships = _relationships(document_id, signer_id)
        await transport.request_json(
            "POST",
            f"/envelopes/{envelope_id}/requirements",
            {
                "data": {
                    "type": "requirements",
                    "attributes": {"action": "agree", "role": "sign"},
                    "relationships": relationships,
                }
            },
        )
        await transport.request_json(
            "POST",
            f"/envelopes/{envelope_id}/requirements",
            {
                "data": {
                    "type": "requirements",
                    "attributes": {"action": "provide_evidence", "auth": signer.authentication},
                    "relationships": relationships,
                }
            },
        )
        await transport.request_json(
            "PATCH",
            f"/envelopes/{envelope_id}",
            {"data": {"id": envelope_id, "type": "envelopes", "attributes": {"status": "running"}}},
        )
        await transport.request_json(
            "POST",
            f"/envelopes/{envelope_id}/notifications",
            {"data": {"type": "notifications", "attributes": {}}},
        )
        return ClicksignSubmission(envelope_id=envelope_id, document_id=document_id, signer_id=signer_id)
    except ClicksignDispatchError as exc:
        raise ClicksignDispatchError(
            str(exc),
            ambiguous=exc.ambiguous,
            envelope_id=envelope_id or exc.envelope_id,
            document_id=document_id or exc.document_id,
        ) from exc


def _dig(value: Any, *path: str) -> Any:
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def parse_clicksign_webhook(raw: bytes, event_header: str | None) -> ClicksignWebhook:
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid Clicksign webhook JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("invalid Clicksign webhook object")
    body_event = _dig(payload, "event", "name")
    if body_event is not None and not isinstance(body_event, str):
        raise ValueError("invalid Clicksign event name")
    header_event = event_header.strip() if event_header else None
    if body_event and header_event and body_event != header_event:
        raise ValueError("Clicksign event header does not match body")
    event_name = body_event or header_event
    if not event_name:
        raise ValueError("missing Clicksign event name")
    account = _dig(payload, "event", "data", "account", "key") or _dig(payload, "document", "account_key")
    if not isinstance(account, str) or not 2 <= len(account) <= 128:
        raise ValueError("missing Clicksign account key")
    document = payload.get("document")
    if isinstance(document, list):
        document = document[0] if document else None
    provider_document_id = None
    local_envelope_id = None
    if isinstance(document, dict):
        provider_document_id = document.get("key") or document.get("id")
        metadata = document.get("metadata")
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except json.JSONDecodeError:
                metadata = None
        if isinstance(metadata, dict):
            local_envelope_id = metadata.get("lexflow_envelope_id")
    event_types: dict[str, Literal["envelope.signed", "envelope.declined", "envelope.expired"]] = {
        "document_closed": "envelope.signed",
        "document_refused": "envelope.declined",
        "document_canceled": "envelope.expired",
    }
    occurred_at = _dig(payload, "event", "occurred_at")
    identifier_material = json.dumps(
        [event_name, occurred_at, provider_document_id, local_envelope_id, hashlib.sha256(raw).hexdigest()],
        ensure_ascii=True,
        separators=(",", ":"),
    )
    event_id = hashlib.sha256(identifier_material.encode("utf-8")).hexdigest()
    return ClicksignWebhook(
        account_reference=account,
        event_id=event_id,
        event_name=event_name,
        event_type=event_types.get(event_name),
        local_envelope_id=local_envelope_id if isinstance(local_envelope_id, str) else None,
        provider_document_id=provider_document_id if isinstance(provider_document_id, str) else None,
    )


def _signed_file_url(payload: dict) -> str | None:
    candidates = (
        _dig(payload, "data", "links", "files", "signed"),
        _dig(payload, "data", "links", "files", "signed_file_url"),
        _dig(payload, "data", "attributes", "downloads", "signed"),
        _dig(payload, "data", "attributes", "downloads", "signed_file_url"),
        _dig(payload, "document", "downloads", "signed_file_url"),
    )
    return next((value for value in candidates if isinstance(value, str) and value), None)


def _allowed_download_host(host: str, provider: str) -> bool:
    host = host.casefold()
    if host == urlsplit(provider_base_url(provider)).hostname:
        return True
    if not host.endswith(".amazonaws.com"):
        return False
    bucket = host.split(".s3", 1)[0]
    # The v3 reference currently documents ``tavola-staging``. Clicksign has
    # also used the exact content bucket names below. Do not accept arbitrary
    # S3 buckets merely because their attacker-controlled name contains the
    # words "clicksign" and "content".
    allowed_buckets = {
        "tavola-staging",
        "tavola-production",
        "tavola",
        "clicksign-content",
        "clicksign-sandbox-content",
        "clicksign-production-content",
        "clicksign-content-sandbox",
        "clicksign-content-production",
    }
    return bucket in allowed_buckets


async def fetch_clicksign_signed_pdf(
    *,
    provider: str,
    access_token: str,
    envelope_id: str,
    document_id: str,
    client: ClicksignClient | None = None,
) -> bytes:
    transport = client or ClicksignClient(provider, access_token)
    details = await transport.request_json("GET", f"/envelopes/{envelope_id}/documents/{document_id}")
    url = _signed_file_url(details)
    if not url:
        raise ClicksignDispatchError("Arquivo assinado ainda não está disponível.", ambiguous=True)
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.port not in {None, 443}
        or not _allowed_download_host(parsed.hostname, provider)
    ):
        raise ClicksignDispatchError("A Clicksign retornou um endereço de download não autorizado.", ambiguous=True)
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0), follow_redirects=False) as http:
            async with http.stream("GET", url, headers={"Accept": "application/pdf"}) as response:
                if not 200 <= response.status_code < 300:
                    raise ClicksignDispatchError("Arquivo assinado ainda não está disponível.", ambiguous=True)
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > MAX_SIGNED_PDF_BYTES:
                        raise ClicksignDispatchError("Arquivo assinado excede 25 MB.", ambiguous=False)
    except httpx.RequestError as exc:
        raise ClicksignDispatchError("Falha ao baixar o arquivo assinado.", ambiguous=True) from exc
    pdf = bytes(content)
    if not pdf.startswith(b"%PDF-"):
        raise ClicksignDispatchError("A Clicksign não retornou um PDF assinado válido.", ambiguous=True)
    return pdf
