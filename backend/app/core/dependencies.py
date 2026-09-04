from datetime import datetime, timezone
from typing import Annotated, Callable

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_token
from app.models.account import AuthSession
from app.models.tenant import Tenant
from app.models.user import User


UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Sessao invalida ou expirada.",
    headers={"WWW-Authenticate": "Bearer"},
)
WRITES_BLOCKED = HTTPException(
    status_code=status.HTTP_402_PAYMENT_REQUIRED,
    detail="A assinatura do escritorio nao permite novas alteracoes.",
)


def require_trusted_origin(request: Request) -> None:
    origin = request.headers.get("Origin")
    if origin and origin.rstrip("/") not in {item.rstrip("/") for item in settings.CORS_ORIGINS}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Origem nao autorizada.")


async def _set_tenant_context(db: AsyncSession, tenant_id: str) -> None:
    if db.bind and db.bind.dialect.name == "postgresql":
        await db.execute(
            text("SELECT set_config('app.current_tenant', :tenant_id, true)"),
            {"tenant_id": tenant_id},
        )


async def get_current_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    token = request.cookies.get(getattr(settings, "COOKIE_NAME", "lexflow_session"))
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        if not request.headers.get("Origin"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Origem obrigatoria.")
        require_trusted_origin(request)
    payload = decode_token(token) if token else None
    if not payload:
        raise UNAUTHORIZED

    user_id = payload.get("sub")
    tenant_id = payload.get("tenant_id")
    session_id = payload.get("sid")
    if (
        not isinstance(user_id, str)
        or not user_id
        or not isinstance(tenant_id, str)
        or not tenant_id
        or not isinstance(session_id, str)
        or not session_id
    ):
        raise UNAUTHORIZED

    await _set_tenant_context(db, tenant_id)
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(User, Tenant, AuthSession)
        .join(Tenant, Tenant.id == User.tenant_id)
        .join(
            AuthSession,
            (AuthSession.id == session_id)
            & (AuthSession.user_id == User.id)
            & (AuthSession.tenant_id == User.tenant_id),
        )
        .where(
            User.id == user_id,
            User.tenant_id == tenant_id,
            User.is_active.is_(True),
            Tenant.is_active.is_(True),
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > now,
        )
    )
    row = result.first()
    if not row:
        raise UNAUTHORIZED

    user, tenant, auth_session = row
    request.state.user_id = user.id
    request.state.tenant_id = tenant.id
    request.state.auth_session = auth_session
    request.state.auth_payload = payload
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: str) -> Callable:
    async def checker(current_user: CurrentUser) -> User:
        if current_user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permissao insuficiente.")
        return current_user

    return checker


async def require_privileged_mfa(request: Request, current_user: CurrentUser) -> User:
    if not settings.is_hardened_environment:
        return current_user
    if not getattr(current_user, "email_verified_at", None):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Verifique o e-mail antes de acessar recursos do escritorio.",
        )
    if not getattr(settings, "PRIVILEGED_MFA_REQUIRED", True):
        return current_user
    if current_user.role not in {"admin", "partner"}:
        return current_user
    auth_session = getattr(request.state, "auth_session", None)
    payload = getattr(request.state, "auth_payload", {})
    if (
        not getattr(current_user, "mfa_enabled", False)
        or not getattr(auth_session, "mfa_verified_at", None)
        or not payload.get("mfa")
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="MFA obrigatorio para esta operacao.",
        )
    return current_user


async def ensure_tenant_write_access(db: AsyncSession, tenant_id: str) -> Tenant:
    tenant = await db.scalar(select(Tenant).where(Tenant.id == tenant_id, Tenant.is_active.is_(True)))
    if not tenant:
        raise UNAUTHORIZED
    if tenant.subscription_status == "trial":
        if not tenant.trial_ends_at or tenant.trial_ends_at <= datetime.now(timezone.utc):
            raise WRITES_BLOCKED
    elif tenant.subscription_status == "active":
        if tenant.subscription_ends_at and tenant.subscription_ends_at <= datetime.now(
            timezone.utc
        ):
            raise WRITES_BLOCKED
    else:
        raise WRITES_BLOCKED
    return tenant


async def require_tenant_write(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    await ensure_tenant_write_access(db, current_user.tenant_id)
    return current_user
