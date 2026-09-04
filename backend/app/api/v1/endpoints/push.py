import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import CurrentUser
from app.models.push import PushDelivery, PushSubscription
from app.models.user import User
from app.schemas.push import PushSubscriptionCreate, PushSubscriptionResponse
from app.services.push_service import active_subscriptions, digest, encrypt_subscription, enqueue_subscription_push, revoke_subscription


router = APIRouter()
Database = Annotated[AsyncSession, Depends(get_db)]


def require_push():
    if not settings.WEB_PUSH_ENABLED:
        raise HTTPException(503, "Notificacoes push nao configuradas.")


async def owned_subscription(db, user, subscription_id):
    item = await db.scalar(select(PushSubscription).where(PushSubscription.id == subscription_id,
        PushSubscription.tenant_id == user.tenant_id, PushSubscription.user_id == user.id).with_for_update())
    if not item:
        raise HTTPException(404, "Dispositivo nao encontrado.")
    return item


@router.get("/capabilities")
async def capabilities(user: CurrentUser):
    return {"enabled": settings.WEB_PUSH_ENABLED, "public_key": settings.WEB_PUSH_VAPID_PUBLIC_KEY if settings.WEB_PUSH_ENABLED else None}


@router.get("/subscriptions")
async def subscriptions(user: CurrentUser, db: Database):
    items = (await db.scalars(active_subscriptions(user.tenant_id, user.id).order_by(PushSubscription.created_at.desc()))).all()
    return {"items": [PushSubscriptionResponse.model_validate(item) for item in items]}


@router.post("/subscriptions", response_model=PushSubscriptionResponse)
async def subscribe(body: PushSubscriptionCreate, request: Request, user: CurrentUser, db: Database):
    require_push()
    # Serialize per-user registration and quotas without relying on a Redis counter.
    await db.scalar(select(User).where(User.id == user.id, User.tenant_id == user.tenant_id).with_for_update())
    now = datetime.now(timezone.utc)
    endpoint_hash = digest(body.endpoint)
    item = await db.scalar(select(PushSubscription).where(PushSubscription.endpoint_hash == endpoint_hash,
        PushSubscription.tenant_id == user.tenant_id, PushSubscription.user_id == user.id).with_for_update())
    active = (await db.scalars(active_subscriptions(user.tenant_id, user.id))).all()
    if (not item or item.id not in {row.id for row in active}) and len(active) >= 10:
        raise HTTPException(409, "Limite de 10 dispositivos ativos. Remova um dispositivo antes de continuar.")
    if not item:
        registrations = await db.scalar(select(func.count()).select_from(PushSubscription).where(
            PushSubscription.tenant_id == user.tenant_id, PushSubscription.user_id == user.id,
            PushSubscription.created_at > now - timedelta(days=1)))
        if registrations >= 30:
            raise HTTPException(429, "Limite diario de novos dispositivos atingido.")
        item = PushSubscription(tenant_id=user.tenant_id, user_id=user.id, endpoint_hash=endpoint_hash)
        db.add(item)
    elif item.revoked_at or item.expires_at <= now:
        await revoke_subscription(db, item)
    item.auth_session_id = request.state.auth_session.id
    item.label = body.label
    item.credentials_encrypted = encrypt_subscription(body.endpoint, body.keys.model_dump())
    item.vapid_key_hash = digest(settings.WEB_PUSH_VAPID_PUBLIC_KEY or "")
    item.consented_at = now
    item.last_seen_at = now
    item.expires_at = now + timedelta(days=90)
    item.revoked_at = None
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        # Do not reveal the owner of an endpoint hidden by RLS or silently transfer it.
        raise HTTPException(409, "Inscricao indisponivel. Remova a inscricao do navegador e ative novamente.") from None
    return item


@router.delete("/subscriptions/{subscription_id}", status_code=204)
async def unsubscribe(subscription_id: str, user: CurrentUser, db: Database):
    item = await owned_subscription(db, user, subscription_id)
    await revoke_subscription(db, item)
    await db.commit()
    return Response(status_code=204)


@router.post("/subscriptions/{subscription_id}/test", status_code=202)
async def test_subscription(subscription_id: str, user: CurrentUser, db: Database):
    require_push()
    await db.scalar(select(User).where(User.id == user.id, User.tenant_id == user.tenant_id).with_for_update())
    item = await owned_subscription(db, user, subscription_id)
    if not await db.scalar(active_subscriptions(user.tenant_id, user.id).where(PushSubscription.id == item.id)):
        raise HTTPException(409, "Ative novamente as notificacoes deste dispositivo.")
    count = await db.scalar(select(func.count()).select_from(PushDelivery).where(PushDelivery.tenant_id == user.tenant_id,
        PushDelivery.user_id == user.id, PushDelivery.kind == "test", PushDelivery.created_at > datetime.now(timezone.utc) - timedelta(hours=1)))
    if count >= 5:
        raise HTTPException(429, "Limite de 5 testes por hora atingido.")
    await enqueue_subscription_push(db, item, kind="test", event_key=str(uuid.uuid4()))
    await db.commit()
    return {"status": "queued"}
