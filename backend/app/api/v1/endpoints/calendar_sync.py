"""Authenticated calendar OAuth/sync endpoints and provider notifications."""

import hashlib
import json
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import CurrentUser, _set_tenant_context, get_current_user, require_tenant_write
from app.core.request_body import read_limited_body
from app.models.external_integrations import CalendarConnection, CalendarSyncConflict, CalendarTaskLink
from app.models.user import User
from app.schemas.external_integrations import (
    CalendarConflictResponse,
    CalendarConnectionResponse,
    CalendarSelection,
    CalendarTaskLinkResponse,
    CalendarTaskSelection,
    ConflictResolution,
    OAuthAuthorization,
    OAuthStart,
    ProviderCalendar,
)
from app.services.audit_service import AuditService
from app.services.calendar_sync import (
    choose_calendar,
    complete_oauth,
    conflict_payload,
    disconnect_calendar,
    get_connection,
    provider_calendars,
    record_webhook,
    resolve_conflict,
    select_tasks,
    start_oauth,
    unselect_task,
)
from app.services.workspace_service import get_task


router = APIRouter(dependencies=[Depends(get_current_user)])
public_router = APIRouter()
PROVIDERS = {"google", "microsoft"}
MAX_WEBHOOK_BYTES = 1024 * 1024


def _provider(value: str) -> str:
    value = value.casefold()
    if value not in PROVIDERS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provedor de calendário não encontrado.")
    return value


def _enqueue(connection: CalendarConnection) -> None:
    try:
        from app.services.calendar_sync_tasks import process_calendar_connection

        process_calendar_connection.delay(connection.id, connection.tenant_id)
    except Exception:
        # The periodic reconciler is the durable fallback. Never expose broker details.
        return


@router.get("/calendar-oauth/status", response_model=dict)
async def calendar_connections(user: CurrentUser, db: AsyncSession = Depends(get_db)):
    rows = (
        await db.scalars(
            select(CalendarConnection)
            .where(CalendarConnection.tenant_id == user.tenant_id, CalendarConnection.user_id == user.id)
            .order_by(CalendarConnection.provider)
        )
    ).all()
    return {"items": [CalendarConnectionResponse.model_validate(row) for row in rows]}


@router.post("/calendar-oauth/{provider}/connect", response_model=OAuthAuthorization)
async def connect_calendar(
    provider: str,
    body: OAuthStart,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    provider = _provider(provider)
    url, expires_at = await start_oauth(db, user, provider, body.redirect_path)
    return OAuthAuthorization(authorization_url=url, expires_at=expires_at)


@router.get("/calendar-oauth/{provider}/callback")
async def calendar_oauth_callback(
    provider: str,
    user: CurrentUser,
    state_value: str = Query(alias="state", min_length=20, max_length=512),
    code: str | None = Query(default=None, min_length=1, max_length=4096),
    error: str | None = Query(default=None, max_length=200),
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    provider = _provider(provider)
    if error or not code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Autorização de calendário cancelada.")
    connection, redirect_path = await complete_oauth(db, user, provider, state_value=state_value, code=code)
    await _set_tenant_context(db, user.tenant_id)
    await AuditService.log_action(db, user.tenant_id, user.id, "CALENDAR_OAUTH_CONNECTED", "calendar_connections", connection.id, {"provider": provider})
    await db.commit()
    separator = "&" if "?" in redirect_path else "?"
    target = f"{settings.FRONTEND_URL.rstrip('/')}{redirect_path}{separator}{urlencode({'calendar_connected': provider})}"
    return RedirectResponse(target, status_code=303)


@router.get("/calendar-oauth/{provider}/calendars", response_model=dict)
async def list_provider_calendars(provider: str, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    connection = await get_connection(db, user, _provider(provider))
    rows = await provider_calendars(db, connection)
    return {"items": [ProviderCalendar(id=row.identifier, name=row.name, primary=row.primary, can_write=row.can_write) for row in rows]}


@router.put("/calendar-oauth/{provider}/calendar", response_model=CalendarConnectionResponse)
async def select_provider_calendar(
    provider: str,
    body: CalendarSelection,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    connection = await get_connection(db, user, _provider(provider), for_update=True)
    connection = await choose_calendar(db, connection, calendar_id=body.calendar_id, expected_revision=body.expected_revision)
    await _set_tenant_context(db, user.tenant_id)
    await AuditService.log_action(db, user.tenant_id, user.id, "CALENDAR_SELECTED", "calendar_connections", connection.id, {"provider": provider})
    await db.commit()
    _enqueue(connection)
    return CalendarConnectionResponse.model_validate(connection)


@router.delete("/calendar-oauth/{provider}", status_code=204)
async def disconnect_provider_calendar(
    provider: str,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    connection = await get_connection(db, user, _provider(provider), for_update=True)
    connection_id = connection.id
    warning = await disconnect_calendar(db, connection)
    await _set_tenant_context(db, user.tenant_id)
    await AuditService.log_action(db, user.tenant_id, user.id, "CALENDAR_OAUTH_DISCONNECTED", "calendar_connections", connection_id, {"provider": provider, "provider_warning": bool(warning)})
    await db.commit()
    return Response(status_code=204)


@router.post("/calendar-oauth/{provider}/tasks", response_model=dict, status_code=202)
async def add_calendar_tasks(
    provider: str,
    body: CalendarTaskSelection,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    connection = await get_connection(db, user, _provider(provider), for_update=True)
    links = await select_tasks(db, user, connection, body.task_ids)
    await _set_tenant_context(db, user.tenant_id)
    await AuditService.log_action(db, user.tenant_id, user.id, "CALENDAR_TASKS_SELECTED", "calendar_connections", connection.id, {"count": len(links)})
    await db.commit()
    _enqueue(connection)
    return {"items": [CalendarTaskLinkResponse.model_validate(row) for row in links]}


@router.post("/calendar-oauth/{provider}/sync", status_code=202)
async def request_calendar_sync(provider: str, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    connection = await get_connection(db, user, _provider(provider))
    if not connection.selected_calendar_id_encrypted:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Selecione uma agenda antes de sincronizar.")
    _enqueue(connection)
    return {"queued": True}


@router.get("/calendar-oauth/{provider}/tasks", response_model=dict)
async def list_calendar_tasks(provider: str, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    connection = await get_connection(db, user, _provider(provider))
    rows = (
        await db.scalars(
            select(CalendarTaskLink)
            .where(CalendarTaskLink.tenant_id == user.tenant_id, CalendarTaskLink.connection_id == connection.id)
            .order_by(CalendarTaskLink.created_at.desc())
        )
    ).all()
    return {"items": [CalendarTaskLinkResponse.model_validate(row) for row in rows]}


@router.delete("/calendar-oauth/{provider}/tasks/{task_id}", status_code=204)
async def remove_calendar_task(
    provider: str,
    task_id: str,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    connection = await get_connection(db, user, _provider(provider), for_update=True)
    await unselect_task(db, user, connection, task_id)
    await _set_tenant_context(db, user.tenant_id)
    await AuditService.log_action(
        db, user.tenant_id, user.id, "CALENDAR_TASK_UNSELECTED", "calendar_connections", connection.id,
        {"provider": provider, "task_id": task_id},
    )
    await db.commit()
    _enqueue(connection)
    return Response(status_code=204)


@router.get("/calendar-oauth/conflicts/pending", response_model=dict)
async def pending_calendar_conflicts(user: CurrentUser, db: AsyncSession = Depends(get_db)):
    rows = (
        await db.scalars(
            select(CalendarSyncConflict)
            .join(
                CalendarConnection,
                and_(
                    CalendarConnection.tenant_id == CalendarSyncConflict.tenant_id,
                    CalendarConnection.id == CalendarSyncConflict.connection_id,
                ),
            )
            .where(
                CalendarSyncConflict.tenant_id == user.tenant_id,
                CalendarConnection.tenant_id == user.tenant_id,
                CalendarConnection.user_id == user.id,
                CalendarSyncConflict.status == "pending",
            )
            .order_by(CalendarSyncConflict.created_at)
        )
    ).all()
    items = []
    for row in rows:
        try:
            task = await get_task(db, user, row.task_id)
        except HTTPException:
            continue
        items.append(CalendarConflictResponse.model_validate(conflict_payload(row, task)))
    return {"items": items}


@router.post("/calendar-oauth/conflicts/{conflict_id}/resolve", response_model=CalendarConflictResponse)
async def resolve_calendar_conflict(
    conflict_id: str,
    body: ConflictResolution,
    request: Request,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    conflict = await db.scalar(
        select(CalendarSyncConflict)
        .join(
            CalendarConnection,
            and_(
                CalendarConnection.tenant_id == CalendarSyncConflict.tenant_id,
                CalendarConnection.id == CalendarSyncConflict.connection_id,
            ),
        )
        .where(
            CalendarSyncConflict.tenant_id == user.tenant_id,
            CalendarSyncConflict.id == conflict_id,
            CalendarConnection.tenant_id == user.tenant_id,
            CalendarConnection.user_id == user.id,
        )
    )
    if not conflict:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conflito não encontrado.")
    conflict = await resolve_conflict(
        db,
        user,
        conflict,
        body.resolution,
        expected_local_revision=body.expected_local_revision,
        expected_remote_hash=body.expected_remote_hash,
    )
    await AuditService.log_action(
        db,
        user.tenant_id,
        user.id,
        "CALENDAR_CONFLICT_RESOLVED",
        "calendar_sync_conflicts",
        conflict.id,
        {
            "resolution": body.resolution,
            "task_id": conflict.task_id,
            "expected_local_revision": body.expected_local_revision,
            "expected_remote_hash": body.expected_remote_hash,
        },
        request.client.host if request.client else None,
        request.headers.get("user-agent"),
    )
    await db.commit()
    task = await get_task(db, user, conflict.task_id)
    response = CalendarConflictResponse.model_validate(conflict_payload(conflict, task))
    connection = await db.scalar(
        select(CalendarConnection).where(
            CalendarConnection.tenant_id == user.tenant_id,
            CalendarConnection.id == conflict.connection_id,
            CalendarConnection.user_id == user.id,
        )
    )
    if connection:
        _enqueue(connection)
    return response


@public_router.post("/calendar-webhooks/google", status_code=202)
async def google_calendar_webhook(
    request: Request,
    channel_id: str = Header(alias="X-Goog-Channel-ID", min_length=1, max_length=200),
    channel_token: str = Header(alias="X-Goog-Channel-Token", min_length=1, max_length=512),
    message_number: str = Header(alias="X-Goog-Message-Number", min_length=1, max_length=100),
    resource_id: str = Header(alias="X-Goog-Resource-ID", min_length=1, max_length=512),
    db: AsyncSession = Depends(get_db),
):
    raw = await read_limited_body(request, MAX_WEBHOOK_BYTES, "Webhook muito grande.")
    connection, duplicate = await record_webhook(
        db, provider="google", reference=channel_id, token=channel_token,
        delivery_id=f"{channel_id}:{message_number}", payload=raw + resource_id.encode(), resource=resource_id,
    )
    if not connection:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Notificação inválida.")
    if not duplicate:
        _enqueue(connection)
    return {"received": True, "duplicate": duplicate}


@public_router.post("/calendar-webhooks/microsoft", status_code=202)
async def microsoft_calendar_webhook(
    request: Request,
    validation_token: str | None = Query(default=None, alias="validationToken", max_length=4096),
    db: AsyncSession = Depends(get_db),
):
    if validation_token is not None:
        return Response(validation_token, media_type="text/plain")
    raw = await read_limited_body(request, MAX_WEBHOOK_BYTES, "Webhook muito grande.")
    try:
        payload = json.loads(raw)
        values = payload["value"]
        if not isinstance(values, list) or len(values) > 100:
            raise ValueError
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Notificação inválida.") from exc
    accepted = duplicates = 0
    for item in values:
        if not isinstance(item, dict):
            continue
        reference, token = item.get("subscriptionId"), item.get("clientState")
        if not isinstance(reference, str) or not isinstance(token, str):
            continue
        item_raw = json.dumps(item, sort_keys=True, separators=(",", ":")).encode()
        delivery = hashlib.sha256(item_raw).hexdigest()
        connection, duplicate = await record_webhook(
            db, provider="microsoft", reference=reference, token=token,
            delivery_id=delivery, payload=item_raw,
        )
        if connection:
            accepted += 1
            duplicates += int(duplicate)
            if not duplicate:
                _enqueue(connection)
    if accepted == 0:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Notificação inválida.")
    return {"received": accepted, "duplicates": duplicates}
