import hashlib
import json
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit import AuditLog

class AuditService:

    @staticmethod
    async def log_action(
        db: AsyncSession,
        tenant_id: str,
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: str = None,
        details: dict = None,
        ip_address: str = None,
        user_agent: str = None
    ) -> AuditLog:
        timestamp_str = datetime.now(timezone.utc).isoformat()
        payload = f"{tenant_id}:{user_id}:{action}:{resource_type}:{resource_id}:{timestamp_str}:{json.dumps(details or {})}"
        sha256_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

        log_entry = AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            sha256_hash=sha256_hash
        )
        db.add(log_entry)
        await db.flush()
        return log_entry
