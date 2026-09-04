"""Autentique GraphQL adapter with authenticated webhook parsing.

The adapter sends an immutable PDF and signer identity.  A1/A3 private keys,
PFX files and PINs remain in the provider/browser signing ceremony.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal
from urllib.parse import urlsplit

import httpx


AUTENTIQUE_PROVIDERS = {"autentique": "https://api.autentique.com.br/v2/graphql"}
MAX_SIGNED_PDF_BYTES = 20 * 1024 * 1024


class AutentiqueDispatchError(RuntimeError):
    def __init__(self, message: str, *, ambiguous: bool, document_id: str | None = None):
        super().__init__(message)
        self.ambiguous = ambiguous
        self.document_id = document_id


@dataclass(frozen=True)
class AutentiqueSigner:
    name: str
    email: str
    cpf: str | None
    authentication: Literal["email", "icp_brasil"]


@dataclass(frozen=True)
class AutentiqueSubmission:
    document_id: str
    signer_id: str | None


@dataclass(frozen=True)
class AutentiqueWebhook:
    account_reference: str
    event_id: str
    event_name: str
    event_type: Literal["envelope.signed", "envelope.declined", "envelope.expired"] | None
    provider_document_id: str | None


class AutentiqueClient:
    def __init__(self, access_token: str, *, client: httpx.AsyncClient | None = None):
        self.headers = {"Authorization": f"Bearer {access_token.strip()}", "Accept": "application/json"}
        self._client = client

    async def graphql(self, query: str, variables: dict, *, file: tuple[str, bytes] | None = None) -> dict:
        owned = self._client is None
        client = self._client or httpx.AsyncClient(timeout=httpx.Timeout(30, connect=5), follow_redirects=False)
        try:
            if file:
                filename, content = file
                operations = json.dumps({"query": query, "variables": {**variables, "file": None}}, separators=(",", ":"))
                response = await client.post(
                    AUTENTIQUE_PROVIDERS["autentique"],
                    headers=self.headers,
                    data={"operations": operations, "map": json.dumps({"0": ["variables.file"]})},
                    files={"0": (filename, content, "application/pdf")},
                )
            else:
                response = await client.post(
                    AUTENTIQUE_PROVIDERS["autentique"],
                    headers={**self.headers, "Content-Type": "application/json"},
                    json={"query": query, "variables": variables},
                )
        except httpx.RequestError as exc:
            raise AutentiqueDispatchError("Autentique não confirmou a operação.", ambiguous=True) from exc
        finally:
            if owned:
                await client.aclose()
        if 300 <= response.status_code < 400:
            raise AutentiqueDispatchError("Redirecionamento inesperado da Autentique.", ambiguous=True)
        try:
            body = response.json()
        except ValueError as exc:
            raise AutentiqueDispatchError("Resposta inválida da Autentique.", ambiguous=response.status_code >= 500) from exc
        if not 200 <= response.status_code < 300 or not isinstance(body, dict):
            raise AutentiqueDispatchError("A Autentique recusou a operação.", ambiguous=response.status_code >= 500)
        errors = body.get("errors")
        if errors:
            message = errors[0].get("message") if isinstance(errors, list) and isinstance(errors[0], dict) else None
            raise AutentiqueDispatchError(str(message or "A Autentique recusou a operação.")[:300], ambiguous=False)
        data = body.get("data")
        if not isinstance(data, dict):
            raise AutentiqueDispatchError("Resposta inválida da Autentique.", ambiguous=True)
        return data


CREATE_DOCUMENT = """
mutation CreateLexFlowDocument($document: DocumentInput!, $signers: [SignerInput!]!, $file: Upload!, $organization_id: Int!) {
  createDocument(document: $document, signers: $signers, file: $file, organization_id: $organization_id) {
    id
    signatures { public_id }
  }
}
"""

GET_DOCUMENT = """
query LexFlowSignedDocument($id: String!) {
  document(id: $id) {
    id
    files { signed pades }
  }
}
"""


async def submit_autentique_document(
    *,
    access_token: str,
    account_reference: str,
    local_envelope_id: str,
    filename: str,
    pdf: bytes,
    pdf_sha256: str,
    signer: AutentiqueSigner,
    expires_at: datetime | None,
    client: AutentiqueClient | None = None,
) -> AutentiqueSubmission:
    if len(pdf) > MAX_SIGNED_PDF_BYTES or not pdf.startswith(b"%PDF-"):
        raise ValueError("signature source must be a PDF up to 20 MB")
    if hashlib.sha256(pdf).hexdigest() != pdf_sha256:
        raise ValueError("signature source hash mismatch")
    transport = client or AutentiqueClient(access_token)
    if not account_reference.isdecimal():
        raise ValueError("Autentique organization id must be numeric")
    document: dict[str, Any] = {
        "name": filename,
        "message": f"Documento enviado com referência LexFlow {local_envelope_id}",
        "qualified": signer.authentication == "icp_brasil",
    }
    if expires_at:
        document["deadline_at"] = expires_at.isoformat()
    signer_body: dict[str, Any] = {"name": signer.name, "email": signer.email, "action": "SIGN"}
    if signer.cpf:
        signer_body["configs"] = {"cpf": signer.cpf}
    data = await transport.graphql(
        CREATE_DOCUMENT,
        {"document": document, "signers": [signer_body], "organization_id": int(account_reference)},
        file=(filename, pdf),
    )
    created = data.get("createDocument")
    document_id = created.get("id") if isinstance(created, dict) else None
    signatures = created.get("signatures") if isinstance(created, dict) else None
    signer_id = signatures[0].get("public_id") if isinstance(signatures, list) and signatures and isinstance(signatures[0], dict) else None
    if not isinstance(document_id, str) or not document_id:
        raise AutentiqueDispatchError("Autentique não retornou o identificador do documento.", ambiguous=True)
    return AutentiqueSubmission(document_id=document_id, signer_id=signer_id if isinstance(signer_id, str) else None)


def parse_autentique_webhook(raw: bytes) -> AutentiqueWebhook:
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid Autentique webhook JSON") from exc
    event = payload.get("event") if isinstance(payload, dict) else None
    if not isinstance(event, dict):
        raise ValueError("invalid Autentique event")
    event_id, event_name = event.get("id"), event.get("type")
    organization = event.get("organization")
    account = organization.get("id") if isinstance(organization, dict) else organization
    data = event.get("data")
    if not isinstance(data, dict):
        raise ValueError("invalid Autentique event data")
    # Current Autentique webhooks document exactly two resource shapes:
    # document events wrap a document object, while signature events place the
    # signature fields directly in data and use object="signature".
    raw_object = data.get("object")
    document_shape = isinstance(raw_object, dict)
    signature_shape = raw_object == "signature"
    if not document_shape and not signature_shape:
        raise ValueError("invalid Autentique event object")
    if event_name == "document.finished" and not document_shape:
        raise ValueError("invalid Autentique document event")
    if event_name == "signature.rejected" and not signature_shape:
        raise ValueError("invalid Autentique signature event")
    object_data = raw_object if document_shape else data
    document_id = object_data.get("id") if document_shape else None
    if isinstance(event_name, str) and event_name.startswith("signature."):
        document_id = object_data.get("document") or object_data.get("document_id")
        if isinstance(document_id, dict):
            document_id = document_id.get("id")
    account = str(account) if isinstance(account, str) or (isinstance(account, int) and not isinstance(account, bool)) else None
    if not all(isinstance(value, str) and 0 < len(value) <= 256 for value in (event_id, event_name, account)):
        raise ValueError("missing Autentique webhook identity")
    if document_id is not None and (not isinstance(document_id, str) or not document_id or len(document_id) > 512):
        raise ValueError("invalid Autentique document identity")
    mapped = {
        "document.finished": "envelope.signed",
        "signature.rejected": "envelope.declined",
    }.get(event_name)
    return AutentiqueWebhook(account, event_id, event_name, mapped, document_id)


def _signed_url(document: dict) -> str | None:
    files = document.get("files") if isinstance(document, dict) else None
    if not isinstance(files, dict):
        return None
    return next((value for value in (files.get("pades"), files.get("signed")) if isinstance(value, str) and value), None)


async def fetch_autentique_signed_pdf(
    *, access_token: str, account_reference: str, document_id: str, client: AutentiqueClient | None = None
) -> bytes:
    transport = client or AutentiqueClient(access_token)
    data = await transport.graphql(GET_DOCUMENT, {"id": document_id})
    url = _signed_url(data.get("document"))
    if not url:
        raise AutentiqueDispatchError("Arquivo assinado ainda não está disponível.", ambiguous=True)
    parsed = urlsplit(url)
    allowed = bool(
        parsed.hostname == "storage.googleapis.com"
        or (parsed.hostname and (parsed.hostname == "autentique.com.br" or parsed.hostname.endswith(".autentique.com.br")))
    )
    if parsed.scheme != "https" or not allowed or parsed.username or parsed.password or parsed.port not in {None, 443}:
        raise AutentiqueDispatchError("A Autentique retornou um endereço de download não autorizado.", ambiguous=True)
    async with httpx.AsyncClient(timeout=httpx.Timeout(30, connect=5), follow_redirects=False) as http:
        async with http.stream("GET", url, headers={"Accept": "application/pdf"}) as response:
            if not 200 <= response.status_code < 300:
                raise AutentiqueDispatchError("Arquivo assinado ainda não está disponível.", ambiguous=True)
            content = bytearray()
            async for chunk in response.aiter_bytes():
                content.extend(chunk)
                if len(content) > MAX_SIGNED_PDF_BYTES:
                    raise AutentiqueDispatchError("PDF assinado excede o limite permitido.", ambiguous=False)
    result = bytes(content)
    if not result.startswith(b"%PDF-"):
        raise AutentiqueDispatchError("A Autentique retornou arquivo assinado inválido.", ambiguous=False)
    return result
