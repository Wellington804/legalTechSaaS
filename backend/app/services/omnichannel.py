"""Small, fail-closed bridge from authenticated provider events to case messages."""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass
from email.utils import parseaddr
from html.parser import HTMLParser

import httpx
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_account_token
from app.models.engagement import CaseMessage, CommunicationInboxItem
from app.models.workspace import WorkspaceCase, WorkspaceClient
from app.services.audit_service import AuditService
from app.services.evolution_manager import phone_from_jid


MAX_INBOUND_BODY = 8_000
MAX_RESEND_RESPONSE = 2 * 1024 * 1024
EMAIL_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{20,128}$")


class InboundProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class InboundMessage:
    provider_message_id: str
    sender: str
    body: str
    subject: str | None = None
    has_attachments: bool = False
    body_truncated: bool = False


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        value = data.strip()
        if value:
            self.parts.append(value)


def _bounded_text(value: str) -> tuple[str, bool]:
    value = value.replace("\x00", "").strip()
    return value[:MAX_INBOUND_BODY], len(value) > MAX_INBOUND_BODY


def event_digest(provider: str, event_identity: str) -> str:
    return hashlib.sha256(f"{provider}:{event_identity}".encode()).hexdigest()


def match_status(client_count: int, case_count: int) -> str:
    if client_count == 1 and case_count == 1:
        return "linked"
    if client_count > 1 or case_count > 1:
        return "ambiguous"
    return "unmatched"


def resend_recipient_token(recipients: object, domain: str | None) -> str | None:
    expected_domain = (domain or "").strip().casefold().lstrip("@")
    if not expected_domain or not isinstance(recipients, list) or len(recipients) > 20:
        return None
    for value in recipients:
        if not isinstance(value, str):
            continue
        _, address = parseaddr(value)
        local, separator, address_domain = address.strip().rpartition("@")
        if separator and address_domain.casefold() == expected_domain and local.startswith("inbox+"):
            token = local.removeprefix("inbox+")
            if EMAIL_TOKEN_RE.fullmatch(token):
                return token
    return None


def resend_sender(value: object) -> str | None:
    if not isinstance(value, str) or len(value) > 500:
        return None
    _, address = parseaddr(value)
    address = address.strip().casefold()
    return address if re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", address) else None


def _direct_whatsapp_phone(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    if "@" in value and not value.endswith(("@s.whatsapp.net", "@c.us")):
        return None
    return phone_from_jid(value)


def extract_whatsapp_message(payload: dict) -> InboundMessage | None:
    if payload.get("event") != "Message":
        return None
    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    info = data.get("Info")
    if isinstance(info, dict):
        message = data.get("Message")
        from_me = info.get("IsFromMe")
        is_group = info.get("IsGroup")
        provider_id = info.get("ID")
        sender_candidates = (info.get("Sender"), info.get("Chat"), info.get("SenderAlt"))
    else:
        key = data.get("key")
        message = data.get("message")
        if not isinstance(key, dict):
            return None
        from_me = key.get("fromMe")
        is_group = False
        provider_id = key.get("id")
        sender_candidates = (key.get("remoteJid"),)
    if not isinstance(message, dict) or from_me is not False or is_group is True:
        return None
    sender = next((phone for value in sender_candidates if (phone := _direct_whatsapp_phone(value))), None)
    if not sender or not isinstance(provider_id, str) or not provider_id or len(provider_id) > 255:
        return None

    text_value = message.get("conversation")
    if not isinstance(text_value, str):
        extended = message.get("extendedTextMessage")
        text_value = extended.get("text") if isinstance(extended, dict) else None
    media_keys = ("imageMessage", "videoMessage", "audioMessage", "documentMessage", "stickerMessage")
    media = next((message.get(name) for name in media_keys if isinstance(message.get(name), dict)), None)
    if not isinstance(text_value, str) and isinstance(media, dict):
        text_value = media.get("caption")
    has_attachments = media is not None
    if not isinstance(text_value, str) or not text_value.strip():
        if not has_attachments:
            return None
        text_value = "[Anexo recebido pelo WhatsApp; revise o arquivo no provedor.]"
    body, truncated = _bounded_text(text_value)
    return InboundMessage(provider_id, sender, body, has_attachments=has_attachments, body_truncated=truncated)


async def resolve_inbound_email_tenant(db: AsyncSession, token: str) -> str | None:
    row = (
        await db.execute(
            text("SELECT tenant_id FROM public.tenant_channel_email_inbound_identity(:token_hash)"),
            {"token_hash": hash_account_token(token)},
        )
    ).first()
    return str(row[0]) if row else None


async def fetch_resend_received_email(email_id: str) -> InboundMessage:
    if not settings.RESEND_API_KEY:
        raise InboundProviderError("resend_not_configured")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"https://api.resend.com/emails/receiving/{email_id}",
                headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
            )
    except (httpx.TimeoutException, httpx.NetworkError) as exc:
        raise InboundProviderError("resend_unavailable") from exc
    if response.status_code == 429 or response.status_code >= 500:
        raise InboundProviderError("resend_unavailable")
    if response.status_code >= 400 or len(response.content) > MAX_RESEND_RESPONSE:
        raise InboundProviderError("resend_rejected")
    try:
        data = response.json()
    except ValueError as exc:
        raise InboundProviderError("resend_invalid_response") from exc
    sender = resend_sender(data.get("from")) if isinstance(data, dict) else None
    if not sender:
        raise InboundProviderError("resend_invalid_response")
    body = data.get("text")
    if not isinstance(body, str) or not body.strip():
        html = data.get("html")
        if isinstance(html, str):
            parser = _TextExtractor()
            parser.feed(html[:MAX_RESEND_RESPONSE])
            body = "\n".join(parser.parts)
    if not isinstance(body, str) or not body.strip():
        body = "[E-mail recebido sem corpo textual.]"
    bounded, truncated = _bounded_text(body)
    attachments = data.get("attachments")
    return InboundMessage(
        provider_message_id=email_id,
        sender=sender,
        subject=str(data.get("subject") or "")[:500] or None,
        body=bounded,
        has_attachments=bool(isinstance(attachments, list) and attachments),
        body_truncated=truncated,
    )


async def _matches(
    db: AsyncSession, tenant_id: str, channel: str, sender: str
) -> tuple[list[WorkspaceClient], list[WorkspaceCase]]:
    contact_clause = (
        func.lower(WorkspaceClient.email) == sender
        if channel == "email"
        else WorkspaceClient.phone == sender
    )
    clients = list(
        (
            await db.scalars(
                select(WorkspaceClient).where(
                    WorkspaceClient.tenant_id == tenant_id,
                    WorkspaceClient.stage != "inactive",
                    WorkspaceClient.archived_at.is_(None),
                    contact_clause,
                )
            )
        ).all()
    )
    if not clients:
        return [], []
    cases = list(
        (
            await db.scalars(
                select(WorkspaceCase).where(
                    WorkspaceCase.tenant_id == tenant_id,
                    WorkspaceCase.client_id.in_([client.id for client in clients]),
                    WorkspaceCase.archived_at.is_(None),
                    WorkspaceCase.status.in_({"open", "paused"}),
                )
            )
        ).all()
    )
    return clients, cases


def _case_message(item: CommunicationInboxItem, client_id: str, case_id: str) -> CaseMessage:
    request_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"lexflow:{item.provider}:{item.event_digest}"))
    return CaseMessage(
        id=str(uuid.uuid4()),
        tenant_id=item.tenant_id,
        case_id=case_id,
        client_id=client_id,
        request_id=request_id,
        channel=item.channel,
        direction="inbound",
        body=item.body,
    )


async def ingest_inbound_message(
    db: AsyncSession,
    *,
    tenant_id: str,
    channel: str,
    provider: str,
    event_identity: str,
    message: InboundMessage,
) -> tuple[CommunicationInboxItem, bool]:
    digest = event_digest(provider, event_identity)
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:event_digest, 0))"),
        {"event_digest": digest},
    )
    existing = await db.scalar(
        select(CommunicationInboxItem).where(
            CommunicationInboxItem.tenant_id == tenant_id,
            CommunicationInboxItem.provider == provider,
            CommunicationInboxItem.event_digest == digest,
        )
    )
    if existing:
        return existing, True

    clients, cases = await _matches(db, tenant_id, channel, message.sender)
    status = match_status(len(clients), len(cases))
    item = CommunicationInboxItem(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        channel=channel,
        provider=provider,
        event_digest=digest,
        provider_message_hash=hash_account_token(message.provider_message_id),
        sender_address=message.sender,
        subject=message.subject,
        body=message.body,
        body_truncated=message.body_truncated,
        has_attachments=message.has_attachments,
        status=status,
        matched_client_id=clients[0].id if len(clients) == 1 else None,
    )
    if status == "linked":
        case_message = _case_message(item, clients[0].id, cases[0].id)
        item.linked_case_id = cases[0].id
        item.linked_message_id = case_message.id
        db.add(case_message)
    db.add(item)
    await AuditService.log_action(
        db,
        tenant_id,
        None,
        "INBOUND_COMMUNICATION_RECEIVED",
        "communication_inbox",
        item.id,
        {"channel": channel, "match_status": status},
    )
    return item, False


def create_linked_case_message(item: CommunicationInboxItem, client_id: str, case_id: str) -> CaseMessage:
    return _case_message(item, client_id, case_id)
