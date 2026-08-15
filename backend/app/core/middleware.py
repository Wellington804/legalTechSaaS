from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from typing import Optional

class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Extract tenant_id from Header or Query Param for Multi-Tenancy isolation
        tenant_id = request.headers.get("X-Tenant-ID") or request.query_params.get("tenant_id")
        request.state.tenant_id = tenant_id if tenant_id else "default-tenant"
        
        response = await call_next(request)
        response.headers["X-Tenant-ID"] = request.state.tenant_id
        return response
