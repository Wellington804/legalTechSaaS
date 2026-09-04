from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.core.database import get_db
from app.core.dependencies import CurrentUser
from app.models.audit import AuditLog
from app.models.user import User

router = APIRouter()

@router.get("/logs")
async def list_audit_logs(
    current_user: CurrentUser,
    user_id: str | None = Query(default=None, max_length=64),
    area: str | None = Query(default=None, max_length=64),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = Query(default=100, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role not in {"admin", "partner"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permissao insuficiente.")
    statement = select(AuditLog, User.full_name).outerjoin(User, User.id == AuditLog.user_id).where(AuditLog.tenant_id == current_user.tenant_id)
    if user_id:
        statement = statement.where(AuditLog.user_id == user_id)
    if area:
        statement = statement.where(AuditLog.resource_type == area)
    if date_from:
        statement = statement.where(AuditLog.created_at >= date_from)
    if date_to:
        statement = statement.where(AuditLog.created_at < date_to)
    result = await db.execute(
        statement
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    return [
        {**{key: value for key, value in log.__dict__.items() if not key.startswith("_")}, "actor_name": actor_name or "Sistema"}
        for log, actor_name in result.all()
    ]
