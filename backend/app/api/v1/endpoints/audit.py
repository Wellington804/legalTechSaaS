from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.core.database import get_db
from app.models.audit import AuditLog

router = APIRouter()

@router.get("/logs")
async def list_audit_logs(req: Request, db: AsyncSession = Depends(get_db)):
    tenant_id = getattr(req.state, "tenant_id", "default-tenant")
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.tenant_id == tenant_id)
        .order_by(AuditLog.created_at.desc())
        .limit(100)
    )
    logs = result.scalars().all()
    return logs
