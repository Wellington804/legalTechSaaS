from datetime import datetime, timedelta, timezone
import hmac
import secrets

import jwt

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import CurrentUser, _set_tenant_context, get_current_user, require_tenant_write
from app.core.security import hash_account_token
from app.models.user import User
from app.services.audit_service import AuditService
from app.models.workspace import WorkspaceCase, WorkspaceTask
from app.services.calendar_export import render_tasks_ics
from app.services.workspace_service import case_access_clause


router = APIRouter(dependencies=[Depends(get_current_user)])
calendar_router = APIRouter()


@router.get("/status")
async def integration_status(current_user: CurrentUser):
    del current_user
    return {
        "calendar_export": {"status": "available", "format": "ics"},
        "datajud": {"status": "configured" if settings.DATAJUD_ENABLED and settings.DATAJUD_API_KEY else "not_configured"},
        "email": {"status": "configured" if settings.RESEND_ENABLED and not settings.NOTIFICATIONS_DRY_RUN else "not_configured"},
        "whatsapp": {"status": "configured" if settings.EVOLUTION_ENABLED and not settings.NOTIFICATIONS_DRY_RUN else "not_configured"},
        "ai": {"status": "configured" if settings.AI_ENABLED else "not_configured", "provider": settings.AI_PROVIDER},
        "sentry": {"status": "configured" if settings.SENTRY_DSN else "not_configured"},
    }


async def calendar_response(current_user: User, db: AsyncSession, days: int, *, subscription: bool = False):
    start = datetime.now(timezone.utc) - timedelta(days=30)
    end = datetime.now(timezone.utc) + timedelta(days=days)
    statement = (
        select(WorkspaceTask)
        .outerjoin(
            WorkspaceCase,
            and_(WorkspaceCase.id == WorkspaceTask.case_id, WorkspaceCase.tenant_id == WorkspaceTask.tenant_id),
        )
        .where(
            WorkspaceTask.tenant_id == current_user.tenant_id,
            WorkspaceTask.status.in_(("pending", "in_progress")),
            WorkspaceTask.due_at.between(start, end),
            or_(WorkspaceTask.case_id.is_(None), case_access_clause(current_user)),
        )
        .order_by(WorkspaceTask.due_at)
        .limit(2000)
    )
    tasks = (await db.scalars(statement)).all()
    return Response(
        render_tasks_ics(list(tasks)),
        media_type="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": 'inline; filename="lexflow-agenda.ics"' if subscription else 'attachment; filename="lexflow-agenda.ics"',
            "Cache-Control": "private, max-age=300" if subscription else "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/calendar.ics")
async def calendar_export(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    days: int = Query(default=180, ge=1, le=366),
):
    return await calendar_response(current_user, db, days)


@router.get("/calendar-feed")
async def calendar_feed_status(current_user: CurrentUser):
    return {"enabled": bool(current_user.calendar_feed_token_hash), "created_at": current_user.calendar_feed_created_at}


@router.post("/calendar-feed", status_code=201)
async def create_calendar_feed(
    request: Request,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    user = await db.scalar(select(User).where(
        User.id == current_user.id, User.tenant_id == current_user.tenant_id,
    ).with_for_update())
    now = datetime.now(timezone.utc)
    token = jwt.encode({
        "sub": user.id, "tenant_id": user.tenant_id, "aud": "lexflow-calendar",
        "nonce": secrets.token_urlsafe(32), "iat": now,
    }, settings.SECRET_KEY, algorithm="HS256")
    user.calendar_feed_token_hash = hash_account_token(token)
    user.calendar_feed_created_at = now
    await AuditService.log_action(db, user.tenant_id, user.id, "CALENDAR_FEED_CREATED", "users", user.id)
    await db.commit()
    return {
        "enabled": True, "created_at": now,
        "feed_url": f"{settings.FRONTEND_URL.rstrip('/')}/api/v1/calendar/{token}.ics",
        "notice": "Este endereco e uma credencial privada. Revogue-o se for compartilhado por engano.",
    }


@router.delete("/calendar-feed", status_code=204)
async def revoke_calendar_feed(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    user = await db.scalar(select(User).where(
        User.id == current_user.id, User.tenant_id == current_user.tenant_id,
    ).with_for_update())
    user.calendar_feed_token_hash = None
    user.calendar_feed_created_at = None
    await AuditService.log_action(db, user.tenant_id, user.id, "CALENDAR_FEED_REVOKED", "users", user.id)
    await db.commit()
    return Response(status_code=204)


@calendar_router.get("/{token}.ics")
async def subscribed_calendar(
    token: str,
    db: AsyncSession = Depends(get_db),
    days: int = Query(default=180, ge=1, le=366),
):
    if len(token) > 2048:
        raise HTTPException(401, "Agenda externa invalida ou revogada.")
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"], audience="lexflow-calendar",
                             options={"require": ["sub", "tenant_id", "aud", "nonce", "iat"]})
        user_id, tenant_id = payload["sub"], payload["tenant_id"]
        if not isinstance(user_id, str) or not isinstance(tenant_id, str):
            raise ValueError
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        raise HTTPException(401, "Agenda externa invalida ou revogada.") from None
    await _set_tenant_context(db, tenant_id)
    user = await db.scalar(select(User).where(
        User.id == user_id, User.tenant_id == tenant_id, User.is_active.is_(True),
    ))
    if not user or not user.calendar_feed_token_hash or not hmac.compare_digest(user.calendar_feed_token_hash, hash_account_token(token)):
        raise HTTPException(401, "Agenda externa invalida ou revogada.")
    return await calendar_response(user, db, days, subscription=True)
