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
from app.services.audit_service import AuditService
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


def task_remote_hash(task: WorkspaceTask) -> str:
    payload = task_payload(task)
    return RemoteEvent(
        task.id,
        None,
        False,
        payload["title"],
        payload["starts_at"],
        payload["location"],
        payload["notes"],
    ).canonical_hash()


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
        elif link.status in {"tombstoned", "delete_pending"}:
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
            client = CalendarClient(connection.provider, await _access_token(db, connection))
            calendar_id = decrypt_mfa_secret(connection.selected_calendar_id_encrypted)
            event_id = decrypt_mfa_secret(link.provider_event_id_encrypted)
            remote = await client.get_event(calendar_id, event_id)
            if not remote.deleted:
                await client.delete_event(calendar_id, event_id, remote.etag)
        except (CalendarProviderError, RuntimeError):
            await _set_tenant_context(db, user.tenant_id)
            link.status = "delete_pending"
            connection.last_error = "O provedor ainda não confirmou a remoção do compromisso. Uma nova tentativa será feita."
            await db.commit()
            return
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
            CalendarSyncConflict.tenant_id == connection.tenant_id,
            CalendarSyncConflict.connection_id == connection.id,
            CalendarSyncConflict.task_id == task.id,
            CalendarSyncConflict.remote_hash == remote_hash,
        )
    )
    if existing:
        existing.remote_etag = remote.etag
        existing.remote_payload_encrypted = encrypt_mfa_secret(_serialize_remote(remote))
        existing.local_revision = task.revision
        existing.reason = reason
        existing.status = "pending"
        existing.resolved_by_user_id = None
        existing.resolved_at = None
        link.status = "conflict"
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


def conflict_payload(conflict: CalendarSyncConflict, task: WorkspaceTask) -> dict:
    remote = _deserialize_remote(decrypt_mfa_secret(conflict.remote_payload_encrypted))
    local_starts_at = task.due_at
    if local_starts_at and local_starts_at.tzinfo is None:
        local_starts_at = local_starts_at.replace(tzinfo=timezone.utc)
    return {
        "id": conflict.id,
        "connection_id": conflict.connection_id,
        "task_id": conflict.task_id,
        "reason": conflict.reason,
        "status": conflict.status,
        "local_revision": task.revision,
        "remote_hash": conflict.remote_hash,
        "created_at": conflict.created_at,
        "local": {
            "hash": task_hash(task),
            "title": task.title,
            "starts_at": local_starts_at,
            "location": task.location,
            "notes": task.notes,
            "deleted": task.status == "cancelled",
            "revision": task.revision,
        },
        "remote": {
            "hash": remote.canonical_hash(),
            "title": remote.title,
            "starts_at": remote.starts_at,
            "location": remote.location,
            "notes": remote.notes,
            "deleted": remote.deleted,
            "revision": None,
        },
    }


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
    # Recover an external create that succeeded before the local transaction
    # committed. Provider markers are opaque IDs and are accepted only for this
    # connection's selected task allowlist.
    candidates_by_task: dict[str, list[RemoteEvent]] = {}
    for remote in page.events:
        if remote.linked_task_id and remote.linked_connection_id in {None, connection.id}:
            candidates_by_task.setdefault(remote.linked_task_id, []).append(remote)
    for link in links:
        if link.provider_event_id_encrypted or link.status != "active":
            continue
        candidates = candidates_by_task.get(link.task_id, [])
        if len(candidates) != 1:
            continue
        remote = candidates[0]
        task = tasks.get(link.task_id)
        link.provider_event_id_encrypted = encrypt_mfa_secret(remote.identifier)
        link.provider_event_hash = digest(remote.identifier)
        link.provider_etag = remote.etag
        if task and not remote.deleted and task.due_at and remote.canonical_hash() == task_remote_hash(task):
            link.last_local_hash = task_hash(task)
            link.last_remote_hash = remote.canonical_hash()
            link.last_synced_at = _utcnow()
        elif task:
            await _record_conflict(db, connection, link, task, remote, "remote_deleted" if remote.deleted else "both_changed")
            conflicts += 1
    by_event = {link.provider_event_hash: link for link in links if link.provider_event_hash}
    for remote in page.events:
        link = by_event.get(digest(remote.identifier))
        if not link or link.status != "active":
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
        if link.status not in {"active", "delete_pending"}:
            continue
        task = tasks.get(link.task_id)
        if link.status == "delete_pending":
            if not link.provider_event_id_encrypted:
                link.status = "tombstoned"
                continue
            try:
                event_id = decrypt_mfa_secret(link.provider_event_id_encrypted)
                remote = await client.get_event(calendar_id, event_id)
                if not remote.deleted:
                    await client.delete_event(calendar_id, event_id, remote.etag)
                await _set_tenant_context(db, tenant_id)
                link.status = "tombstoned"
                link.last_synced_at = _utcnow()
                pushed += 1
            except (CalendarProviderError, RuntimeError) as exc:
                await _set_tenant_context(db, tenant_id)
                sync_error = str(exc)[:500]
                connection.last_error = sync_error
            continue
        if not task:
            if link.provider_event_id_encrypted:
                try:
                    event_id = decrypt_mfa_secret(link.provider_event_id_encrypted)
                    remote = await client.get_event(calendar_id, event_id)
                    if not remote.deleted:
                        await client.delete_event(calendar_id, event_id, remote.etag)
                    await _set_tenant_context(db, tenant_id)
                    link.status = "tombstoned"
                    link.last_synced_at = _utcnow()
                except (CalendarProviderError, RuntimeError) as exc:
                    await _set_tenant_context(db, tenant_id)
                    link.status = "delete_pending"
                    sync_error = str(exc)[:500]
                    connection.last_error = sync_error
            else:
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
                    calendar_id,
                    decrypt_mfa_secret(link.provider_event_id_encrypted),
                    link.provider_etag,
                    task.id,
                    task_payload(task),
                    connection.id,
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
                if not link.provider_event_id_encrypted:
                    sync_error = "O provedor informou conflito sem identificar o evento remoto. A reconciliação será repetida."
                    connection.last_error = sync_error
                    break
                try:
                    event_id = decrypt_mfa_secret(link.provider_event_id_encrypted)
                    remote = await client.get_event(calendar_id, event_id)
                    await _set_tenant_context(db, tenant_id)
                except (CalendarProviderError, RuntimeError) as lookup_error:
                    await _set_tenant_context(db, tenant_id)
                    sync_error = str(lookup_error)[:500]
                    connection.last_error = sync_error
                    break
                await _record_conflict(
                    db,
                    connection,
                    link,
                    task,
                    remote,
                    "remote_deleted" if remote.deleted else "both_changed",
                )
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
    db: AsyncSession,
    user: User,
    conflict: CalendarSyncConflict,
    resolution: Literal["accept_remote", "keep_local"],
    *,
    expected_local_revision: int,
    expected_remote_hash: str,
) -> CalendarSyncConflict:
    """Resolve only the exact local/remote snapshots shown to the reviewer.

    Provider access happens before database row locks only when refreshing the
    OAuth token may commit.  The actual remote read is performed while the
    conflict, connection, task and link are locked, and is compared with both
    the stored hash and ETag before any local mutation.
    """
    if conflict.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Este conflito já foi resolvido.")
    if not secrets.compare_digest(conflict.remote_hash, expected_remote_hash):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A versão externa exibida não é mais atual.")
    task = await get_task(db, user, conflict.task_id)
    require_task_write(user, task)
    if task.revision != expected_local_revision:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="O compromisso mudou após a abertura do conflito.")

    connection = await db.scalar(
        select(CalendarConnection).where(
            CalendarConnection.tenant_id == user.tenant_id,
            CalendarConnection.id == conflict.connection_id,
            CalendarConnection.user_id == user.id,
            CalendarConnection.status == "active",
        )
    )
    if not connection or not connection.selected_calendar_id_encrypted:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Reconecte e selecione a agenda antes de resolver.")
    token = await _access_token(db, connection)

    await _set_tenant_context(db, user.tenant_id)
    connection = await db.scalar(
        select(CalendarConnection)
        .where(
            CalendarConnection.tenant_id == user.tenant_id,
            CalendarConnection.id == conflict.connection_id,
            CalendarConnection.user_id == user.id,
            CalendarConnection.status == "active",
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    current = await db.scalar(
        select(CalendarSyncConflict)
        .where(
            CalendarSyncConflict.tenant_id == user.tenant_id,
            CalendarSyncConflict.id == conflict.id,
            CalendarSyncConflict.connection_id == conflict.connection_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    locked_task = await db.scalar(
        select(WorkspaceTask)
        .where(WorkspaceTask.tenant_id == user.tenant_id, WorkspaceTask.id == conflict.task_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    link = await db.scalar(
        select(CalendarTaskLink).where(
            CalendarTaskLink.tenant_id == user.tenant_id,
            CalendarTaskLink.connection_id == conflict.connection_id,
            CalendarTaskLink.task_id == conflict.task_id,
        ).with_for_update().execution_options(populate_existing=True)
    )
    if not connection or not connection.selected_calendar_id_encrypted:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A conexão de calendário mudou durante a revisão.")
    if not current or current.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Este conflito já foi resolvido ou removido.")
    if not locked_task or not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vínculo de calendário não encontrado.")
    if link.status != "conflict":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="O vínculo de calendário não está mais em conflito.")
    require_task_write(user, locked_task)
    if locked_task.revision != expected_local_revision:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="O compromisso mudou após a abertura do conflito.")
    if not secrets.compare_digest(current.remote_hash, expected_remote_hash):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A versão externa exibida não é mais atual.")

    try:
        stored_remote = _deserialize_remote(decrypt_mfa_secret(current.remote_payload_encrypted))
        calendar_id = decrypt_mfa_secret(connection.selected_calendar_id_encrypted)
    except (RuntimeError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="O snapshot do conflito não pôde ser validado.") from exc
    client = CalendarClient(connection.provider, token)
    try:
        live_remote = await client.get_event(calendar_id, stored_remote.identifier)
    except (CalendarProviderError, KeyError, TypeError, ValueError) as exc:
        await _set_tenant_context(db, user.tenant_id)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Não foi possível revalidar a versão externa.") from exc
    await _set_tenant_context(db, user.tenant_id)
    live_hash = live_remote.canonical_hash()
    etag_changed = current.remote_etag != live_remote.etag
    remote_is_stale = (
        not secrets.compare_digest(live_hash, expected_remote_hash)
        or not secrets.compare_digest(live_hash, current.remote_hash)
        or etag_changed
        or (not live_remote.deleted and not live_remote.etag)
    )
    if remote_is_stale:
        # Persist the provider's real state before returning 409.  A reload can
        # then show the exact new comparison instead of trapping the reviewer
        # on a stale encrypted snapshot.
        previous_remote_hash = current.remote_hash
        if not secrets.compare_digest(previous_remote_hash, live_hash):
            replacement = await db.scalar(
                select(CalendarSyncConflict)
                .where(
                    CalendarSyncConflict.tenant_id == user.tenant_id,
                    CalendarSyncConflict.connection_id == current.connection_id,
                    CalendarSyncConflict.task_id == current.task_id,
                    CalendarSyncConflict.remote_hash == live_hash,
                    CalendarSyncConflict.id != current.id,
                )
                .with_for_update()
            )
            if replacement:
                await db.delete(current)
                current = replacement
        current.remote_hash = live_hash
        current.remote_etag = live_remote.etag
        current.remote_payload_encrypted = encrypt_mfa_secret(_serialize_remote(live_remote))
        current.reason = "remote_deleted" if live_remote.deleted else "both_changed"
        current.local_revision = locked_task.revision
        current.status = "pending"
        current.resolved_by_user_id = None
        current.resolved_at = None
        link.provider_etag = live_remote.etag
        await AuditService.log_action(
            db,
            user.tenant_id,
            user.id,
            "CALENDAR_CONFLICT_REFRESHED",
            "calendar_sync_conflicts",
            current.id,
            {
                "task_id": current.task_id,
                "previous_remote_hash": previous_remote_hash,
                "remote_hash": live_hash,
                "local_revision": locked_task.revision,
            },
        )
        await db.commit()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A agenda externa mudou após a abertura do conflito.")

    if resolution == "accept_remote":
        if live_remote.deleted:
            locked_task.status = "cancelled"
            locked_task.manually_reviewed = False
            locked_task.revision += 1
            link.status = "tombstoned"
        else:
            try:
                _apply_remote(locked_task, live_remote)
            except ValueError as exc:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A versão externa está incompleta.") from exc
            link.status = "active"
            link.last_local_hash = task_hash(locked_task)
            link.last_remote_hash = live_hash
            link.provider_etag = live_remote.etag
        current.status = "accepted_remote"
    else:
        link.status = "active"
        link.last_remote_hash = live_hash
        link.provider_etag = live_remote.etag
        if live_remote.deleted:
            link.provider_event_hash = None
            link.provider_event_id_encrypted = None
            link.provider_etag = None
        current.status = "kept_local"
    current.resolved_by_user_id = user.id
    current.resolved_at = _utcnow()
    await db.flush()
    return current


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
    if provider == "google":
        if not resource or not connection.watch_resource_hash:
            return None, False
        if not secrets.compare_digest(connection.watch_resource_hash, digest(resource)):
            return None, False
    elif resource and (
        not connection.watch_resource_hash
        or not secrets.compare_digest(connection.watch_resource_hash, digest(resource))
    ):
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
