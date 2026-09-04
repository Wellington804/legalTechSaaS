import hashlib
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import decrypt_mfa_secret, encrypt_mfa_secret
from app.models.account import AuthSession
from app.models.push import PushDelivery, PushSubscription
from app.models.routine import RoutineReminder
from app.models.tenant import Tenant
from app.models.user import User
from app.models.workspace import WorkspaceTask
from app.services.workspace_service import authorized_case_query


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def encrypt_subscription(endpoint: str, keys: dict) -> str:
    return encrypt_mfa_secret(json.dumps({"endpoint": endpoint, "keys": keys}, ensure_ascii=True))


def decrypt_subscription(value: str) -> dict:
    return json.loads(decrypt_mfa_secret(value))


def active_subscriptions(tenant_id: str, user_id: str):
    now = datetime.now(timezone.utc)
    return select(PushSubscription).join(AuthSession, AuthSession.id == PushSubscription.auth_session_id).where(
        PushSubscription.tenant_id == tenant_id, PushSubscription.user_id == user_id,
        PushSubscription.revoked_at.is_(None), PushSubscription.expires_at > now,
        AuthSession.tenant_id == tenant_id, AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None),
    )


async def enqueue_subscription_push(db, subscription, *, event_key, kind, case_id=None, task_id=None, reminder_id=None) -> bool:
    if kind not in {"task_assigned", "portal_message", "portal_document", "test", "task_reminder", "judicial_movement"}:
        raise ValueError("Unsupported push event")
    if (kind == "task_assigned" and not task_id) or (kind.startswith("portal_") and not case_id):
        raise ValueError("Push source is required")
    if kind == "task_reminder" and (not task_id or not reminder_id):
        raise ValueError("Reminder source is required")
    identity = digest(f"{kind}:{event_key}")
    if await db.scalar(select(PushDelivery.id).where(PushDelivery.subscription_id == subscription.id, PushDelivery.event_key == identity)):
        return False
    try:
        async with db.begin_nested():
            db.add(PushDelivery(tenant_id=subscription.tenant_id, user_id=subscription.user_id, subscription_id=subscription.id,
                                event_key=identity, kind=kind, case_id=case_id, task_id=task_id, reminder_id=reminder_id,
                                expires_at=datetime.now(timezone.utc) + timedelta(days=1)))
            await db.flush()
    except IntegrityError:
        if await db.scalar(select(PushDelivery.id).where(PushDelivery.subscription_id == subscription.id, PushDelivery.event_key == identity)):
            return False
        raise
    return True


async def enqueue_user_push(db: AsyncSession, *, tenant_id: str, user_id: str, event_key: str, kind: str,
                            case_id: str | None = None, task_id: str | None = None, reminder_id: str | None = None) -> int:
    """Add content-free outbox rows to the caller's transaction. Never commit or send here."""
    if not settings.WEB_PUSH_ENABLED:
        return 0
    subscriptions = (await db.scalars(active_subscriptions(tenant_id, user_id))).all()
    count = 0
    for subscription in subscriptions:
        count += await enqueue_subscription_push(db, subscription, event_key=event_key, kind=kind, case_id=case_id, task_id=task_id, reminder_id=reminder_id)
    return count


async def revoke_subscription(db: AsyncSession, subscription: PushSubscription) -> None:
    subscription.revoked_at = datetime.now(timezone.utc)
    await db.execute(update(PushDelivery).where(PushDelivery.tenant_id == subscription.tenant_id,
        PushDelivery.subscription_id == subscription.id, PushDelivery.status == "queued").values(status="cancelled", error_code="subscription_revoked"))


async def revoke_session_push(db: AsyncSession, *, tenant_id: str, session_id: str) -> None:
    subscriptions = (await db.scalars(select(PushSubscription).where(PushSubscription.tenant_id == tenant_id,
        PushSubscription.auth_session_id == session_id, PushSubscription.revoked_at.is_(None)))).all()
    for subscription in subscriptions:
        await revoke_subscription(db, subscription)


async def delivery_is_authorized(db: AsyncSession, delivery: PushDelivery, subscription: PushSubscription) -> bool:
    """Recheck live authority; session expiry does not prolong auth or disable closed-app alerts."""
    now = datetime.now(timezone.utc)
    if subscription.revoked_at or subscription.expires_at <= now:
        return False
    if subscription.vapid_key_hash != digest(settings.WEB_PUSH_VAPID_PUBLIC_KEY or ""):
        return False
    user = await db.scalar(select(User).join(Tenant, Tenant.id == User.tenant_id).join(AuthSession,
        (AuthSession.id == subscription.auth_session_id) & (AuthSession.user_id == User.id) & (AuthSession.tenant_id == User.tenant_id)).where(
        User.tenant_id == delivery.tenant_id, User.id == delivery.user_id, User.is_active.is_(True),
        Tenant.is_active.is_(True), AuthSession.revoked_at.is_(None)))
    if not user:
        return False
    if delivery.case_id:
        from app.models.workspace import WorkspaceCase
        case = await db.scalar(authorized_case_query(user).where(WorkspaceCase.id == delivery.case_id, WorkspaceCase.archived_at.is_(None)))
        if not case or (delivery.kind.startswith("portal_") and case.responsible_user_id != user.id):
            return False
        if delivery.kind == "judicial_movement" and case.responsible_user_id != user.id:
            return False
    if delivery.kind == "task_assigned":
        task = await db.scalar(select(WorkspaceTask).where(WorkspaceTask.tenant_id == delivery.tenant_id, WorkspaceTask.id == delivery.task_id))
        if not task or task.assigned_user_id != user.id or task.case_id != delivery.case_id or task.status in {"completed", "cancelled"}:
            return False
    if delivery.kind == "task_reminder":
        from app.services.routine_service import reminder_is_authorized
        reminder = await db.scalar(select(RoutineReminder).where(RoutineReminder.id == delivery.reminder_id,
            RoutineReminder.tenant_id == delivery.tenant_id, RoutineReminder.user_id == delivery.user_id,
            RoutineReminder.task_id == delivery.task_id, RoutineReminder.status == "due"))
        if not reminder or not await reminder_is_authorized(db, reminder, user=user):
            return False
        task = await db.scalar(select(WorkspaceTask).where(WorkspaceTask.tenant_id == delivery.tenant_id,
            WorkspaceTask.id == delivery.task_id))
        if not task or task.case_id != delivery.case_id:
            return False
    return True
