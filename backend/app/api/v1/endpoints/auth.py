import hashlib
import re
import unicodedata
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field, StrictBool, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import CurrentUser, _set_tenant_context, require_trusted_origin
from app.core.redis_cache import cache_manager
from app.core.security import (
    create_access_token,
    decrypt_mfa_secret,
    get_password_hash,
    hash_account_token,
    matching_totp_counter,
    validate_password_policy,
    verify_password,
)
from app.models.account import AccountToken, AuthSession
from app.services.push_service import revoke_session_push
from app.models.tenant import Tenant
from app.models.user import User


router = APIRouter()
DUMMY_PASSWORD_HASH = "$2b$12$7zdJKwqW.TlQyWaEeTO7c.CkPPTlQmW94BqHXbZZqrd1HgmtbF33C"
REMEMBERED_SESSION_DAYS = 14


async def _enforce_auth_rate_limit(
    action: str,
    request: Request,
    email: str,
    *,
    limit: int,
    window_seconds: int,
) -> None:
    client = cache_manager.redis_client
    if client is None:
        if settings.is_hardened_environment:
            raise HTTPException(status_code=503, detail="Authentication temporarily unavailable.")
        return
    source = request.client.host if request.client else "unknown"
    source_key = "legaltech:auth:rate:source:" + hashlib.sha256(
        f"{action}:{source}".encode()
    ).hexdigest()
    account_key = "legaltech:auth:rate:account:" + hashlib.sha256(
        f"{action}:{email}".encode()
    ).hexdigest()
    try:
        counts = await client.eval(
            "local a=redis.call('INCR',KEYS[1]); local b=redis.call('INCR',KEYS[2]); "
            "if a==1 then redis.call('EXPIRE',KEYS[1],ARGV[1]) end; "
            "if b==1 then redis.call('EXPIRE',KEYS[2],ARGV[1]) end; return {a,b}",
            2,
            source_key,
            account_key,
            window_seconds,
        )
    except Exception:
        if settings.is_hardened_environment:
            raise HTTPException(status_code=503, detail="Authentication temporarily unavailable.")
        return
    if any(int(count) > limit for count in counts):
        raise HTTPException(status_code=429, detail="Too many authentication attempts.")


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")


def _registration_is_allowed(email: str) -> bool:
    allowed = {item.strip().lower() for item in settings.PILOT_ALLOWED_REGISTRATION_EMAILS}
    return not allowed or email in allowed


def _session_lifetime(remember_me: bool = False) -> timedelta:
    return timedelta(days=REMEMBERED_SESSION_DAYS) if remember_me else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)


def _set_session_cookie(response: Response, token: str, *, remember_me: bool = False) -> None:
    response.set_cookie(
        key=getattr(settings, "COOKIE_NAME", "lexflow_session"),
        value=token,
        max_age=int(_session_lifetime(remember_me).total_seconds()),
        httponly=True,
        secure=getattr(settings, "COOKIE_SECURE", False),
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=getattr(settings, "COOKIE_NAME", "lexflow_session"),
        httponly=True,
        secure=getattr(settings, "COOKIE_SECURE", False),
        samesite="lax",
        path="/",
    )


async def create_session_token(
    db: AsyncSession,
    user: User,
    *,
    mfa_verified: bool = False,
    remember_me: bool = False,
) -> str:
    # AuthSession is tenant-RLS protected even on login/register, before CurrentUser exists.
    await _set_tenant_context(db, user.tenant_id)
    session = AuthSession(
        user_id=user.id,
        tenant_id=user.tenant_id,
        expires_at=datetime.now(timezone.utc) + _session_lifetime(remember_me),
        mfa_verified_at=datetime.now(timezone.utc) if mfa_verified else None,
    )
    db.add(session)
    await db.flush()
    return create_access_token(
        subject=user.id,
        tenant_id=user.tenant_id,
        session_id=session.id,
        mfa_verified=mfa_verified,
        expires_delta=_session_lifetime(remember_me),
    )


class UserRegister(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str
    tenant_name: str = Field(min_length=2, max_length=120)
    oab_number: str | None = Field(default=None, max_length=30)
    oab_uf: str | None = Field(default=None, min_length=2, max_length=2)

    @field_validator("full_name", "tenant_name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("valor muito curto")
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        validate_password_policy(value)
        return value

    @field_validator("oab_uf")
    @classmethod
    def normalize_oab_uf(cls, value: str | None) -> str | None:
        return value.strip().upper() if value else None


class UserLogin(BaseModel):
    email: EmailStr
    password: str
    otp_code: str | None = Field(default=None, max_length=128)
    remember_me: StrictBool = False

    @field_validator("password")
    @classmethod
    def validate_password_size(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("senha invalida")
        return value


class ProfileResponse(BaseModel):
    user_id: str
    user_name: str
    email: EmailStr
    role: str
    tenant_id: str
    tenant_name: str
    tenant_cnpj: str | None
    oab_number: str | None
    oab_uf: str | None
    professional_name: str | None
    professional_email: EmailStr | None
    professional_phone: str | None
    professional_address: dict | None
    tenant_legal_name: str | None
    tenant_email: EmailStr | None
    tenant_phone: str | None
    tenant_website: str | None
    tenant_address: dict | None
    tenant_timezone: str
    tenant_signature_city: str | None
    email_verified: bool
    email_verification_required: bool
    mfa_enabled: bool
    mfa_required: bool
    subscription_status: str
    trial_ends_at: datetime | None


def _profile(user: User, tenant: Tenant) -> dict:
    return {
        "user_id": user.id,
        "user_name": user.full_name,
        "email": user.email,
        "role": user.role,
        "tenant_id": user.tenant_id,
        "tenant_name": tenant.name,
        "tenant_cnpj": tenant.cnpj,
        "oab_number": user.oab_number,
        "oab_uf": user.oab_uf,
        "professional_name": getattr(user, "professional_name", None),
        "professional_email": getattr(user, "professional_email", None),
        "professional_phone": getattr(user, "professional_phone", None),
        "professional_address": getattr(user, "professional_address", None),
        "tenant_legal_name": getattr(tenant, "legal_name", None),
        "tenant_email": getattr(tenant, "office_email", None),
        "tenant_phone": getattr(tenant, "office_phone", None),
        "tenant_website": getattr(tenant, "website", None),
        "tenant_address": getattr(tenant, "office_address", None),
        "tenant_timezone": getattr(tenant, "timezone", None) or "America/Sao_Paulo",
        "tenant_signature_city": getattr(tenant, "signature_city", None),
        "email_verified": user.email_verified_at is not None,
        "email_verification_required": bool(
            settings.is_hardened_environment and user.email_verified_at is None
        ),
        "mfa_enabled": bool(user.mfa_enabled),
        "mfa_required": bool(
            settings.is_hardened_environment
            and getattr(settings, "PRIVILEGED_MFA_REQUIRED", True)
            and user.role in {"admin", "partner"}
            and not user.mfa_enabled
        ),
        "subscription_status": tenant.subscription_status,
        "trial_ends_at": tenant.trial_ends_at,
    }


async def _consume_recovery_code(db: AsyncSession, user: User, code: str) -> bool:
    token_hash = hash_account_token(code)
    token = await db.scalar(
        select(AccountToken)
        .where(
            AccountToken.user_id == user.id,
            AccountToken.tenant_id == user.tenant_id,
            AccountToken.token_type == "mfa_recovery",
            AccountToken.token_hash == token_hash,
            AccountToken.consumed_at.is_(None),
            AccountToken.expires_at > datetime.now(timezone.utc),
        )
        .with_for_update()
    )
    if not token:
        return False
    token.consumed_at = datetime.now(timezone.utc)
    return True


async def _verify_login_mfa(db: AsyncSession, user: User, otp_code: str | None) -> bool:
    if not user.mfa_enabled:
        return False
    if not otp_code or not user.mfa_secret_encrypted:
        return False
    try:
        counter = matching_totp_counter(decrypt_mfa_secret(user.mfa_secret_encrypted), otp_code)
        if counter is not None and (
            user.mfa_last_counter is None or counter > user.mfa_last_counter
        ):
            user.mfa_last_counter = counter
            return True
    except RuntimeError:
        raise HTTPException(status_code=503, detail="MFA temporarily unavailable.")
    return await _consume_recovery_code(db, user, otp_code)


@router.post("/register", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_in: UserRegister,
    request: Request,
    response: Response,
    _: None = Depends(require_trusted_origin),
    db: AsyncSession = Depends(get_db),
):
    email = str(user_in.email).lower()
    await _enforce_auth_rate_limit("register", request, email, limit=5, window_seconds=600)
    if not _registration_is_allowed(email):
        raise HTTPException(status_code=403, detail="Cadastro indisponivel para este e-mail.")
    tenant_slug = _slugify(user_in.tenant_name)
    if not tenant_slug:
        raise HTTPException(status_code=422, detail="Nome do escritorio invalido.")

    existing_user = await db.scalar(select(User.id).where(func.lower(User.email) == email))
    if existing_user:
        raise HTTPException(status_code=409, detail="E-mail ja cadastrado no sistema.")
    existing_tenant = await db.scalar(select(Tenant.id).where(Tenant.slug == tenant_slug))
    if existing_tenant:
        raise HTTPException(status_code=409, detail="Escritorio ja cadastrado no sistema.")

    now = datetime.now(timezone.utc)
    tenant = Tenant(
        name=user_in.tenant_name,
        slug=tenant_slug,
        subscription_status="trial",
        subscription_plan="trial",
        trial_starts_at=now,
        trial_ends_at=now + timedelta(days=getattr(settings, "DEFAULT_TRIAL_DAYS", 14)),
        quota_users=getattr(settings, "TRIAL_QUOTA_USERS", 3),
        quota_storage_bytes=getattr(settings, "TRIAL_QUOTA_STORAGE_BYTES", 1073741824),
        quota_messages=getattr(settings, "TRIAL_QUOTA_MESSAGES", 100),
    )
    db.add(tenant)
    try:
        await db.flush()
        user = User(
            tenant_id=tenant.id,
            full_name=user_in.full_name,
            email=email,
            hashed_password=get_password_hash(user_in.password),
            role="admin",
            oab_number=user_in.oab_number,
            oab_uf=user_in.oab_uf,
        )
        db.add(user)
        await db.flush()
        token = await create_session_token(db, user)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Usuario ou escritorio ja cadastrado.")

    _set_session_cookie(response, token)
    return ProfileResponse(**_profile(user, tenant))


@router.post("/login", response_model=ProfileResponse)
async def login(
    login_in: UserLogin,
    request: Request,
    response: Response,
    _: None = Depends(require_trusted_origin),
    db: AsyncSession = Depends(get_db),
):
    email = str(login_in.email).lower()
    await _enforce_auth_rate_limit("login", request, email, limit=10, window_seconds=300)
    result = await db.execute(
        select(User, Tenant)
        .join(Tenant, Tenant.id == User.tenant_id)
        .where(func.lower(User.email) == email)
    )
    row = result.first()
    user, tenant = row if row else (None, None)
    password_valid = verify_password(login_in.password, user.hashed_password if user else DUMMY_PASSWORD_HASH)
    if not user or not password_valid or not user.is_active or not tenant.is_active:
        raise HTTPException(status_code=401, detail="Credenciais invalidas.")

    await _set_tenant_context(db, user.tenant_id)
    # Serializes last-counter updates, so the same valid TOTP cannot create two
    # concurrent sessions before either request commits its replay marker.
    locked_user = await db.scalar(
        select(User)
        .where(User.id == user.id, User.tenant_id == user.tenant_id)
        .execution_options(populate_existing=True)
        .with_for_update()
    )
    if (
        not locked_user
        or not locked_user.is_active
        or not verify_password(login_in.password, locked_user.hashed_password)
    ):
        await db.rollback()
        raise HTTPException(status_code=401, detail="Credenciais invalidas.")
    user = locked_user
    mfa_verified = await _verify_login_mfa(db, user, login_in.otp_code)
    if user.mfa_enabled and not mfa_verified:
        await db.rollback()
        raise HTTPException(status_code=401, detail="Codigo MFA invalido.")

    token = await create_session_token(db, user, mfa_verified=mfa_verified, remember_me=login_in.remember_me)
    await db.commit()
    _set_session_cookie(response, token, remember_me=login_in.remember_me)
    return ProfileResponse(**_profile(user, tenant))


@router.get("/me", response_model=ProfileResponse)
async def me(current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    tenant = await db.scalar(select(Tenant).where(Tenant.id == current_user.tenant_id))
    if not tenant:
        raise HTTPException(status_code=401, detail="Sessao invalida ou expirada.")
    return ProfileResponse(**_profile(current_user, tenant))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    auth_session = getattr(request.state, "auth_session", None)
    if auth_session and auth_session.user_id == current_user.id:
        auth_session.revoked_at = datetime.now(timezone.utc)
        await revoke_session_push(db, tenant_id=current_user.tenant_id, session_id=auth_session.id)
        await db.commit()
    clear_session_cookie(response)
