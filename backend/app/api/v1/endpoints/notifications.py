import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import _set_tenant_context, get_current_user
from app.core.request_body import read_limited_body
from app.core.redis_cache import cache_manager
from app.models.user import User
from app.models.engagement import TenantChannel
from app.services.audit_service import AuditService
from app.schemas.notification import NotificationDeliveryResponse, NotificationDispatchRequest
from app.services.notification_providers import provider_is_configured
from app.services.notification_service import (
    apply_provider_event,
    create_or_get_delivery,
    get_tenant_delivery,
    verify_resend_signature,
)
from app.services.tasks import process_notification_task


router = APIRouter()
MAX_WEBHOOK_BYTES = 256 * 1024
DISPATCHES_PER_MINUTE = 20


async def enforce_dispatch_rate_limit(user: User) -> None:
    client = cache_manager.redis_client
    if client is None:
        raise HTTPException(status_code=503, detail="Rate limiter is unavailable")
    key = f"legaltech:notifications:rate:{user.tenant_id}:{user.id}"
    try:
        count = await client.eval(
            "local n=redis.call('INCR',KEYS[1]); "
            "if n==1 then redis.call('EXPIRE',KEYS[1],60) end; return n",
            1,
            key,
        )
    except Exception:
        raise HTTPException(status_code=503, detail="Rate limiter is unavailable")
    if int(count) > DISPATCHES_PER_MINUTE:
        raise HTTPException(status_code=429, detail="Notification dispatch limit exceeded")


@router.post("", response_model=NotificationDeliveryResponse, status_code=status.HTTP_202_ACCEPTED)
async def dispatch_notification(
    body: NotificationDispatchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not settings.UNBOUND_NOTIFICATION_DISPATCH_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Notification dispatch is disabled until recipients are bound to persisted tenant resources",
        )
    await enforce_dispatch_rate_limit(current_user)
    if not provider_is_configured(body.channel):
        raise HTTPException(status_code=503, detail="Notification provider is disabled")
    delivery, existing = await create_or_get_delivery(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        resource_ref=body.resource_ref,
        recipient=body.recipient,
        channel=body.channel,
    )
    await db.commit()
    if delivery.status == "queued":
        try:
            process_notification_task.delay(delivery.id, current_user.tenant_id)
        except Exception:
            raise HTTPException(status_code=503, detail="Delivery persisted but worker is unavailable")
    response = NotificationDeliveryResponse.model_validate(delivery)
    return response.model_copy(update={"existing": existing})


@router.get("/{delivery_id}", response_model=NotificationDeliveryResponse)
async def get_notification(
    delivery_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    delivery = await get_tenant_delivery(db, delivery_id, current_user.tenant_id)
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")
    return NotificationDeliveryResponse.model_validate(delivery)


@router.post("/webhooks/resend", status_code=status.HTTP_202_ACCEPTED)
async def resend_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    svix_id: str = Header(alias="svix-id"),
    svix_timestamp: str = Header(alias="svix-timestamp"),
    svix_signature: str = Header(alias="svix-signature"),
):
    raw = await read_limited_body(request, MAX_WEBHOOK_BYTES, "Webhook too large")
    secret = getattr(settings, "RESEND_WEBHOOK_SECRET", "")
    if not secret or not verify_resend_signature(
        raw,
        message_id=svix_id,
        timestamp=svix_timestamp,
        signatures=svix_signature,
        secret=secret,
    ):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    try:
        payload = json.loads(raw)
        event_type = payload["type"]
        provider_message_id = payload["data"]["email_id"]
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid webhook payload")
    if not isinstance(event_type, str) or not isinstance(provider_message_id, str):
        raise HTTPException(status_code=400, detail="Invalid webhook payload")

    statuses = {
        "email.sent": "sent",
        "email.delivered": "delivered",
        "email.bounced": "failed",
        "email.complained": "failed",
        "email.failed": "failed",
    }
    if event_type in statuses:
        await apply_provider_event(
            db,
            provider="resend",
            provider_message_id=provider_message_id,
            event_identity=svix_id,
            event_type=event_type,
            status=statuses[event_type],
        )
    return {"received": True}


@router.post("/webhooks/evolution", status_code=status.HTTP_202_ACCEPTED)
async def evolution_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    raw = await read_limited_body(request, MAX_WEBHOOK_BYTES, "Webhook too large")
    try:
        payload = json.loads(raw)
        instance_id = payload["instanceId"]
        instance_token = payload["instanceToken"]
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid webhook payload")
    from app.services.engagement_service import resolve_evolution_instance

    tenant_id = await resolve_evolution_instance(db, str(instance_id), str(instance_token))
    if not tenant_id:
        raise HTTPException(status_code=401, detail="Invalid webhook credentials")

    event = payload.get("event")
    if event in {"Connected", "PairSuccess", "Disconnected", "LoggedOut", "ConnectFailure", "QRTimeout", "QRCode"}:
        from app.services.evolution_manager import phone_from_jid

        await _set_tenant_context(db, tenant_id)
        channel = await db.get(TenantChannel, tenant_id)
        if not channel:
            raise HTTPException(status_code=401, detail="Invalid webhook credentials")
        previous = channel.whatsapp_connection_state
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        if event in {"Connected", "PairSuccess"}:
            channel.whatsapp_connection_state = "connected"
            channel.whatsapp_enabled = True
            channel.whatsapp_number = phone_from_jid(data.get("jid")) or channel.whatsapp_number
        elif event == "QRCode":
            channel.whatsapp_connection_state = "pending"
        else:
            channel.whatsapp_connection_state = "disconnected"
            if event == "LoggedOut":
                channel.whatsapp_number = None
        channel.whatsapp_last_checked_at = datetime.now(timezone.utc)
        if previous != channel.whatsapp_connection_state and channel.whatsapp_connection_state in {"connected", "disconnected"}:
            action = "WHATSAPP_CONNECTED" if channel.whatsapp_connection_state == "connected" else "WHATSAPP_DISCONNECTED"
            await AuditService.log_action(db, tenant_id, None, action, "case_communication", tenant_id)
        await db.commit()
        return {"received": True}

    if event != "Receipt" or payload.get("state") not in {"Read", "ReadSelf", "Delivered"}:
        return {"received": True}
    data = payload.get("data")
    message_ids = data.get("MessageIDs") if isinstance(data, dict) else None
    timestamp_value = data.get("Timestamp") if isinstance(data, dict) else None
    if (
        not isinstance(message_ids, list)
        or not message_ids
        or len(message_ids) > 100
        or not isinstance(timestamp_value, str)
    ):
        raise HTTPException(status_code=400, detail="Invalid receipt payload")
    for message_id in message_ids:
        if not isinstance(message_id, str) or not message_id or len(message_id) > 255:
            raise HTTPException(status_code=400, detail="Invalid receipt payload")
        event_identity = f"{instance_id}:{message_id}:{payload['state']}:{timestamp_value}"
        await apply_provider_event(
            db,
            provider="evolution",
            provider_message_id=message_id,
            event_identity=event_identity,
            event_type=f"Receipt.{payload['state']}",
            status="delivered",
            expected_tenant_id=tenant_id,
        )
    return {"received": True}
