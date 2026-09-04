"""Only persisted, case-authorized messages and revocable portal access."""
import asyncio
import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import PurePath
from typing import Literal

import jwt
from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import CurrentUser, _set_tenant_context, ensure_tenant_write_access, require_trusted_origin
from app.core.security import decrypt_mfa_secret, encrypt_mfa_secret, hash_account_token
from app.models.engagement import CaseMessage, CommunicationInboxItem, PortalChecklist, PortalFolderShare, PortalGrant, TenantChannel
from app.models.notification import NotificationDelivery
from app.models.tenant import Tenant
from app.models.workspace import WorkspaceCase, WorkspaceClient, WorkspaceDocument, WorkspaceDocumentFolder, WorkspaceDocumentUpload, WorkspaceDocumentVersion
from app.services.audit_service import AuditService
from app.services.notification_service import create_or_get_delivery
from app.services.ai_provider import ai_available
from app.services.push_service import enqueue_user_push
from app.services.workspace_service import ALLOWED_UPLOAD_TYPES, MAX_UPLOAD_BYTES, get_case, get_client, get_document, require_role, read_validated_upload, ensure_document_storage_capacity
from app.services.document_storage import create_download_url, create_upload_url, enabled as r2_enabled, quarantine_key
from app.services.document_tasks import process_upload
from app.services import evolution_manager
from app.services.omnichannel import create_linked_case_message
from app.api.v1.endpoints.notifications import enforce_dispatch_rate_limit

router = APIRouter()
portal_router = APIRouter()
PORTAL_COOKIE = "lexflow_portal"


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class MessageInput(StrictInput):
    request_id: uuid.UUID
    body: str = Field(min_length=1, max_length=8000)
    channel: Literal["portal", "email", "whatsapp"] = "portal"


class ChecklistInput(StrictInput):
    title: str = Field(min_length=2, max_length=200)
    document_id: str | None = Field(default=None, max_length=64)


class TokenInput(StrictInput):
    token: str = Field(min_length=20, max_length=2048)


class FolderShareInput(StrictInput):
    grant_id: str = Field(min_length=1, max_length=64)
    folder_id: str = Field(min_length=1, max_length=64)
    can_upload: bool = False


class PortalInviteInput(StrictInput):
    access_days: int = Field(default=7, ge=1, le=30)


class PortalUploadInput(StrictInput):
    folder_id: str = Field(min_length=1, max_length=64)
    filename: str = Field(min_length=1, max_length=255)
    size: int = Field(gt=0, le=25 * 1024 * 1024)
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class InboxLinkInput(StrictInput):
    case_id: str = Field(min_length=1, max_length=64)
    expected_revision: int = Field(ge=1)
    reason: str = Field(min_length=3, max_length=500)


class InboxReviewInput(StrictInput):
    expected_revision: int = Field(ge=1)
    reason: str = Field(min_length=3, max_length=500)


class InboundEmailInput(StrictInput):
    rotate: bool = False


def message_json(message, delivery=None):
    return {"id": message.id, "case_id": message.case_id, "body": message.body, "channel": message.channel,
            "direction": message.direction, "created_at": message.created_at,
            "status": delivery.status if delivery else "recorded", "error_code": delivery.error_code if delivery else None,
            "read_at": getattr(message, "read_at", None)}


def inbox_json(item: CommunicationInboxItem):
    return {
        "id": item.id,
        "channel": item.channel,
        "sender": item.sender_address,
        "subject": item.subject,
        "body": item.body,
        "body_truncated": item.body_truncated,
        "has_attachments": item.has_attachments,
        "status": item.status,
        "matched_client_id": item.matched_client_id,
        "linked_case_id": item.linked_case_id,
        "received_at": item.received_at,
        "revision": item.revision,
    }


async def audit(db, user, action, resource_id):
    await AuditService.log_action(db, user.tenant_id, user.id, action, "case_communication", resource_id)


def channel_json(row):
    whatsapp_ready = bool(row and row.whatsapp_enabled and row.whatsapp_connection_state == "connected"
                            and row.evolution_instance_id_encrypted and row.evolution_api_key_encrypted)
    return {"email_enabled": bool(row and row.email_enabled), "whatsapp_enabled": whatsapp_ready,
            "ai_enabled": bool(row and row.ai_enabled),
            "credentials_configured": bool(row and row.evolution_instance_id_encrypted and row.evolution_api_key_encrypted and row.evolution_token_encrypted),
            "email_provider_ready": bool(settings.RESEND_ENABLED and settings.RESEND_API_KEY and not settings.NOTIFICATIONS_DRY_RUN),
            "whatsapp_provider_ready": evolution_manager.configured(),
            "ai_provider_ready": ai_available(),
            "datajud_ready": bool(settings.DATAJUD_ENABLED and settings.DATAJUD_API_KEY)}


def whatsapp_json(row):
    configured = bool(row and row.evolution_instance_id_encrypted and row.evolution_instance_id_hash
                      and row.evolution_api_key_encrypted and row.evolution_token_encrypted)
    status_value = row.whatsapp_connection_state if row else "disconnected"
    if not configured and status_value == "connected":
        status_value = "disconnected"
    return {
        "status": status_value,
        "connected": bool(configured and row.whatsapp_enabled and status_value == "connected"),
        "number": row.whatsapp_number if row and status_value == "connected" else None,
        "last_checked_at": row.whatsapp_last_checked_at if row else None,
    }


def _provider_unavailable():
    raise HTTPException(503, "Não foi possível acessar o serviço do WhatsApp agora. Tente novamente em instantes.")


def _instance_token(row: TenantChannel) -> str:
    try:
        return decrypt_mfa_secret(row.evolution_api_key_encrypted or "")
    except RuntimeError:
        _provider_unavailable()


def _instance_id(row: TenantChannel) -> str:
    try:
        return decrypt_mfa_secret(row.evolution_instance_id_encrypted or "")
    except RuntimeError:
        _provider_unavailable()


async def _refresh_whatsapp(db: AsyncSession, row: TenantChannel) -> bool:
    if not evolution_manager.configured() or not row.evolution_instance_id_encrypted or not row.evolution_api_key_encrypted:
        return False
    previous = row.whatsapp_connection_state
    try:
        provider_status = await evolution_manager.status(_instance_token(row))
        connected = provider_status["connected"] and provider_status["logged_in"]
        if connected:
            row.whatsapp_connection_state = "connected"
            row.whatsapp_enabled = True
            row.whatsapp_number = await evolution_manager.phone_number(_instance_id(row))
        elif previous != "pending":
            row.whatsapp_connection_state = "disconnected"
        row.whatsapp_last_checked_at = datetime.now(timezone.utc)
        if previous != row.whatsapp_connection_state:
            action = "WHATSAPP_CONNECTED" if row.whatsapp_connection_state == "connected" else "WHATSAPP_DISCONNECTED"
            await AuditService.log_action(db, row.tenant_id, None, action, "case_communication", row.tenant_id)
        await db.commit()
        return True
    except evolution_manager.EvolutionProviderError:
        return False


@router.get("/channels")
async def channels(user: CurrentUser, db: AsyncSession = Depends(get_db)):
    row = await db.get(TenantChannel, user.tenant_id)
    verified = await _refresh_whatsapp(db, row) if row else False
    return {"whatsapp": {**whatsapp_json(row), "verification_unavailable": bool(row and row.evolution_instance_id_encrypted and not verified)}}


def _inbound_email_address(row: TenantChannel | None) -> str | None:
    domain = (settings.RESEND_INBOUND_DOMAIN or "").strip().casefold().lstrip("@")
    if not domain or not row or not row.email_inbound_enabled or not row.email_inbound_token_encrypted:
        return None
    try:
        token = decrypt_mfa_secret(row.email_inbound_token_encrypted)
    except RuntimeError:
        return None
    return f"inbox+{token}@{domain}"


@router.get("/inbox")
async def list_inbox(
    user: CurrentUser,
    status_filter: Literal["open", "linked", "dismissed", "all"] = "open",
    db: AsyncSession = Depends(get_db),
):
    require_role(user, {"admin", "partner"})
    query = select(CommunicationInboxItem).where(
        CommunicationInboxItem.tenant_id == user.tenant_id
    )
    if status_filter == "open":
        query = query.where(CommunicationInboxItem.status.in_({"unmatched", "ambiguous"}))
    elif status_filter != "all":
        query = query.where(CommunicationInboxItem.status == status_filter)
    rows = (
        await db.scalars(query.order_by(CommunicationInboxItem.received_at.desc()).limit(100))
    ).all()
    return {"items": [inbox_json(item) for item in rows]}


@router.get("/inbox/email-address")
async def inbound_email_address(
    response: Response, user: CurrentUser, db: AsyncSession = Depends(get_db)
):
    require_role(user, {"admin", "partner"})
    row = await db.get(TenantChannel, user.tenant_id)
    response.headers["Cache-Control"] = "no-store"
    return {
        "configured": bool(_inbound_email_address(row)),
        "address": _inbound_email_address(row),
        "provider_ready": bool(
            settings.RESEND_ENABLED
            and settings.RESEND_API_KEY
            and settings.RESEND_WEBHOOK_SECRET
            and settings.RESEND_INBOUND_DOMAIN
            and not settings.NOTIFICATIONS_DRY_RUN
        ),
    }


@router.post("/inbox/email-address")
async def enable_inbound_email(
    response: Response,
    user: CurrentUser,
    body: InboundEmailInput | None = None,
    db: AsyncSession = Depends(get_db),
):
    require_role(user, {"admin", "partner"})
    await ensure_tenant_write_access(db, user.tenant_id)
    if not (
        settings.RESEND_ENABLED
        and settings.RESEND_API_KEY
        and settings.RESEND_WEBHOOK_SECRET
        and settings.RESEND_INBOUND_DOMAIN
        and not settings.NOTIFICATIONS_DRY_RUN
    ):
        raise HTTPException(503, "Recebimento de e-mail ainda não está configurado na VPS.")
    await db.scalar(select(Tenant).where(Tenant.id == user.tenant_id).with_for_update())
    row = await db.get(TenantChannel, user.tenant_id)
    if not row:
        row = TenantChannel(tenant_id=user.tenant_id)
        db.add(row)
    rotate = bool(body and body.rotate)
    if rotate or not row.email_inbound_token_encrypted or not row.email_inbound_token_hash:
        token = secrets.token_urlsafe(24)
        row.email_inbound_token_encrypted = encrypt_mfa_secret(token)
        row.email_inbound_token_hash = hash_account_token(token)
    row.email_inbound_enabled = True
    await audit(db, user, "INBOUND_EMAIL_ADDRESS_ROTATED" if rotate else "INBOUND_EMAIL_ADDRESS_ENABLED", user.tenant_id)
    await db.commit()
    response.headers["Cache-Control"] = "no-store"
    return {"configured": True, "address": _inbound_email_address(row), "provider_ready": True}


@router.delete("/inbox/email-address", status_code=204)
async def disable_inbound_email(user: CurrentUser, db: AsyncSession = Depends(get_db)):
    require_role(user, {"admin", "partner"})
    await ensure_tenant_write_access(db, user.tenant_id)
    row = await db.scalar(
        select(TenantChannel).where(TenantChannel.tenant_id == user.tenant_id).with_for_update()
    )
    if row:
        row.email_inbound_enabled = False
        row.email_inbound_token_encrypted = None
        row.email_inbound_token_hash = None
        await audit(db, user, "INBOUND_EMAIL_ADDRESS_DISABLED", user.tenant_id)
        await db.commit()
    return Response(status_code=204)


@router.post("/inbox/{item_id}/link")
async def link_inbox_item(
    item_id: str,
    body: InboxLinkInput,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    require_role(user, {"admin", "partner"})
    await ensure_tenant_write_access(db, user.tenant_id)
    item = await db.scalar(
        select(CommunicationInboxItem).where(
            CommunicationInboxItem.id == item_id,
            CommunicationInboxItem.tenant_id == user.tenant_id,
        ).with_for_update()
    )
    if not item:
        raise HTTPException(404, "Mensagem recebida não encontrada.")
    if item.status not in {"unmatched", "ambiguous"}:
        raise HTTPException(409, "Esta mensagem já foi revisada.")
    if item.revision != body.expected_revision:
        raise HTTPException(409, "A mensagem foi alterada. Atualize a caixa de entrada.")
    case = await get_case(db, user, body.case_id)
    if case.archived_at or case.status not in {"open", "paused"}:
        raise HTTPException(409, "Selecione um processo ativo.")
    message = create_linked_case_message(item, case.client_id, case.id)
    db.add(message)
    item.matched_client_id = case.client_id
    item.linked_case_id = case.id
    item.linked_message_id = message.id
    item.status = "linked"
    item.reviewed_by_user_id = user.id
    item.reviewed_at = datetime.now(timezone.utc)
    item.revision += 1
    await AuditService.log_action(
        db,
        user.tenant_id,
        user.id,
        "INBOUND_COMMUNICATION_LINKED",
        "communication_inbox",
        item.id,
        {"case_id": case.id, "reason": body.reason},
    )
    await db.commit()
    return inbox_json(item)


@router.post("/inbox/{item_id}/dismiss")
async def dismiss_inbox_item(
    item_id: str,
    body: InboxReviewInput,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    require_role(user, {"admin", "partner"})
    await ensure_tenant_write_access(db, user.tenant_id)
    item = await db.scalar(
        select(CommunicationInboxItem).where(
            CommunicationInboxItem.id == item_id,
            CommunicationInboxItem.tenant_id == user.tenant_id,
        ).with_for_update()
    )
    if not item:
        raise HTTPException(404, "Mensagem recebida não encontrada.")
    if item.status not in {"unmatched", "ambiguous"}:
        raise HTTPException(409, "Esta mensagem já foi revisada.")
    if item.revision != body.expected_revision:
        raise HTTPException(409, "A mensagem foi alterada. Atualize a caixa de entrada.")
    item.status = "dismissed"
    item.reviewed_by_user_id = user.id
    item.reviewed_at = datetime.now(timezone.utc)
    item.revision += 1
    await AuditService.log_action(
        db,
        user.tenant_id,
        user.id,
        "INBOUND_COMMUNICATION_DISMISSED",
        "communication_inbox",
        item.id,
        {"reason": body.reason},
    )
    await db.commit()
    return inbox_json(item)


@router.post("/whatsapp/connect")
async def connect_whatsapp(response: Response, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    require_role(user, {"admin", "partner"})
    await ensure_tenant_write_access(db, user.tenant_id)
    if not evolution_manager.configured():
        _provider_unavailable()
    await db.scalar(select(Tenant).where(Tenant.id == user.tenant_id).with_for_update())
    row = await db.get(TenantChannel, user.tenant_id)
    if not row:
        row = TenantChannel(tenant_id=user.tenant_id)
        db.add(row)
    if not row.evolution_instance_id_encrypted or not row.evolution_instance_id_hash or not row.evolution_api_key_encrypted or not row.evolution_token_encrypted:
        instance_id = str(uuid.uuid4())
        token = secrets.token_urlsafe(48)
        encrypted = encrypt_mfa_secret(token)
        row.evolution_instance_id_encrypted = encrypt_mfa_secret(instance_id)
        row.evolution_instance_id_hash = hash_account_token(instance_id)
        row.evolution_api_key_encrypted = encrypted
        row.evolution_token_encrypted = encrypted
    else:
        instance_id = _instance_id(row)
        token = _instance_token(row)
    row.whatsapp_enabled = True
    row.whatsapp_connection_state = "pending"
    await audit(db, user, "WHATSAPP_CONNECTION_STARTED", user.tenant_id)
    await db.commit()
    try:
        await evolution_manager.ensure_instance(instance_id, token)
        qr = await evolution_manager.connect(token)
    except evolution_manager.EvolutionProviderError:
        await _set_tenant_context(db, user.tenant_id)
        row.whatsapp_connection_state = "disconnected"
        await db.commit()
        _provider_unavailable()
    await _set_tenant_context(db, user.tenant_id)
    row.whatsapp_last_checked_at = datetime.now(timezone.utc)
    await db.commit()
    response.headers["Cache-Control"] = "no-store"
    return {"whatsapp": whatsapp_json(row), "qr_code": qr}


@router.get("/whatsapp/qr")
async def whatsapp_qr(response: Response, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    require_role(user, {"admin", "partner"})
    row = await db.get(TenantChannel, user.tenant_id)
    if not row or not row.evolution_api_key_encrypted or row.whatsapp_connection_state != "pending":
        raise HTTPException(409, "Inicie a conexão do WhatsApp antes de solicitar o QR Code.")
    try:
        qr = await evolution_manager.qr_code(_instance_token(row))
    except evolution_manager.EvolutionProviderError:
        _provider_unavailable()
    response.headers["Cache-Control"] = "no-store"
    return {"qr_code": qr}


@router.post("/whatsapp/reconnect")
async def reconnect_whatsapp(user: CurrentUser, db: AsyncSession = Depends(get_db)):
    require_role(user, {"admin", "partner"})
    await ensure_tenant_write_access(db, user.tenant_id)
    row = await db.get(TenantChannel, user.tenant_id)
    if not row or not row.evolution_api_key_encrypted:
        raise HTTPException(409, "Conecte o WhatsApp antes de tentar reconectar.")
    try:
        await evolution_manager.reconnect(_instance_token(row))
    except evolution_manager.EvolutionProviderError:
        _provider_unavailable()
    row.whatsapp_connection_state = "pending"
    row.whatsapp_enabled = True
    await audit(db, user, "WHATSAPP_RECONNECTED", user.tenant_id)
    await db.commit()
    await _refresh_whatsapp(db, row)
    return {"whatsapp": whatsapp_json(row)}


@router.delete("/whatsapp/connection", status_code=204)
async def disconnect_whatsapp(user: CurrentUser, db: AsyncSession = Depends(get_db)):
    require_role(user, {"admin", "partner"})
    await ensure_tenant_write_access(db, user.tenant_id)
    row = await db.get(TenantChannel, user.tenant_id)
    if not row or not row.evolution_api_key_encrypted:
        return Response(status_code=204)
    if row.evolution_instance_id_encrypted:
        try:
            await evolution_manager.delete_instance(_instance_id(row))
        except evolution_manager.EvolutionProviderError:
            _provider_unavailable()
    row.whatsapp_connection_state = "disconnected"
    row.whatsapp_enabled = False
    row.whatsapp_number = None
    row.evolution_instance_id_encrypted = None
    row.evolution_instance_id_hash = None
    row.evolution_api_key_encrypted = None
    row.evolution_token_encrypted = None
    row.whatsapp_last_checked_at = datetime.now(timezone.utc)
    await audit(db, user, "WHATSAPP_DISCONNECTED", user.tenant_id)
    await db.commit()
    return Response(status_code=204)


@router.get("/cases/{case_id}/messages")
async def list_messages(case_id: str, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    await get_case(db, user, case_id)
    rows = (await db.execute(select(CaseMessage, NotificationDelivery).outerjoin(NotificationDelivery, NotificationDelivery.id == CaseMessage.delivery_id).where(
        CaseMessage.tenant_id == user.tenant_id, CaseMessage.case_id == case_id).order_by(CaseMessage.created_at.desc()).limit(100))).all()
    return {"items": [message_json(*row) for row in rows]}


@router.post("/cases/{case_id}/messages", status_code=202)
async def create_message(case_id: str, body: MessageInput, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    require_role(user, {"admin", "partner", "lawyer"})
    await ensure_tenant_write_access(db, user.tenant_id)
    await enforce_dispatch_rate_limit(user)
    # Serializes quota and idempotency checks across concurrent requests.
    tenant = await db.scalar(select(Tenant).where(Tenant.id == user.tenant_id).with_for_update())
    case = await get_case(db, user, case_id)
    client = await get_client(db, user, case.client_id)
    existing = await db.scalar(select(CaseMessage).where(CaseMessage.tenant_id == user.tenant_id, CaseMessage.request_id == str(body.request_id)))
    if existing:
        if (existing.case_id, existing.body, existing.channel) != (case_id, body.body, body.channel):
            raise HTTPException(409, "Identificador já utilizado em outra mensagem.")
        delivery = await db.get(NotificationDelivery, existing.delivery_id) if existing.delivery_id else None
        return message_json(existing, delivery)
    if case.archived_at or client.stage == "inactive":
        raise HTTPException(409, "Caso ou cliente inativo.")
    delivery = None
    row = CaseMessage(id=str(uuid.uuid4()), tenant_id=user.tenant_id, case_id=case_id, client_id=client.id,
                      request_id=str(body.request_id), channel=body.channel, direction="outbound", body=body.body, created_by_user_id=user.id)
    if body.channel != "portal":
        config = await db.get(TenantChannel, user.tenant_id)
        ready = channel_json(config)
        if not ready[f"{body.channel}_enabled"] or not ready[f"{body.channel}_provider_ready"]:
            raise HTTPException(503, "Canal não configurado/habilitado para este escritório.")
        recipient = client.email if body.channel == "email" else client.phone
        if not recipient:
            raise HTTPException(422, "Complete o contato do cliente antes do envio.")
        month = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        count = await db.scalar(select(func.count(NotificationDelivery.id)).where(NotificationDelivery.tenant_id == user.tenant_id, NotificationDelivery.created_at >= month))
        if count >= tenant.quota_messages:
            raise HTTPException(409, "Limite mensal de mensagens atingido.")
        delivery, _ = await create_or_get_delivery(db, tenant_id=user.tenant_id, user_id=user.id, resource_ref=f"case-message:{row.id}", recipient=recipient, channel=body.channel)
        row.delivery_id = delivery.id
    db.add(row)
    await audit(db, user, "CASE_MESSAGE_CREATED", row.id)
    await db.commit()
    if delivery:
        from app.services.tasks import process_notification_task
        try:
            process_notification_task.delay(delivery.id, user.tenant_id)
        except Exception:
            pass  # Durable reconciler republishes queued rows; do not claim external delivery.
    return message_json(row, delivery)


def portal_token(grant, kind, lifetime):
    return jwt.encode({"sub": grant.id, "tenant_id": grant.tenant_id, "aud": "legaltech-portal", "kind": kind,
                       "nonce": secrets.token_urlsafe(32), "exp": datetime.now(timezone.utc) + lifetime}, settings.SECRET_KEY, algorithm="HS256")


async def validate_portal_token(db, token, kind, *, lock=False):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"], audience="legaltech-portal", options={"require": ["exp", "sub", "tenant_id", "kind"]})
        if payload["kind"] != kind or not isinstance(payload["tenant_id"], str):
            raise ValueError
    except (jwt.InvalidTokenError, ValueError, TypeError):
        raise HTTPException(401, "Acesso ao portal inválido ou expirado.")
    await _set_tenant_context(db, payload["tenant_id"])
    query = select(PortalGrant).where(PortalGrant.id == payload["sub"], PortalGrant.tenant_id == payload["tenant_id"])
    grant = await db.scalar(query.with_for_update() if lock else query)
    stored = grant.token_hash if grant and kind == "invite" else grant.session_hash if grant else None
    if not grant or grant.revoked_at or grant.expires_at <= datetime.now(timezone.utc) or not stored or not hmac.compare_digest(stored, hash_account_token(token)):
        raise HTTPException(401, "Acesso ao portal inválido ou expirado.")
    tenant = await db.get(Tenant, grant.tenant_id)
    client = await db.scalar(select(WorkspaceClient).where(WorkspaceClient.id == grant.client_id, WorkspaceClient.tenant_id == grant.tenant_id))
    case = await db.scalar(select(WorkspaceCase).where(WorkspaceCase.id == grant.case_id, WorkspaceCase.tenant_id == grant.tenant_id, WorkspaceCase.client_id == grant.client_id))
    if not tenant or not tenant.is_active or not client or client.stage == "inactive" or not case or case.archived_at:
        raise HTTPException(401, "Acesso ao portal indisponível.")
    return grant, case


@router.post("/cases/{case_id}/portal-invites", status_code=201)
async def invite_portal(case_id: str, user: CurrentUser, body: PortalInviteInput | None = None, db: AsyncSession = Depends(get_db)):
    require_role(user, {"admin", "partner", "lawyer"})
    await ensure_tenant_write_access(db, user.tenant_id)
    case = await get_case(db, user, case_id)
    grant = PortalGrant(id=str(uuid.uuid4()), tenant_id=user.tenant_id, case_id=case.id, client_id=case.client_id,
                        created_by_user_id=user.id, expires_at=datetime.now(timezone.utc) + timedelta(days=body.access_days if body else 7))
    token = portal_token(grant, "invite", timedelta(days=1))
    grant.token_hash = hash_account_token(token)
    db.add(grant)
    await audit(db, user, "PORTAL_INVITATION_CREATED", grant.id)
    await db.commit()
    return {"id": grant.id, "invite_link": f"{settings.FRONTEND_URL.rstrip('/')}/portal#token={token}", "expires_at": datetime.now(timezone.utc) + timedelta(days=1), "access_expires_at": grant.expires_at,
            "notice": "Compartilhe por canal verificado. O link é uma credencial de acesso de uso único, não prova de identidade civil."}


@router.get("/cases/{case_id}/portal-invites")
async def portal_invites(case_id: str, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    await get_case(db, user, case_id)
    rows = (await db.scalars(select(PortalGrant).where(PortalGrant.tenant_id == user.tenant_id, PortalGrant.case_id == case_id).order_by(PortalGrant.created_at.desc()).limit(100))).all()
    return {"items": [{"id": r.id, "expires_at": r.expires_at, "redeemed_at": r.redeemed_at, "revoked_at": r.revoked_at} for r in rows]}


@router.delete("/portal-invites/{grant_id}", status_code=204)
async def revoke_portal(grant_id: str, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    require_role(user, {"admin", "partner", "lawyer"})
    grant = await db.scalar(select(PortalGrant).where(PortalGrant.id == grant_id, PortalGrant.tenant_id == user.tenant_id).with_for_update())
    if not grant:
        raise HTTPException(404, "Acesso não encontrado.")
    await get_case(db, user, grant.case_id)
    grant.revoked_at = datetime.now(timezone.utc)
    await audit(db, user, "PORTAL_ACCESS_REVOKED", grant.id)
    await db.commit()


@router.get("/cases/{case_id}/folder-shares")
async def list_folder_shares(case_id: str, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    await get_case(db, user, case_id)
    rows = (await db.execute(
        select(PortalFolderShare, WorkspaceDocumentFolder).join(
            WorkspaceDocumentFolder,
            (WorkspaceDocumentFolder.tenant_id == PortalFolderShare.tenant_id) &
            (WorkspaceDocumentFolder.id == PortalFolderShare.folder_id),
        ).where(
            PortalFolderShare.tenant_id == user.tenant_id,
            WorkspaceDocumentFolder.case_id == case_id,
            WorkspaceDocumentFolder.archived_at.is_(None),
            PortalFolderShare.revoked_at.is_(None),
        ).order_by(WorkspaceDocumentFolder.name)
    )).all()
    return {"items": [{"id": share.id, "grant_id": share.grant_id, "folder_id": share.folder_id, "folder_name": folder.name, "can_upload": share.can_upload, "created_at": share.created_at} for share, folder in rows]}


@router.post("/cases/{case_id}/folder-shares", status_code=201)
async def share_case_folder(case_id: str, body: FolderShareInput, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    require_role(user, {"admin", "partner", "lawyer"})
    await ensure_tenant_write_access(db, user.tenant_id)
    case = await get_case(db, user, case_id)
    grant = await db.scalar(select(PortalGrant).where(
        PortalGrant.id == body.grant_id, PortalGrant.tenant_id == user.tenant_id,
        PortalGrant.case_id == case.id, PortalGrant.revoked_at.is_(None), PortalGrant.expires_at > datetime.now(timezone.utc),
    ))
    folder = await db.scalar(select(WorkspaceDocumentFolder).where(
        WorkspaceDocumentFolder.id == body.folder_id, WorkspaceDocumentFolder.tenant_id == user.tenant_id,
        WorkspaceDocumentFolder.case_id == case.id, WorkspaceDocumentFolder.client_id == case.client_id,
        WorkspaceDocumentFolder.archived_at.is_(None),
    ))
    if not grant or not folder:
        raise HTTPException(404, "Convite ou pasta do processo não encontrado.")
    share = await db.scalar(select(PortalFolderShare).where(
        PortalFolderShare.tenant_id == user.tenant_id,
        PortalFolderShare.grant_id == grant.id,
        PortalFolderShare.folder_id == folder.id,
    ).with_for_update())
    if share:
        share.can_upload = body.can_upload
        share.revoked_at = None
    else:
        share = PortalFolderShare(tenant_id=user.tenant_id, grant_id=grant.id, folder_id=folder.id, can_upload=body.can_upload, created_by_user_id=user.id)
        db.add(share)
        await db.flush()
    await AuditService.log_action(db, user.tenant_id, user.id, "PORTAL_FOLDER_SHARED", "workspace_document_folders", folder.id, {"grant_id": grant.id, "can_upload": body.can_upload})
    await db.commit()
    return {"id": share.id, "grant_id": grant.id, "folder_id": folder.id, "folder_name": folder.name, "can_upload": share.can_upload}


@router.delete("/folder-shares/{share_id}", status_code=204)
async def revoke_folder_share(share_id: str, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    require_role(user, {"admin", "partner", "lawyer"})
    share = await db.scalar(select(PortalFolderShare).where(
        PortalFolderShare.id == share_id, PortalFolderShare.tenant_id == user.tenant_id,
    ).with_for_update())
    if not share:
        raise HTTPException(404, "Compartilhamento não encontrado.")
    grant = await db.scalar(select(PortalGrant).where(PortalGrant.id == share.grant_id, PortalGrant.tenant_id == user.tenant_id))
    await get_case(db, user, grant.case_id if grant else "")
    share.revoked_at = datetime.now(timezone.utc)
    await AuditService.log_action(db, user.tenant_id, user.id, "PORTAL_FOLDER_SHARE_REVOKED", "workspace_document_folders", share.folder_id, {"grant_id": share.grant_id})
    await db.commit()


@router.get("/cases/{case_id}/checklist")
async def case_checklist(case_id: str, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    await get_case(db, user, case_id)
    rows = (await db.scalars(select(PortalChecklist).where(PortalChecklist.tenant_id == user.tenant_id, PortalChecklist.case_id == case_id).order_by(PortalChecklist.created_at).limit(100))).all()
    return {"items": rows}


@router.post("/cases/{case_id}/checklist", status_code=201)
async def add_checklist(case_id: str, body: ChecklistInput, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    require_role(user, {"admin", "partner", "lawyer"})
    await ensure_tenant_write_access(db, user.tenant_id)
    await get_case(db, user, case_id)
    if body.document_id:
        document = await get_document(db, user, body.document_id)
        if document.case_id != case_id:
            raise HTTPException(422, "Documento não pertence ao caso.")
    item = PortalChecklist(tenant_id=user.tenant_id, case_id=case_id, title=body.title, document_id=body.document_id)
    db.add(item)
    await db.flush()
    await audit(db, user, "PORTAL_CHECKLIST_CREATED", item.id)
    await db.commit()
    return {"id": item.id, "title": item.title, "document_id": item.document_id}


def portal_origin(request):
    if request.method not in {"GET", "HEAD", "OPTIONS"} and not request.headers.get("Origin"):
        raise HTTPException(403, "Origem obrigatória.")
    require_trusted_origin(request)


@portal_router.post("/redeem")
async def redeem(body: TokenInput, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    portal_origin(request)
    grant, _ = await validate_portal_token(db, body.token, "invite", lock=True)
    if grant.redeemed_at:
        raise HTTPException(401, "Link já utilizado. Solicite outro acesso ao escritório.")
    token = portal_token(grant, "session", timedelta(hours=8))
    grant.redeemed_at = datetime.now(timezone.utc)
    grant.session_hash = hash_account_token(token)
    await AuditService.log_action(db, grant.tenant_id, None, "PORTAL_ACCESS_REDEEMED", "portal_grant", grant.id)
    await db.commit()
    response.set_cookie(PORTAL_COOKIE, token, max_age=28800, httponly=True, secure=settings.COOKIE_SECURE, samesite="lax", path="/api/v1/client-portal")
    return {"authenticated": True}


async def portal_session(request: Request, db: AsyncSession = Depends(get_db)):
    portal_origin(request)
    return await validate_portal_token(db, request.cookies.get(PORTAL_COOKIE, ""), "session")


async def portal_write_session(request: Request, db: AsyncSession = Depends(get_db)):
    portal_origin(request)
    return await validate_portal_token(db, request.cookies.get(PORTAL_COOKIE, ""), "session", lock=True)


async def portal_folder_ids(db: AsyncSession, grant: PortalGrant, *, upload: bool = False) -> tuple[set[str], list[WorkspaceDocumentFolder]]:
    shares = (await db.scalars(select(PortalFolderShare).where(
        PortalFolderShare.tenant_id == grant.tenant_id,
        PortalFolderShare.grant_id == grant.id,
        PortalFolderShare.revoked_at.is_(None),
        PortalFolderShare.can_upload.is_(True) if upload else PortalFolderShare.id.is_not(None),
    ))).all()
    roots = {share.folder_id for share in shares}
    folders = (await db.scalars(select(WorkspaceDocumentFolder).where(
        WorkspaceDocumentFolder.tenant_id == grant.tenant_id,
        WorkspaceDocumentFolder.case_id == grant.case_id,
        WorkspaceDocumentFolder.archived_at.is_(None),
    ).order_by(WorkspaceDocumentFolder.name).limit(500))).all()
    allowed = set(roots)
    changed = True
    while changed:
        changed = False
        for folder in folders:
            if folder.parent_id in allowed and folder.id not in allowed:
                allowed.add(folder.id)
                changed = True
    return allowed, folders


@portal_router.get("")
async def portal_home(session=Depends(portal_session), db: AsyncSession = Depends(get_db)):
    grant, case = session
    messages = (await db.scalars(select(CaseMessage).where(CaseMessage.tenant_id == grant.tenant_id, CaseMessage.case_id == case.id, CaseMessage.channel == "portal").order_by(CaseMessage.created_at.desc()).limit(100))).all()
    checklist = (await db.scalars(select(PortalChecklist).where(PortalChecklist.tenant_id == grant.tenant_id, PortalChecklist.case_id == case.id).limit(100))).all()
    allowed, folders = await portal_folder_ids(db, grant)
    upload_allowed, _ = await portal_folder_ids(db, grant, upload=True)
    documents = (await db.scalars(select(WorkspaceDocument).where(
        WorkspaceDocument.tenant_id == grant.tenant_id,
        WorkspaceDocument.case_id == case.id,
        WorkspaceDocument.folder_id.in_(allowed) if allowed else WorkspaceDocument.id.is_(None),
        WorkspaceDocument.deleted_at.is_(None),
        WorkspaceDocument.archived_at.is_(None),
    ).order_by(WorkspaceDocument.updated_at.desc()).limit(300))).all()
    return {"case": {"title": case.title, "number": case.number, "status": case.status}, "messages": [message_json(m) for m in messages],
            "checklist": [{"id": c.id, "title": c.title, "has_document": bool(c.document_id), "completed_at": c.completed_at} for c in checklist],
            "folders": [{"id": f.id, "parent_id": f.parent_id, "name": f.name, "can_upload": f.id in upload_allowed} for f in folders if f.id in allowed],
            "files": [{"id": d.id, "folder_id": d.folder_id, "title": d.title, "filename": d.filename, "content_type": d.content_type, "file_size": d.file_size, "updated_at": d.updated_at} for d in documents]}


@portal_router.post("/messages", status_code=201)
async def portal_message(body: MessageInput, session=Depends(portal_write_session), db: AsyncSession = Depends(get_db)):
    grant, case = session
    await ensure_tenant_write_access(db, grant.tenant_id)
    if body.channel != "portal":
        raise HTTPException(422, "Canal inválido.")
    await db.scalar(select(Tenant).where(Tenant.id == grant.tenant_id).with_for_update())
    existing = await db.scalar(select(CaseMessage).where(CaseMessage.tenant_id == grant.tenant_id, CaseMessage.request_id == str(body.request_id)))
    if existing:
        if existing.case_id != case.id or existing.body != body.body or existing.direction != "inbound":
            raise HTTPException(409, "Identificador já utilizado.")
        return message_json(existing)
    # Bound portal traffic separately from paid provider deliveries.
    recent = await db.scalar(select(func.count(CaseMessage.id)).where(CaseMessage.tenant_id == grant.tenant_id, CaseMessage.case_id == case.id,
                            CaseMessage.direction == "inbound", CaseMessage.created_at > datetime.now(timezone.utc) - timedelta(hours=1)))
    if recent >= 60:
        raise HTTPException(429, "Limite de mensagens do portal atingido. Tente mais tarde.")
    message = CaseMessage(tenant_id=grant.tenant_id, case_id=case.id, client_id=grant.client_id, request_id=str(body.request_id), channel="portal", direction="inbound", body=body.body)
    db.add(message)
    await db.flush()
    await AuditService.log_action(db, grant.tenant_id, None, "CLIENT_MESSAGE_CREATED", "portal_grant", grant.id, {"message_id": message.id})
    await enqueue_user_push(db, tenant_id=grant.tenant_id, user_id=case.responsible_user_id,
                            event_key=f"portal-message:{message.id}", kind="portal_message", case_id=case.id)
    await db.commit()
    return message_json(message)


@portal_router.post("/messages/read", status_code=204)
async def portal_mark_messages_read(session=Depends(portal_write_session), db: AsyncSession = Depends(get_db)):
    grant, case = session
    rows = (await db.scalars(select(CaseMessage).where(
        CaseMessage.tenant_id == grant.tenant_id,
        CaseMessage.case_id == case.id,
        CaseMessage.channel == "portal",
        CaseMessage.direction == "outbound",
        CaseMessage.read_at.is_(None),
    ).with_for_update())).all()
    if rows:
        now = datetime.now(timezone.utc)
        for row in rows:
            row.read_at = now
        await AuditService.log_action(
            db, grant.tenant_id, None, "PORTAL_MESSAGES_READ", "portal_grant", grant.id,
            {"count": len(rows)},
        )
        await db.commit()
    return Response(status_code=204)


@portal_router.get("/documents/{item_id}")
async def portal_download(item_id: str, session=Depends(portal_session), db: AsyncSession = Depends(get_db)):
    grant, case = session
    item = await db.scalar(select(PortalChecklist).where(PortalChecklist.id == item_id, PortalChecklist.tenant_id == grant.tenant_id, PortalChecklist.case_id == case.id))
    document = await db.scalar(select(WorkspaceDocument).where(WorkspaceDocument.tenant_id == grant.tenant_id, WorkspaceDocument.case_id == case.id,
                              WorkspaceDocument.id == item.document_id, WorkspaceDocument.archived_at.is_(None),
                              WorkspaceDocument.deleted_at.is_(None))) if item and item.document_id else None
    if not document:
        raise HTTPException(404, "Documento compartilhado não encontrado.")
    version = await db.scalar(select(WorkspaceDocumentVersion).where(
        WorkspaceDocumentVersion.tenant_id == grant.tenant_id,
        WorkspaceDocumentVersion.document_id == document.id,
        WorkspaceDocumentVersion.version == document.current_version,
    ))
    if version and version.object_key:
        if version.storage_status != "available":
            raise HTTPException(409, "Arquivo ainda está sendo verificado.")
        url = await asyncio.to_thread(create_download_url, version.object_key, document.filename or "documento", document.content_type or "application/octet-stream")
        await AuditService.log_action(db, grant.tenant_id, None, "PORTAL_FILE_DOWNLOADED", "workspace_documents", document.id, {"grant_id": grant.id, "checklist_id": item.id})
        await db.commit()
        return RedirectResponse(url, status_code=307, headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})
    # Force attachment, even for text/PDF; no untrusted active content in app origin.
    content = document.file_content if document.file_content is not None else (document.content_text or "").encode()
    await AuditService.log_action(db, grant.tenant_id, None, "PORTAL_FILE_DOWNLOADED", "workspace_documents", document.id, {"grant_id": grant.id, "checklist_id": item.id})
    await db.commit()
    return Response(content, media_type="application/octet-stream", headers={"Content-Disposition": 'attachment; filename="documento"', "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@portal_router.get("/files/{document_id}")
async def portal_file_download(document_id: str, session=Depends(portal_session), db: AsyncSession = Depends(get_db)):
    grant, case = session
    allowed, _ = await portal_folder_ids(db, grant)
    document = await db.scalar(select(WorkspaceDocument).where(
        WorkspaceDocument.id == document_id, WorkspaceDocument.tenant_id == grant.tenant_id,
        WorkspaceDocument.case_id == case.id, WorkspaceDocument.folder_id.in_(allowed) if allowed else WorkspaceDocument.id.is_(None),
        WorkspaceDocument.deleted_at.is_(None), WorkspaceDocument.archived_at.is_(None),
    ))
    if not document:
        raise HTTPException(404, "Arquivo compartilhado não encontrado.")
    version = await db.scalar(select(WorkspaceDocumentVersion).where(
        WorkspaceDocumentVersion.tenant_id == grant.tenant_id,
        WorkspaceDocumentVersion.document_id == document.id,
        WorkspaceDocumentVersion.version == document.current_version,
    ))
    if version and version.object_key:
        if version.storage_status != "available":
            raise HTTPException(409, "Arquivo ainda está sendo verificado.")
        url = await asyncio.to_thread(create_download_url, version.object_key, document.filename or "documento", document.content_type or "application/octet-stream")
        await AuditService.log_action(db, grant.tenant_id, None, "PORTAL_FILE_DOWNLOADED", "workspace_documents", document.id, {"grant_id": grant.id})
        await db.commit()
        return RedirectResponse(url, status_code=307, headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})
    content = document.file_content if document.file_content is not None else (document.content_text or "").encode()
    await AuditService.log_action(db, grant.tenant_id, None, "PORTAL_FILE_DOWNLOADED", "workspace_documents", document.id, {"grant_id": grant.id})
    await db.commit()
    return Response(content, media_type="application/octet-stream", headers={"Content-Disposition": 'attachment; filename="documento"', "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@portal_router.post("/file-uploads", status_code=201)
async def portal_create_file_upload(body: PortalUploadInput, session=Depends(portal_write_session), db: AsyncSession = Depends(get_db)):
    grant, case = session
    await ensure_tenant_write_access(db, grant.tenant_id)
    if not r2_enabled():
        raise HTTPException(503, "Armazenamento de arquivos ainda não configurado.")
    allowed, _ = await portal_folder_ids(db, grant, upload=True)
    if body.folder_id not in allowed:
        raise HTTPException(403, "Esta pasta não aceita envios do cliente.")
    filename = PurePath(body.filename).name
    content_type = ALLOWED_UPLOAD_TYPES.get(PurePath(filename).suffix.casefold()) if filename == body.filename else None
    if not content_type or body.size > MAX_UPLOAD_BYTES:
        raise HTTPException(422, "Use PDF, DOCX, XLSX, TXT, JPG ou PNG de até 25 MB.")
    await ensure_document_storage_capacity(db, grant.tenant_id, body.size)
    row = WorkspaceDocumentUpload(
        id=str(uuid.uuid4()),
        tenant_id=grant.tenant_id, folder_id=body.folder_id, client_id=grant.client_id, case_id=case.id,
        filename=filename, content_type=content_type, expected_size=body.size, expected_sha256=body.sha256,
        object_key="pending", status="created", created_by_portal_grant_id=grant.id,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )
    row.object_key = quarantine_key(grant.tenant_id, row.id)
    signed = await asyncio.to_thread(create_upload_url, row.object_key, content_type, body.sha256)
    db.add(row)
    await AuditService.log_action(db, grant.tenant_id, None, "PORTAL_FILE_UPLOAD_AUTHORIZED", "workspace_document_uploads", row.id, {"grant_id": grant.id, "size": body.size})
    await db.commit()
    return {"id": row.id, "status": row.status, "upload_url": signed["url"], "upload_headers": signed["headers"], "expires_at": row.expires_at}


@portal_router.post("/file-uploads/{upload_id}/complete")
async def portal_complete_file_upload(upload_id: str, session=Depends(portal_write_session), db: AsyncSession = Depends(get_db)):
    grant, _ = session
    row = await db.scalar(select(WorkspaceDocumentUpload).where(
        WorkspaceDocumentUpload.id == upload_id, WorkspaceDocumentUpload.tenant_id == grant.tenant_id,
        WorkspaceDocumentUpload.created_by_portal_grant_id == grant.id,
    ).with_for_update())
    if not row:
        raise HTTPException(404, "Upload não encontrado.")
    if row.expires_at <= datetime.now(timezone.utc) and row.status == "created":
        row.status = "expired"
        await db.commit()
        raise HTTPException(410, "A autorização de upload expirou.")
    if row.status == "created":
        row.status = "uploaded"
        await db.commit()
    if row.status not in {"uploaded", "processing", "completed"}:
        raise HTTPException(409, row.error or "Upload não pode ser processado.")
    if row.status != "completed":
        process_upload.apply_async(args=[row.id, row.tenant_id], queue="documents")
    return {"id": row.id, "status": row.status, "received": True, "review_required": True}


@portal_router.get("/file-uploads/{upload_id}")
async def portal_file_upload_status(upload_id: str, session=Depends(portal_session), db: AsyncSession = Depends(get_db)):
    grant, _ = session
    row = await db.scalar(select(WorkspaceDocumentUpload).where(
        WorkspaceDocumentUpload.id == upload_id, WorkspaceDocumentUpload.tenant_id == grant.tenant_id,
        WorkspaceDocumentUpload.created_by_portal_grant_id == grant.id,
    ))
    if not row:
        raise HTTPException(404, "Upload não encontrado.")
    return {"id": row.id, "status": row.status, "document_id": row.document_id, "error": row.error}


@portal_router.post("/documents/{item_id}/upload", status_code=201)
async def portal_upload(item_id: str, file: UploadFile = File(...), session=Depends(portal_write_session), db: AsyncSession = Depends(get_db)):
    grant, case = session
    await ensure_tenant_write_access(db, grant.tenant_id)
    filename, content_type, content, digest = await read_validated_upload(file)
    # Same quota lock as staff uploads; no unaccounted private storage area.
    await ensure_document_storage_capacity(db, grant.tenant_id, len(content))
    item = await db.scalar(select(PortalChecklist).where(PortalChecklist.id == item_id, PortalChecklist.tenant_id == grant.tenant_id,
                            PortalChecklist.case_id == case.id).with_for_update())
    if not item:
        raise HTTPException(404, "Solicitação não encontrada.")
    if item.document_id:
        raise HTTPException(409, "Este item já possui documento. Solicite um novo item para corrigir o envio.")
    document = WorkspaceDocument(tenant_id=grant.tenant_id, case_id=case.id, client_id=grant.client_id, kind="evidence",
                    title=item.title, filename=filename, content_type=content_type, file_content=content, file_size=len(content), sha256_hash=digest)
    db.add(document)
    await db.flush()
    db.add(WorkspaceDocumentVersion(tenant_id=grant.tenant_id, document_id=document.id, version=1, filename=filename,
        content_type=content_type, file_content=content, file_size=len(content), sha256_hash=digest, created_by_portal_grant_id=grant.id))
    item.document_id = document.id
    item.completed_at = datetime.now(timezone.utc)
    await AuditService.log_action(db, grant.tenant_id, None, "CLIENT_DOCUMENT_UPLOADED", "workspace_documents", document.id,
                                 {"portal_grant_id": grant.id, "checklist_id": item.id, "sha256": digest})
    await enqueue_user_push(db, tenant_id=grant.tenant_id, user_id=case.responsible_user_id,
                            event_key=f"portal-document:{document.id}", kind="portal_document", case_id=case.id)
    await db.commit()
    return {"document_id": document.id, "received": True, "review_required": True}


@portal_router.post("/logout", status_code=204)
async def portal_logout(response: Response, session=Depends(portal_write_session), db: AsyncSession = Depends(get_db)):
    grant, _ = session
    grant.session_hash = None
    await db.commit()
    response.delete_cookie(PORTAL_COOKIE, path="/api/v1/client-portal", secure=settings.COOKIE_SECURE, httponly=True, samesite="lax")
