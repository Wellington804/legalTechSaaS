"""OAuth lifecycle and conflict-aware calendar synchronization."""

import base64
import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import _set_tenant_context
from app.core.security import decrypt_mfa_secret, encrypt_mfa_secret
from app.models.external_integrations import (
    CalendarConnection,
    CalendarOAuthState,
    CalendarSyncConflict,
    CalendarTaskLink,
    CalendarWebhookEvent,
)
from app.models.user import User
from app.models.workspace import WorkspaceTask
from app.services.calendar_providers import (
    CalendarClient,
    CalendarCursorExpired,
    CalendarProviderError,
    RemoteEvent,
    authorization_url,
    exchange_code,
    refresh_tokens,
    revoke_google_token,
)
from app.services.workspace_service import get_task, require_task_write


OAUTH_STATE_TTL = timedelta(minutes=10)
SYNC_WINDOW_PAST = timedelta(days=90)
SYNC_WINDOW_FUTURE = timedelta(days=730)


def digest(value: str | bytes) -> str:
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


async def start_oauth(
    db: AsyncSession, user: User, provider: Literal["google", "microsoft"], redirect_path: str
) -> tuple[str, datetime]:
    state = secrets.token_urlsafe(48)
    verifier, challenge = _pkce()
    expires_at = _utcnow() + OAUTH_STATE_TTL
    db.add(
        CalendarOAuthState(
            tenant_id=user.tenant_id,
            user_id=user.id,
            provider=provider,
            state_digest=digest(state),
            pkce_verifier_encrypted=encrypt_mfa_secret(verifier),
            redirect_path=redirect_path,
            expires_at=expires_at,
        )
    )
    await db.commit()
    return authorization_url(provider, state=state, challenge=challenge), expires_at


async def complete_oauth(
    db: AsyncSession,
    user: User,
    provider: Literal["google", "microsoft"],
    *,
    state_value: str,
    code: str,
) -> tuple[CalendarConnection, str]:
    """Consume state before token exchange so callback replay cannot reissue credentials."""
    state = await db.scalar(
        select(CalendarOAuthState)
        .where(
            CalendarOAuthState.tenant_id == user.tenant_id,
            CalendarOAuthState.user_id == user.id,
            CalendarOAuthState.provider == provider,
            CalendarOAuthState.state_digest == digest(state_value),
        )
        .with_for_update()
    )
    now = _utcnow()
    if not state or state.consumed_at is not None or state.expires_at <= now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autorização expirada ou já utilizada.")
    try:
        verifier = decrypt_mfa_secret(state.pkce_verifier_encrypted)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Estado OAuth inválido.") from exc
    redirect_path = state.redirect_path
    state.consumed_at = now
    await db.commit()

    tokens = await exchange_code(provider, code, verifier)
    account = await CalendarClient(provider, tokens.access_token).account()
    await _set_tenant_context(db, user.tenant_id)
    connection = await db.scalar(
        select(CalendarConnection)
        .where(
            CalendarConnection.tenant_id == user.tenant_id,
            CalendarConnection.user_id == user.id,
            CalendarConnection.provider == provider,
        )
        .with_for_update()
    )
    account_hash = digest(f"{provider}:{account.identifier}")
    if connection and connection.provider_account_id_hash != account_hash:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Desconecte a conta atual antes de autorizar outra conta do mesmo provedor.",
        )
    if connection is None:
        connection = CalendarConnection(
            tenant_id=user.tenant_id,
            user_id=user.id,
            provider=provider,
            provider_account_id_hash=account_hash,
            access_token_encrypted=encrypt_mfa_secret(tokens.access_token),
            refresh_token_encrypted=encrypt_mfa_secret(tokens.refresh_token),
            token_expires_at=tokens.expires_at,
            granted_scopes=json.dumps(tokens.scopes),
        )
        db.add(connection)
    else:
        connection.access_token_encrypted = encrypt_mfa_secret(tokens.access_token)
        connection.refresh_token_encrypted = encrypt_mfa_secret(tokens.refresh_token)
        connection.token_expires_at = tokens.expires_at
        connection.granted_scopes = json.dumps(tokens.scopes)
        connection.status = "active"
        connection.last_error = None
        connection.revision += 1
    connection.provider_account_label = account.label
    await db.commit()
    return connection, redirect_path


async def get_connection(
    db: AsyncSession, user: User, provider: Literal["google", "microsoft"], *, for_update: bool = False
) -> CalendarConnection:
    query = select(CalendarConnection).where(
        CalendarConnection.tenant_id == user.tenant_id,
        CalendarConnection.user_id == user.id,
        CalendarConnection.provider == provider,
    )
    if for_update:
        query = query.with_for_update()
    connection = await db.scalar(query)
    if not connection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Calendário não conectado.")
    return connection


async def _access_token(db: AsyncSession, connection: CalendarConnection) -> str:
    try:
        access = decrypt_mfa_secret(connection.access_token_encrypted)
        refresh = decrypt_mfa_secret(connection.refresh_token_encrypted)
    except RuntimeError as exc:
        raise CalendarProviderError("Credenciais de calendário inválidas.", reauthorization_required=True) from exc
    if connection.token_expires_at > _utcnow() + timedelta(minutes=2):
        return access
    try:
        tokens = await refresh_tokens(connection.provider, refresh)
    except CalendarProviderError as exc:
        await _set_tenant_context(db, connection.tenant_id)
        if exc.reauthorization_required:
            connection.status = "reauthorization_required"
            connection.last_error = "Autorização expirada. Reconecte o calendário."
            connection.revision += 1
            await db.commit()
        raise
    await _set_tenant_context(db, connection.tenant_id)
    connection.access_token_encrypted = encrypt_mfa_secret(tokens.access_token)
    connection.refresh_token_encrypted = encrypt_mfa_secret(tokens.refresh_token)
    connection.token_expires_at = tokens.expires_at
    connection.granted_scopes = json.dumps(tokens.scopes)
    connection.status = "active"
    connection.last_error = None
    await db.commit()
    return tokens.access_token


async def provider_calendars(db: AsyncSession, connection: CalendarConnection):
    return await CalendarClient(connection.provider, await _access_token(db, connection)).calendars()


async def choose_calendar(
    db: AsyncSession,
    connection: CalendarConnection,
    *,
    calendar_id: str,
    expected_revision: int,
) -> CalendarConnection:
    if connection.revision != expected_revision:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Conexão alterada em outra sessão.")
    token = await _access_token(db, connection)
    client = CalendarClient(connection.provider, token)
    calendars = await client.calendars()
    selected = next((item for item in calendars if secrets.compare_digest(item.identifier, calendar_id)), None)
    if not selected or not selected.can_write:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Selecione uma agenda com permissão de escrita.")
    if connection.watch_reference_encrypted:
        try:
            await client.delete_watch(
                decrypt_mfa_secret(connection.watch_reference_encrypted),
                decrypt_mfa_secret(connection.watch_resource_encrypted) if connection.watch_resource_encrypted else None,
            )
        except (CalendarProviderError, RuntimeError):
            pass
    watch = await client.create_watch(calendar_id, connection.id)
    await _set_tenant_context(db, connection.tenant_id)
    current = await db.scalar(
        select(CalendarConnection)
        .where(CalendarConnection.tenant_id == connection.tenant_id, CalendarConnection.id == connection.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not current or current.revision != expected_revision:
        try:
            await client.delete_watch(watch.reference, watch.resource)
        except CalendarProviderError:
            pass
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Conexão alterada em outra sessão.")
    current.selected_calendar_id_encrypted = encrypt_mfa_secret(calendar_id)
    current.selected_calendar_label = selected.name
    current.sync_cursor_encrypted = None
    current.sync_window_start = _utcnow() - SYNC_WINDOW_PAST
    current.sync_window_end = _utcnow() + SYNC_WINDOW_FUTURE
    current.watch_reference_hash = digest(watch.reference)
    current.watch_reference_encrypted = encrypt_mfa_secret(watch.reference)
    current.watch_resource_hash = digest(watch.resource) if watch.resource else None
    current.watch_resource_encrypted = encrypt_mfa_secret(watch.resource) if watch.resource else None
    current.watch_token_hash = digest(watch.token)
    current.watch_token_encrypted = encrypt_mfa_secret(watch.token)
    current.watch_expires_at = watch.expires_at
    current.last_error = None
    current.revision += 1
    await db.commit()
    return current


async def disconnect_calendar(db: AsyncSession, connection: CalendarConnection) -> str | None:
    warning = None
    try:
        access = await _access_token(db, connection)
        client = CalendarClient(connection.provider, access)
        if connection.watch_reference_encrypted:
            await client.delete_watch(
                decrypt_mfa_secret(connection.watch_reference_encrypted),
                decrypt_mfa_secret(connection.watch_resource_encrypted) if connection.watch_resource_encrypted else None,
            )
        if connection.provider == "google":
            await revoke_google_token(decrypt_mfa_secret(connection.refresh_token_encrypted))
    except (CalendarProviderError, RuntimeError) as exc:
        warning = str(exc)[:300]
    await _set_tenant_context(db, connection.tenant_id)
    await db.delete(connection)
    await db.commit()
    return warning


async def renew_watch_if_needed(db: AsyncSession, connection: CalendarConnection) -> bool:
    if not connection.selected_calendar_id_encrypted:
        return False
    if connection.watch_expires_at and connection.watch_expires_at > _utcnow() + timedelta(hours=24):
        return False
    calendar_id = decrypt_mfa_secret(connection.selected_calendar_id_encrypted)
    client = CalendarClient(connection.provider, await _access_token(db, connection))
    watch = await client.create_watch(calendar_id, connection.id)
    old_reference = decrypt_mfa_secret(connection.watch_reference_encrypted) if connection.watch_reference_encrypted else None
    old_resource = decrypt_mfa_secret(connection.watch_resource_encrypted) if connection.watch_resource_encrypted else None
    await _set_tenant_context(db, connection.tenant_id)
    connection.watch_reference_hash = digest(watch.reference)
    connection.watch_reference_encrypted = encrypt_mfa_secret(watch.reference)
    connection.watch_resource_hash = digest(watch.resource) if watch.resource else None
    connection.watch_resource_encrypted = encrypt_mfa_secret(watch.resource) if watch.resource else None
    connection.watch_token_hash = digest(watch.token)
    connection.watch_token_encrypted = encrypt_mfa_secret(watch.token)
    connection.watch_expires_at = watch.expires_at
    connection.revision += 1
    await db.commit()
    if old_reference:
        try:
            await client.delete_watch(old_reference, old_resource)
        except CalendarProviderError:
            pass
    return True


def task_payload(task: WorkspaceTask) -> dict:
    if not task.due_at:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Compromisso sem data não pode ser sincronizado.")
    starts_at = task.due_at if task.due_at.tzinfo else task.due_at.replace(tzinfo=timezone.utc)
    return {
        "title": task.title,
        "starts_at": starts_at.astimezone(timezone.utc),
        "location": task.location or "",
        "notes": task.notes or "",
    }


def task_hash(task: WorkspaceTask) -> str:
    starts_at = task.due_at
    if starts_at and starts_at.tzinfo is None:
        starts_at = starts_at.replace(tzinfo=timezone.utc)
    serializable = {
        "title": task.title,
        "starts_at": starts_at.astimezone(timezone.utc).isoformat() if starts_at else None,
        "location": task.location or "",
        "notes": task.notes or "",
        "status": task.status,
    }
    return digest(json.dumps(serializable, sort_keys=True, separators=(",", ":")))


async def select_tasks(db: AsyncSession, user: User, connection: CalendarConnection, task_ids: list[str]) -> list[CalendarTaskLink]:
    if not connection.selected_calendar_id_encrypted:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Selecione uma agenda antes de adicionar compromissos.")
    links = []
    for task_id in task_ids:
        task = await get_task(db, user, task_id)
        require_task_write(user, task)
        task_payload(task)
        link = await db.scalar(
            select(CalendarTaskLink).where(
                CalendarTaskLink.tenant_id == user.tenant_id,
                CalendarTaskLink.connection_id == connection.id,
                CalendarTaskLink.task_id == task.id,
            )
        )
        if link is None:
            link = CalendarTaskLink(tenant_id=user.tenant_id, connection_id=connection.id, task_id=task.id)
            db.add(link)
        elif link.status == "tombstoned":
            link.status = "active"
        links.append(link)
    await db.commit()
    return links


async def unselect_task(db: AsyncSession, user: User, connection: CalendarConnection, task_id: str) -> None:
    link = await db.scalar(
        select(CalendarTaskLink).where(
            CalendarTaskLink.tenant_id == user.tenant_id,
            CalendarTaskLink.connection_id == connection.id,
            CalendarTaskLink.task_id == task_id,
        )
    )
    if not link:
        return
    if link.provider_event_id_encrypted:
        if not connection.selected_calendar_id_encrypted:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Agenda de destino indisponível.")
        try:
            await CalendarClient(connection.provider, await _access_token(db, connection)).delete_event(
                decrypt_mfa_secret(connection.selected_calendar_id_encrypted),
                decrypt_mfa_secret(link.provider_event_id_encrypted),
                link.provider_etag,
            )
        except CalendarProviderError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="O provedor não confirmou a remoção.") from exc
        await _set_tenant_context(db, user.tenant_id)
    await db.delete(link)
    await db.commit()


def _serialize_remote(remote: RemoteEvent) -> str:
    body = {
        "identifier": remote.identifier,
        "etag": remote.etag,
        "deleted": remote.deleted,
        "title": remote.title,
        "starts_at": remote.starts_at.isoformat() if remote.starts_at else None,
        "location": remote.location,
        "notes": remote.notes,
    }
    # The shared Fernet helper accepts an ASCII envelope; JSON escapes preserve
    # all Unicode legal text without weakening encryption.
    return json.dumps(body, ensure_ascii=True, separators=(",", ":"))


def _deserialize_remote(value: str) -> RemoteEvent:
    body = json.loads(value)
    return RemoteEvent(
        body["identifier"], body.get("etag"), bool(body.get("deleted")), body.get("title"),
        datetime.fromisoformat(body["starts_at"]) if body.get("starts_at") else None,
        body.get("location"), body.get("notes"),
    )


async def _record_conflict(
    db: AsyncSession, connection: CalendarConnection, link: CalendarTaskLink, task: WorkspaceTask, remote: RemoteEvent, reason: str
) -> CalendarSyncConflict:
    remote_hash = remote.canonical_hash()
    existing = await db.scalar(
        select(CalendarSyncConflict).where(
            CalendarSyncConflict.connection_id == connection.id,
            CalendarSyncConflict.task_id == task.id,
            CalendarSyncConflict.remote_hash == remote_hash,
        )
    )
    if existing:
        return existing
    conflict = CalendarSyncConflict(
        tenant_id=connection.tenant_id,
        connection_id=connection.id,
        task_id=task.id,
        reason=reason,
        remote_hash=remote_hash,
        remote_etag=remote.etag,
        remote_payload_encrypted=encrypt_mfa_secret(_serialize_remote(remote)),
        local_revision=task.revision,
    )
    db.add(conflict)
    link.status = "conflict"
    return conflict


def _apply_remote(task: WorkspaceTask, remote: RemoteEvent) -> None:
    if remote.deleted or not remote.title or not remote.starts_at:
        raise ValueError("remote event cannot be applied")
    task.title = remote.title[:300]
    task.due_at = remote.starts_at
    task.location = (remote.location or "")[:300] or None
    task.notes = remote.notes
    task.manually_reviewed = False
    task.revision += 1


async def synchronize_connection(db: AsyncSession, tenant_id: str, connection_id: str) -> dict[str, int]:
    """Synchronize one explicit task allowlist. Provider data outside it is discarded."""
    await _set_tenant_context(db, tenant_id)
    connection = await db.scalar(
        select(CalendarConnection).where(CalendarConnection.tenant_id == tenant_id, CalendarConnection.id == connection_id)
    )
    if not connection or connection.status != "active" or not connection.selected_calendar_id_encrypted:
        return {"pulled": 0, "pushed": 0, "conflicts": 0}
    user = await db.scalar(select(User).where(User.tenant_id == tenant_id, User.id == connection.user_id, User.is_active.is_(True)))
    if not user:
        connection.status = "revoked"
        connection.last_error = "Usuário não está mais ativo."
        await db.commit()
        return {"pulled": 0, "pushed": 0, "conflicts": 0}
    calendar_id = decrypt_mfa_secret(connection.selected_calendar_id_encrypted)
    token = await _access_token(db, connection)
    # Webhooks and the periodic reconciler can enqueue the same connection at
    # once.  Serialize its delta cursor and provider writes so two workers
    # cannot create/update the same external event from a stale snapshot.
    await _set_tenant_context(db, tenant_id)
    connection = await db.scalar(
        select(CalendarConnection)
        .where(CalendarConnection.tenant_id == tenant_id, CalendarConnection.id == connection_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not connection or connection.status != "active" or not connection.selected_calendar_id_encrypted:
        return {"pulled": 0, "pushed": 0, "conflicts": 0}
    calendar_id = decrypt_mfa_secret(connection.selected_calendar_id_encrypted)
    client = CalendarClient(connection.provider, token)
    cursor = decrypt_mfa_secret(connection.sync_cursor_encrypted) if connection.sync_cursor_encrypted else None
    start = connection.sync_window_start or (_utcnow() - SYNC_WINDOW_PAST)
    end = connection.sync_window_end or (_utcnow() + SYNC_WINDOW_FUTURE)
    try:
        page = await client.changes(calendar_id, connection.id, cursor, start, end)
    except CalendarCursorExpired:
        page = await client.changes(calendar_id, connection.id, None, start, end)
    await _set_tenant_context(db, tenant_id)
    links = (
        await db.scalars(select(CalendarTaskLink).where(CalendarTaskLink.tenant_id == tenant_id, CalendarTaskLink.connection_id == connection.id))
    ).all()
    by_event = {link.provider_event_hash: link for link in links if link.provider_event_hash}
    tasks: dict[str, WorkspaceTask] = {}
    for link in links:
        try:
            tasks[link.task_id] = await get_task(db, user, link.task_id)
        except HTTPException:
            # Permission may have been revoked after selection. The push phase
            # removes the external copy without reading legal task content.
            continue
    pulled = pushed = conflicts = 0
    sync_error: str | None = None
    for remote in page.events:
        link = by_event.get(digest(remote.identifier))
        if not link or link.status == "tombstoned":
            continue
        task = tasks.get(link.task_id)
        if not task:
            continue
        remote_hash = remote.canonical_hash()
        remote_changed = remote_hash != link.last_remote_hash
        local_changed = task_hash(task) != link.last_local_hash if link.last_local_hash else False
        if not remote_changed:
            continue
        if remote.deleted:
            if task.status == "cancelled":
                link.status = "tombstoned"
                link.last_remote_hash = remote_hash
            else:
                await _record_conflict(db, connection, link, task, remote, "remote_deleted")
                conflicts += 1
            continue
        if not remote.title or not remote.starts_at:
            await _record_conflict(db, connection, link, task, remote, "both_changed")
            conflicts += 1
            continue
        if local_changed:
            await _record_conflict(db, connection, link, task, remote, "both_changed")
            conflicts += 1
            continue
        _apply_remote(task, remote)
        local_hash = task_hash(task)
        link.last_local_hash = local_hash
        link.last_remote_hash = remote_hash
        link.provider_etag = remote.etag
        link.last_synced_at = _utcnow()
        pulled += 1

    for link in links:
        if link.status != "active":
            continue
        task = tasks.get(link.task_id)
        if not task:
            if link.provider_event_id_encrypted:
                try:
                    await client.delete_event(
                        calendar_id,
                        decrypt_mfa_secret(link.provider_event_id_encrypted),
                        link.provider_etag,
                    )
                    await _set_tenant_context(db, tenant_id)
                except (CalendarProviderError, RuntimeError):
                    pass
            link.status = "tombstoned"
            continue
        current_hash = task_hash(task)
        if task.status != "cancelled" and not task.due_at:
            sync_error = f"Compromisso {task.id} está sem data e aguarda correção."
            continue
        try:
            if not link.provider_event_id_encrypted:
                if task.status == "cancelled":
                    link.status = "tombstoned"
                    continue
                remote = await client.create_event(calendar_id, task.id, task_payload(task), connection.id)
                await _set_tenant_context(db, tenant_id)
                link.provider_event_id_encrypted = encrypt_mfa_secret(remote.identifier)
                link.provider_event_hash = digest(remote.identifier)
                link.provider_etag = remote.etag
                link.last_remote_hash = remote.canonical_hash()
                link.last_local_hash = current_hash
                link.last_synced_at = _utcnow()
                pushed += 1
            elif task.status == "cancelled":
                await client.delete_event(calendar_id, decrypt_mfa_secret(link.provider_event_id_encrypted), link.provider_etag)
                await _set_tenant_context(db, tenant_id)
                link.status = "tombstoned"
                link.last_local_hash = current_hash
                link.last_synced_at = _utcnow()
                pushed += 1
            elif current_hash != link.last_local_hash:
                remote = await client.update_event(
                    calendar_id, decrypt_mfa_secret(link.provider_event_id_encrypted), link.provider_etag, task.id, task_payload(task)
                )
                await _set_tenant_context(db, tenant_id)
                link.provider_etag = remote.etag
                link.last_remote_hash = remote.canonical_hash()
                link.last_local_hash = current_hash
                link.last_synced_at = _utcnow()
                pushed += 1
        except CalendarProviderError as exc:
            await _set_tenant_context(db, tenant_id)
            if exc.conflict:
                remote = RemoteEvent(
                    decrypt_mfa_secret(link.provider_event_id_encrypted), link.provider_etag, False,
                    task.title, task.due_at, task.location, task.notes,
                )
                await _record_conflict(db, connection, link, task, remote, "both_changed")
                conflicts += 1
            else:
                sync_error = str(exc)[:500]
                connection.last_error = sync_error
                if exc.reauthorization_required:
                    connection.status = "reauthorization_required"
                break
    connection.sync_cursor_encrypted = encrypt_mfa_secret(page.cursor)
    connection.last_sync_at = _utcnow()
    if connection.status == "active":
        connection.last_error = sync_error
    await db.commit()
    return {"pulled": pulled, "pushed": pushed, "conflicts": conflicts}


async def resolve_conflict(
    db: AsyncSession, user: User, conflict: CalendarSyncConflict, resolution: Literal["accept_remote", "keep_local"]
) -> CalendarSyncConflict:
    task = await get_task(db, user, conflict.task_id)
    require_task_write(user, task)
    if conflict.status != "pending":
        return conflict
    link = await db.scalar(
        select(CalendarTaskLink).where(
            CalendarTaskLink.tenant_id == user.tenant_id,
            CalendarTaskLink.connection_id == conflict.connection_id,
            CalendarTaskLink.task_id == conflict.task_id,
        ).with_for_update()
    )
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vínculo de calendário não encontrado.")
    if resolution == "accept_remote":
        remote = _deserialize_remote(decrypt_mfa_secret(conflict.remote_payload_encrypted))
        if remote.deleted:
            task.status = "cancelled"
            task.manually_reviewed = False
            task.revision += 1
            link.status = "tombstoned"
        else:
            _apply_remote(task, remote)
            link.status = "active"
            link.last_local_hash = task_hash(task)
            link.last_remote_hash = remote.canonical_hash()
            link.provider_etag = remote.etag
        conflict.status = "accepted_remote"
    else:
        remote = _deserialize_remote(decrypt_mfa_secret(conflict.remote_payload_encrypted))
        link.status = "active"
        link.last_remote_hash = remote.canonical_hash()
        link.provider_etag = remote.etag
        if remote.deleted:
            link.provider_event_hash = None
            link.provider_event_id_encrypted = None
            link.provider_etag = None
        conflict.status = "kept_local"
    conflict.resolved_by_user_id = user.id
    conflict.resolved_at = _utcnow()
    await db.commit()
    return conflict


async def record_webhook(
    db: AsyncSession,
    *,
    provider: Literal["google", "microsoft"],
    reference: str,
    token: str,
    delivery_id: str,
    payload: bytes,
    resource: str | None = None,
) -> tuple[CalendarConnection, bool] | tuple[None, bool]:
    reference_hash = digest(reference)
    if db.bind and db.bind.dialect.name == "postgresql":
        row = (
            await db.execute(
                text("SELECT * FROM public.calendar_webhook_identity(:provider, :reference_hash)"),
                {"provider": provider, "reference_hash": reference_hash},
            )
        ).first()
        if not row:
            return None, False
        tenant_id, connection_id = row.tenant_id, row.connection_id
        await _set_tenant_context(db, tenant_id)
        connection = await db.scalar(
            select(CalendarConnection).where(CalendarConnection.tenant_id == tenant_id, CalendarConnection.id == connection_id)
        )
    else:
        connection = await db.scalar(
            select(CalendarConnection).where(
                CalendarConnection.provider == provider, CalendarConnection.watch_reference_hash == reference_hash
            )
        )
    if not connection or not connection.watch_token_hash or not secrets.compare_digest(connection.watch_token_hash, digest(token)):
        return None, False
    if resource and connection.watch_resource_hash and not secrets.compare_digest(connection.watch_resource_hash, digest(resource)):
        return None, False
    event = CalendarWebhookEvent(
        tenant_id=connection.tenant_id,
        connection_id=connection.id,
        provider=provider,
        delivery_id=delivery_id[:200],
        payload_digest=digest(payload),
    )
    try:
        async with db.begin_nested():
            db.add(event)
            await db.flush()
    except IntegrityError:
        return connection, True
    await db.commit()
    return connection, False
