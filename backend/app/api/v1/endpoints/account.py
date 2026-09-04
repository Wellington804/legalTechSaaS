from datetime import datetime, timedelta, timezone
from typing import Literal
from urllib.parse import quote, urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import (
    ProfileResponse,
    _enforce_auth_rate_limit,
    _profile,
    _set_session_cookie,
    clear_session_cookie,
    create_session_token,
)
from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import (
    CurrentUser,
    _set_tenant_context,
    ensure_tenant_write_access,
    require_privileged_mfa,
    require_roles,
    require_trusted_origin,
)
from app.core.security import (
    decrypt_mfa_secret,
    encrypt_mfa_secret,
    get_password_hash,
    hash_account_token,
    matching_totp_counter,
    new_opaque_token,
    new_recovery_codes,
    new_totp_secret,
    validate_password_policy,
    verify_password,
    verify_totp_code,
)
from app.models.account import AccountToken, PrivacyRequest, SubscriptionRequest, TeamInvitation
from app.models.notification import NotificationDelivery
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.workspace import Address, normalize_phone
from app.services.workspace_service import document_storage_used
from app.services.audit_service import AuditService


router = APIRouter()
ROLES = {"admin", "partner", "lawyer", "paralegal"}
GENERIC_ACCOUNT_RESPONSE = {"detail": "Se a conta existir, voce recebera instrucoes."}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _client_details(request: Request) -> tuple[str | None, str | None]:
    return (
        request.client.host if request.client else None,
        request.headers.get("user-agent", "")[:512] or None,
    )


async def _audit(
    db: AsyncSession,
    request: Request,
    *,
    tenant_id: str,
    user_id: str | None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    details: dict | None = None,
) -> None:
    ip_address, user_agent = _client_details(request)
    await AuditService.log_action(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent,
    )


def _normalize_optional(value: str | None) -> str | None:
    return value.strip() if value and value.strip() else None


def _normalize_oab_uf(value: str | None) -> str | None:
    value = _normalize_optional(value)
    if value and len(value) != 2:
        raise ValueError("UF da OAB invalida")
    return value.upper() if value else None


def _normalize_cnpj(value: str | None) -> str | None:
    value = _normalize_optional(value)
    if not value:
        return None
    digits = "".join(character for character in value if character.isdigit())
    if len(digits) != 14:
        raise ValueError("CNPJ invalido")
    return digits


def _normalize_privacy_url(value: str | None) -> str | None:
    value = _normalize_optional(value)
    if not value:
        return None
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password or parsed.fragment:
        raise ValueError("URL do aviso deve usar HTTPS, sem credenciais ou fragmento")
    return value


def _account_email_ready() -> bool:
    return bool(
        getattr(settings, "ACCOUNT_EMAILS_ENABLED", False)
        and getattr(settings, "RESEND_ENABLED", False)
        and not getattr(settings, "NOTIFICATIONS_DRY_RUN", True)
        and getattr(settings, "RESEND_API_KEY", None)
        and getattr(settings, "RESEND_FROM_EMAIL", None)
        and getattr(settings, "FRONTEND_URL", None)
    )


def _trusted_frontend_url() -> str:
    raw_url = getattr(settings, "FRONTEND_URL", None)
    if not raw_url:
        raise HTTPException(status_code=503, detail="Entrega de e-mail de conta indisponivel.")
    parsed = urlsplit(raw_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    allowed_origins = {origin_item.rstrip("/") for origin_item in settings.CORS_ORIGINS}
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.query
        or parsed.fragment
        or origin.rstrip("/") not in allowed_origins
    ):
        raise HTTPException(status_code=503, detail="Entrega de e-mail de conta indisponivel.")
    return raw_url.rstrip("/")


async def _send_account_email(
    *,
    recipient: str,
    action: str,
    raw_token: str,
    idempotency_key: str,
) -> None:
    if not _account_email_ready():
        raise HTTPException(status_code=503, detail="Entrega de e-mail de conta indisponivel.")
    frontend_url = _trusted_frontend_url()
    action_url = (
        f"{frontend_url}/account/access#action={quote(action, safe='')}&"
        f"token={quote(raw_token, safe='')}"
    )
    payload = {
        "from": settings.RESEND_FROM_EMAIL,
        "to": [recipient],
        "subject": "Acao necessaria na sua conta LegalTech",
        "text": f"Use este link para continuar com seguranca: {action_url}",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                    "Idempotency-Key": idempotency_key,
                },
                json=payload,
            )
    except (httpx.TimeoutException, httpx.NetworkError):
        raise HTTPException(status_code=503, detail="Entrega de e-mail de conta indisponivel.")
    if response.status_code >= 300:
        raise HTTPException(status_code=503, detail="Entrega de e-mail de conta indisponivel.")


async def _create_email_token(
    db: AsyncSession,
    *,
    user: User,
    token_type: str,
    expires_in: timedelta,
) -> tuple[AccountToken, str]:
    # Password reset begins unauthenticated, so establish the user-derived
    # transaction scope before touching tenant-RLS-protected credentials.
    await _set_tenant_context(db, user.tenant_id)
    now = _utcnow()
    existing = (
        await db.execute(
            select(AccountToken)
            .where(
                AccountToken.user_id == user.id,
                AccountToken.tenant_id == user.tenant_id,
                AccountToken.token_type == token_type,
                AccountToken.consumed_at.is_(None),
            )
            .with_for_update()
        )
    ).scalars()
    for token in existing:
        token.consumed_at = now
    raw_token = new_opaque_token()
    token = AccountToken(
        user_id=user.id,
        tenant_id=user.tenant_id,
        token_type=token_type,
        token_hash=hash_account_token(raw_token),
        expires_at=now + expires_in,
    )
    db.add(token)
    await db.flush()
    return token, raw_token


async def _get_token_user(
    db: AsyncSession, raw_token: str, token_type: str
) -> tuple[AccountToken, User] | None:
    token_hash = hash_account_token(raw_token)
    tenant_id = await _public_account_token_tenant(db, token_hash, token_type)
    if not tenant_id and db.bind and db.bind.dialect.name == "postgresql":
        return None
    token_query = (
        select(AccountToken)
        .where(
            AccountToken.token_hash == token_hash,
            AccountToken.token_type == token_type,
            AccountToken.consumed_at.is_(None),
            AccountToken.expires_at > _utcnow(),
        )
    )
    if tenant_id:
        token_query = token_query.where(AccountToken.tenant_id == tenant_id)
    token = await db.scalar(token_query.with_for_update())
    if not token:
        return None
    user = await db.scalar(
        select(User).where(
            User.id == token.user_id,
            User.tenant_id == token.tenant_id,
            User.is_active.is_(True),
        )
    )
    return (token, user) if user else None


async def _public_account_token_tenant(
    db: AsyncSession, token_hash: str, token_type: str
) -> str | None:
    if not db.bind or db.bind.dialect.name != "postgresql":
        return None
    tenant_id = await db.scalar(
        text("SELECT public.account_token_tenant_for_hash(:token_hash, :token_type)"),
        {"token_hash": token_hash, "token_type": token_type},
    )
    if isinstance(tenant_id, str) and tenant_id:
        await _set_tenant_context(db, tenant_id)
        return tenant_id
    return None


async def _public_team_invitation_tenant(
    db: AsyncSession, token_hash: str
) -> str | None:
    if not db.bind or db.bind.dialect.name != "postgresql":
        return None
    tenant_id = await db.scalar(
        text("SELECT public.team_invitation_tenant_for_hash(:token_hash)"),
        {"token_hash": token_hash},
    )
    if isinstance(tenant_id, str) and tenant_id:
        await _set_tenant_context(db, tenant_id)
        return tenant_id
    return None


async def _revoke_user_sessions(db: AsyncSession, user: User) -> None:
    from app.models.account import AuthSession

    await db.execute(
        update(AuthSession)
        .where(
            AuthSession.user_id == user.id,
            AuthSession.tenant_id == user.tenant_id,
            AuthSession.revoked_at.is_(None),
        )
        .values(revoked_at=_utcnow())
    )


async def _locked_tenant(db: AsyncSession, tenant_id: str) -> Tenant:
    tenant = await db.scalar(select(Tenant).where(Tenant.id == tenant_id).with_for_update())
    if not tenant or not tenant.is_active:
        raise HTTPException(status_code=404, detail="Escritorio nao encontrado.")
    return tenant


async def _reserved_user_count(db: AsyncSession, tenant: Tenant) -> int:
    active_users = await db.scalar(
        select(func.count(User.id)).where(User.tenant_id == tenant.id, User.is_active.is_(True))
    )
    pending_invites = await db.scalar(
        select(func.count(TeamInvitation.id)).where(
            TeamInvitation.tenant_id == tenant.id,
            TeamInvitation.accepted_at.is_(None),
            TeamInvitation.revoked_at.is_(None),
            TeamInvitation.expires_at > _utcnow(),
        )
    )
    return int(active_users or 0) + int(pending_invites or 0)


async def _ensure_user_slot(db: AsyncSession, tenant: Tenant) -> None:
    if await _reserved_user_count(db, tenant) >= tenant.quota_users:
        raise HTTPException(status_code=409, detail="Limite de usuarios do plano atingido.")


async def _verify_current_mfa(db: AsyncSession, current_user: User, code: str) -> bool:
    if not current_user.mfa_enabled or not current_user.mfa_secret_encrypted:
        return False
    try:
        if verify_totp_code(decrypt_mfa_secret(current_user.mfa_secret_encrypted), code):
            return True
    except RuntimeError:
        raise HTTPException(status_code=503, detail="MFA temporariamente indisponivel.")
    token = await db.scalar(
        select(AccountToken)
        .where(
            AccountToken.user_id == current_user.id,
            AccountToken.tenant_id == current_user.tenant_id,
            AccountToken.token_type == "mfa_recovery",
            AccountToken.token_hash == hash_account_token(code),
            AccountToken.consumed_at.is_(None),
            AccountToken.expires_at > _utcnow(),
        )
        .with_for_update()
    )
    if not token:
        return False
    token.consumed_at = _utcnow()
    return True


def _require_recent_password_session(request: Request) -> None:
    auth_session = getattr(request.state, "auth_session", None)
    created_at = getattr(auth_session, "created_at", None)
    if created_at and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    if not created_at or created_at < _utcnow() - timedelta(minutes=60):
        raise HTTPException(
            status_code=403,
            detail="Entre novamente com a senha antes de alterar o MFA.",
        )


async def _locked_current_user(db: AsyncSession, current_user: User) -> User:
    locked_user = await db.scalar(
        select(User)
        .where(User.id == current_user.id, User.tenant_id == current_user.tenant_id)
        .execution_options(populate_existing=True)
        .with_for_update()
    )
    if not locked_user or not locked_user.is_active:
        raise HTTPException(status_code=401, detail="Sessao invalida ou expirada.")
    return locked_user


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    oab_number: str | None = Field(default=None, max_length=30)
    oab_uf: str | None = Field(default=None, max_length=2)
    professional_name: str | None = Field(default=None, max_length=120)
    professional_email: EmailStr | None = None
    professional_phone: str | None = Field(default=None, max_length=32)
    professional_address: Address | None = None

    @field_validator("full_name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        return _normalize_optional(value)

    @field_validator("oab_number", "professional_name")
    @classmethod
    def normalize_oab_number(cls, value: str | None) -> str | None:
        return _normalize_optional(value)

    @field_validator("professional_phone")
    @classmethod
    def normalize_professional_phone(cls, value: str | None) -> str | None:
        return normalize_phone(value)

    @field_validator("oab_uf")
    @classmethod
    def normalize_oab_state(cls, value: str | None) -> str | None:
        return _normalize_oab_uf(value)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        validate_password_policy(value)
        return value


class EmailRequest(BaseModel):
    email: EmailStr


class TokenConfirmation(BaseModel):
    token: str = Field(min_length=20, max_length=256)


class PasswordResetConfirmation(TokenConfirmation):
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        validate_password_policy(value)
        return value


class TeamInviteCreate(BaseModel):
    email: EmailStr
    role: str

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        if value not in ROLES:
            raise ValueError("papel invalido")
        return value


class TeamInviteAccept(TokenConfirmation):
    full_name: str = Field(min_length=2, max_length=120)
    password: str
    oab_number: str | None = Field(default=None, max_length=30)
    oab_uf: str | None = Field(default=None, max_length=2)

    @field_validator("full_name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return _normalize_optional(value) or ""

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        validate_password_policy(value)
        return value

    @field_validator("oab_number")
    @classmethod
    def normalize_oab_number(cls, value: str | None) -> str | None:
        return _normalize_optional(value)

    @field_validator("oab_uf")
    @classmethod
    def normalize_oab_state(cls, value: str | None) -> str | None:
        return _normalize_oab_uf(value)


class TeamMemberUpdate(BaseModel):
    role: str

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        if value not in ROLES:
            raise ValueError("papel invalido")
        return value


class OfficeUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    cnpj: str | None = Field(default=None, max_length=32)
    legal_name: str | None = Field(default=None, max_length=160)
    office_email: EmailStr | None = None
    office_phone: str | None = Field(default=None, max_length=32)
    website: str | None = Field(default=None, max_length=2048)
    office_address: Address | None = None
    timezone: str = Field(default="America/Sao_Paulo", max_length=64)
    signature_city: str | None = Field(default=None, max_length=120)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return _normalize_optional(value) or ""

    @field_validator("legal_name", "website", "signature_city")
    @classmethod
    def normalize_optional_fields(cls, value: str | None) -> str | None:
        return _normalize_optional(value)

    @field_validator("office_phone")
    @classmethod
    def normalize_office_phone(cls, value: str | None) -> str | None:
        return normalize_phone(value)

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("fuso horario invalido") from exc
        return value

    @field_validator("cnpj")
    @classmethod
    def normalize_cnpj(cls, value: str | None) -> str | None:
        return _normalize_cnpj(value)


class OnboardingUpdate(BaseModel):
    office_name: str | None = Field(default=None, min_length=2, max_length=120)
    cnpj: str | None = Field(default=None, max_length=32)
    oab_number: str | None = Field(default=None, max_length=30)
    oab_uf: str | None = Field(default=None, max_length=2)

    @field_validator("office_name", "oab_number")
    @classmethod
    def normalize_optional(cls, value: str | None) -> str | None:
        return _normalize_optional(value)

    @field_validator("cnpj")
    @classmethod
    def normalize_cnpj(cls, value: str | None) -> str | None:
        return _normalize_cnpj(value)

    @field_validator("oab_uf")
    @classmethod
    def normalize_oab_state(cls, value: str | None) -> str | None:
        return _normalize_oab_uf(value)


class SubscriptionRequestInput(BaseModel):
    message: str | None = Field(default=None, max_length=1000)

    @field_validator("message")
    @classmethod
    def normalize_message(cls, value: str | None) -> str | None:
        return _normalize_optional(value)


class MfaCode(BaseModel):
    code: str = Field(min_length=6, max_length=128)


class MfaDisable(MfaCode):
    current_password: str


class MfaSetupResponse(BaseModel):
    secret: str
    provisioning_uri: str


class MfaRecoveryCodesResponse(BaseModel):
    recovery_codes: list[str]


class TeamMemberResponse(BaseModel):
    id: str
    full_name: str
    email: EmailStr
    role: str
    is_active: bool
    oab_number: str | None
    oab_uf: str | None


class TeamInviteResponse(BaseModel):
    id: str
    email: EmailStr
    role: str
    expires_at: datetime
    invite_link: str
    delivery: str = "manual_copy"


class SubscriptionResponse(BaseModel):
    plan: str
    status: str
    trial_starts_at: datetime | None
    trial_ends_at: datetime | None
    subscription_ends_at: datetime | None
    cancel_at_period_end: bool
    quota_users: int
    active_users: int
    quota_storage_bytes: int
    storage_used_bytes: int
    quota_messages: int
    messages_used: int
    cancellation_request_pending: bool


class PrivacySettingsUpdate(BaseModel):
    privacy_notice_url: str | None = Field(default=None, max_length=2048)
    privacy_notice_version: str | None = Field(default=None, max_length=64)
    privacy_contact: EmailStr | None = None
    data_retention_days: int | None = Field(default=None, ge=30, le=3650)

    @field_validator("privacy_notice_url")
    @classmethod
    def valid_notice_url(cls, value: str | None) -> str | None:
        return _normalize_privacy_url(value)

    @field_validator("privacy_notice_version")
    @classmethod
    def valid_notice_version(cls, value: str | None) -> str | None:
        return _normalize_optional(value)


class PrivacySettingsResponse(PrivacySettingsUpdate):
    configured: bool


class PrivacyRequestInput(BaseModel):
    request_type: Literal["export", "deletion", "anonymization"]
    scope: Literal["self", "tenant"] = "self"
    reason: str | None = Field(default=None, max_length=2000)

    @field_validator("reason")
    @classmethod
    def valid_reason(cls, value: str | None) -> str | None:
        return _normalize_optional(value)


class PrivacyRequestResponse(BaseModel):
    id: str
    requested_by_user_id: str | None
    request_type: str
    scope: str
    status: str
    reason: str | None
    resolution_note: str | None
    created_at: datetime
    resolved_at: datetime | None


def _privacy_settings(tenant: Tenant) -> PrivacySettingsResponse:
    values = {
        "privacy_notice_url": tenant.privacy_notice_url,
        "privacy_notice_version": tenant.privacy_notice_version,
        "privacy_contact": tenant.privacy_contact,
        "data_retention_days": tenant.data_retention_days,
    }
    return PrivacySettingsResponse(**values, configured=all(values.values()))


def _privacy_request(request: PrivacyRequest) -> PrivacyRequestResponse:
    return PrivacyRequestResponse(
        id=request.id,
        requested_by_user_id=request.requested_by_user_id,
        request_type=request.request_type,
        scope=request.scope,
        status=request.status,
        reason=request.reason,
        resolution_note=request.resolution_note,
        created_at=request.created_at,
        resolved_at=request.resolved_at,
    )


def _team_member(user: User) -> TeamMemberResponse:
    return TeamMemberResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        oab_number=user.oab_number,
        oab_uf=user.oab_uf,
    )


@router.get("/profile", response_model=ProfileResponse)
async def profile(current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    tenant = await db.scalar(select(Tenant).where(Tenant.id == current_user.tenant_id))
    if not tenant:
        raise HTTPException(status_code=401, detail="Sessao invalida ou expirada.")
    return ProfileResponse(**_profile(current_user, tenant))


@router.patch("/profile", response_model=ProfileResponse)
async def update_profile(
    payload: ProfileUpdate,
    request: Request,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    changes = payload.model_dump(exclude_unset=True)
    if payload.professional_email is not None:
        changes["professional_email"] = str(payload.professional_email)
    for field, value in changes.items():
        setattr(current_user, field, value)
    tenant = await db.scalar(select(Tenant).where(Tenant.id == current_user.tenant_id))
    if not tenant:
        raise HTTPException(status_code=401, detail="Sessao invalida ou expirada.")
    await _audit(
        db,
        request,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        action="ACCOUNT_PROFILE_UPDATED",
        resource_type="user",
        resource_id=current_user.id,
        details={"fields": sorted(changes)},
    )
    await db.commit()
    return ProfileResponse(**_profile(current_user, tenant))


@router.post("/password", response_model=ProfileResponse)
async def change_password(
    payload: PasswordChange,
    request: Request,
    response: Response,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    await _enforce_auth_rate_limit(
        "password-change", request, current_user.email, limit=5, window_seconds=600
    )
    current_user = await _locked_current_user(db, current_user)
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Senha atual invalida.")
    current_user.hashed_password = get_password_hash(payload.new_password)
    await _revoke_user_sessions(db, current_user)
    session_payload = getattr(request.state, "auth_payload", {})
    new_token = await create_session_token(
        db,
        current_user,
        mfa_verified=bool(session_payload.get("mfa") and current_user.mfa_enabled),
    )
    tenant = await db.scalar(select(Tenant).where(Tenant.id == current_user.tenant_id))
    await _audit(
        db,
        request,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        action="ACCOUNT_PASSWORD_CHANGED",
        resource_type="user",
        resource_id=current_user.id,
    )
    await db.commit()
    _set_session_cookie(response, new_token)
    return ProfileResponse(**_profile(current_user, tenant))


@router.post("/sessions/revoke-all", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_all_sessions(
    request: Request,
    response: Response,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    await _revoke_user_sessions(db, current_user)
    await _audit(
        db,
        request,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        action="ACCOUNT_SESSIONS_REVOKED",
        resource_type="user",
        resource_id=current_user.id,
    )
    await db.commit()
    clear_session_cookie(response)


@router.post("/email-verifications/request", status_code=status.HTTP_202_ACCEPTED)
async def request_email_verification(
    request: Request,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    if current_user.email_verified_at is not None:
        return GENERIC_ACCOUNT_RESPONSE
    token, raw_token = await _create_email_token(
        db, user=current_user, token_type="email_verify", expires_in=timedelta(hours=24)
    )
    await _send_account_email(
        recipient=current_user.email,
        action="verify",
        raw_token=raw_token,
        idempotency_key=token.id,
    )
    await _audit(
        db,
        request,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        action="ACCOUNT_EMAIL_VERIFICATION_REQUESTED",
        resource_type="user",
        resource_id=current_user.id,
    )
    await db.commit()
    return GENERIC_ACCOUNT_RESPONSE


@router.post("/email-verifications/confirm", status_code=status.HTTP_204_NO_CONTENT)
async def confirm_email_verification(
    payload: TokenConfirmation,
    request: Request,
    _: None = Depends(require_trusted_origin),
    db: AsyncSession = Depends(get_db),
):
    token_user = await _get_token_user(db, payload.token, "email_verify")
    if not token_user:
        raise HTTPException(status_code=400, detail="Token invalido ou expirado.")
    token, user = token_user
    await _set_tenant_context(db, user.tenant_id)
    user.email_verified_at = _utcnow()
    token.consumed_at = _utcnow()
    await _audit(
        db,
        request,
        tenant_id=user.tenant_id,
        user_id=user.id,
        action="ACCOUNT_EMAIL_VERIFIED",
        resource_type="user",
        resource_id=user.id,
    )
    await db.commit()


@router.post("/password-resets/request", status_code=status.HTTP_202_ACCEPTED)
async def request_password_reset(
    payload: EmailRequest,
    request: Request,
    _: None = Depends(require_trusted_origin),
    db: AsyncSession = Depends(get_db),
):
    email = str(payload.email).lower()
    await _enforce_auth_rate_limit("password-reset", request, email, limit=5, window_seconds=600)
    if not _account_email_ready():
        raise HTTPException(status_code=503, detail="Entrega de e-mail de conta indisponivel.")
    user = await db.scalar(select(User).where(func.lower(User.email) == email, User.is_active.is_(True)))
    if not user:
        return GENERIC_ACCOUNT_RESPONSE
    token, raw_token = await _create_email_token(
        db, user=user, token_type="password_reset", expires_in=timedelta(hours=1)
    )
    await _send_account_email(
        recipient=user.email,
        action="reset",
        raw_token=raw_token,
        idempotency_key=token.id,
    )
    await db.commit()
    return GENERIC_ACCOUNT_RESPONSE


@router.post("/password-resets/confirm", status_code=status.HTTP_204_NO_CONTENT)
async def confirm_password_reset(
    payload: PasswordResetConfirmation,
    request: Request,
    _: None = Depends(require_trusted_origin),
    db: AsyncSession = Depends(get_db),
):
    token_user = await _get_token_user(db, payload.token, "password_reset")
    if not token_user:
        raise HTTPException(status_code=400, detail="Token invalido ou expirado.")
    token, user = token_user
    await _set_tenant_context(db, user.tenant_id)
    user.hashed_password = get_password_hash(payload.new_password)
    token.consumed_at = _utcnow()
    await _revoke_user_sessions(db, user)
    await _audit(
        db,
        request,
        tenant_id=user.tenant_id,
        user_id=user.id,
        action="ACCOUNT_PASSWORD_RESET",
        resource_type="user",
        resource_id=user.id,
    )
    await db.commit()


@router.get("/team", response_model=list[TeamMemberResponse])
async def list_team(
    current_user: CurrentUser,
    _: User = Depends(require_roles("admin", "partner")),
    __: User = Depends(require_privileged_mfa),
    db: AsyncSession = Depends(get_db),
):
    members = (
        await db.execute(
            select(User).where(User.tenant_id == current_user.tenant_id).order_by(User.created_at)
        )
    ).scalars().all()
    return [_team_member(member) for member in members]


@router.get("/team/invites")
async def list_team_invites(
    current_user: CurrentUser,
    _: User = Depends(require_roles("admin")),
    __: User = Depends(require_privileged_mfa),
    db: AsyncSession = Depends(get_db),
):
    invitations = (await db.scalars(select(TeamInvitation).where(
        TeamInvitation.tenant_id == current_user.tenant_id,
        TeamInvitation.accepted_at.is_(None), TeamInvitation.revoked_at.is_(None),
        TeamInvitation.expires_at > _utcnow(),
    ).order_by(TeamInvitation.created_at.desc()).limit(200))).all()
    return {"items": [{"id": row.id, "email": row.email, "role": row.role, "expires_at": row.expires_at} for row in invitations]}


@router.post("/team/invites", response_model=TeamInviteResponse, status_code=status.HTTP_201_CREATED)
async def create_team_invite(
    payload: TeamInviteCreate,
    request: Request,
    current_user: CurrentUser,
    _: User = Depends(require_roles("admin")),
    __: User = Depends(require_privileged_mfa),
    db: AsyncSession = Depends(get_db),
):
    await ensure_tenant_write_access(db, current_user.tenant_id)
    tenant = await _locked_tenant(db, current_user.tenant_id)
    await _ensure_user_slot(db, tenant)
    email = str(payload.email).lower()
    existing_user = await db.scalar(select(User.id).where(func.lower(User.email) == email))
    if existing_user:
        raise HTTPException(status_code=409, detail="E-mail ja cadastrado no sistema.")

    invitation = await db.scalar(
        select(TeamInvitation)
        .where(TeamInvitation.tenant_id == tenant.id, TeamInvitation.email == email)
        .with_for_update()
    )
    now = _utcnow()
    raw_token = new_opaque_token()
    if invitation and invitation.accepted_at is not None:
        raise HTTPException(status_code=409, detail="Convite ja utilizado.")
    if invitation and invitation.revoked_at is None and invitation.expires_at > now:
        raise HTTPException(status_code=409, detail="Ja existe um convite pendente para este e-mail.")
    if invitation:
        invitation.invited_by_user_id = current_user.id
        invitation.role = payload.role
        invitation.token_hash = hash_account_token(raw_token)
        invitation.expires_at = now + timedelta(days=7)
        invitation.accepted_at = None
        invitation.revoked_at = None
    else:
        invitation = TeamInvitation(
            tenant_id=tenant.id,
            invited_by_user_id=current_user.id,
            email=email,
            role=payload.role,
            token_hash=hash_account_token(raw_token),
            expires_at=now + timedelta(days=7),
        )
        db.add(invitation)
    await db.flush()
    frontend_url = getattr(settings, "FRONTEND_URL", None)
    if not frontend_url:
        raise HTTPException(status_code=503, detail="URL da aplicacao nao configurada para convites.")
    invite_link = (
        f"{frontend_url.rstrip('/')}/account/access#action=invite&"
        f"token={quote(raw_token, safe='')}"
    )
    await _audit(
        db,
        request,
        tenant_id=tenant.id,
        user_id=current_user.id,
        action="TEAM_INVITATION_CREATED",
        resource_type="team_invitation",
        resource_id=invitation.id,
        details={"role": invitation.role},
    )
    await db.commit()
    return TeamInviteResponse(
        id=invitation.id,
        email=invitation.email,
        role=invitation.role,
        expires_at=invitation.expires_at,
        invite_link=invite_link,
    )


@router.post("/team/invites/accept", status_code=status.HTTP_204_NO_CONTENT)
async def accept_team_invite(
    payload: TeamInviteAccept,
    request: Request,
    _: None = Depends(require_trusted_origin),
    db: AsyncSession = Depends(get_db),
): 
    token_hash = hash_account_token(payload.token)
    tenant_id = await _public_team_invitation_tenant(db, token_hash)
    if not tenant_id and db.bind and db.bind.dialect.name == "postgresql":
        raise HTTPException(status_code=400, detail="Convite invalido ou expirado.")
    if not tenant_id:
        preliminary_invite = await db.scalar(
            select(TeamInvitation).where(TeamInvitation.token_hash == token_hash)
        )
        tenant_id = preliminary_invite.tenant_id if preliminary_invite else None
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Convite invalido ou expirado.")
    tenant = await _locked_tenant(db, tenant_id)
    invitation = await db.scalar(
        select(TeamInvitation)
        .where(TeamInvitation.tenant_id == tenant.id, TeamInvitation.token_hash == token_hash)
        .with_for_update()
    )
    if (
        not invitation
        or invitation.token_hash != token_hash
        or invitation.accepted_at is not None
        or invitation.revoked_at is not None
        or invitation.expires_at <= _utcnow()
    ):
        raise HTTPException(status_code=400, detail="Convite invalido ou expirado.")
    await ensure_tenant_write_access(db, tenant.id)
    if await _reserved_user_count(db, tenant) > tenant.quota_users:
        raise HTTPException(status_code=409, detail="Limite de usuarios do plano atingido.")
    existing_user = await db.scalar(select(User.id).where(func.lower(User.email) == invitation.email))
    if existing_user:
        raise HTTPException(status_code=400, detail="Convite invalido ou expirado.")

    user = User(
        tenant_id=tenant.id,
        full_name=payload.full_name,
        email=invitation.email,
        hashed_password=get_password_hash(payload.password),
        role=invitation.role,
        oab_number=payload.oab_number,
        oab_uf=payload.oab_uf,
    )
    db.add(user)
    invitation.accepted_at = _utcnow()
    await _set_tenant_context(db, tenant.id)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Convite invalido ou expirado.")
    await _audit(
        db,
        request,
        tenant_id=tenant.id,
        user_id=user.id,
        action="TEAM_INVITATION_ACCEPTED",
        resource_type="team_invitation",
        resource_id=invitation.id,
    )
    await db.commit()


@router.post("/team/invites/{invite_id}/cancel", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_team_invite(
    invite_id: str,
    request: Request,
    current_user: CurrentUser,
    _: User = Depends(require_roles("admin")),
    __: User = Depends(require_privileged_mfa),
    db: AsyncSession = Depends(get_db),
):
    invitation = await db.scalar(
        select(TeamInvitation)
        .where(TeamInvitation.id == invite_id, TeamInvitation.tenant_id == current_user.tenant_id)
        .with_for_update()
    )
    if not invitation or invitation.accepted_at is not None:
        raise HTTPException(status_code=404, detail="Convite nao encontrado.")
    invitation.revoked_at = _utcnow()
    await _audit(
        db,
        request,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        action="TEAM_INVITATION_CANCELLED",
        resource_type="team_invitation",
        resource_id=invitation.id,
    )
    await db.commit()


@router.patch("/team/{member_id}", response_model=TeamMemberResponse)
async def update_team_member(
    member_id: str,
    payload: TeamMemberUpdate,
    request: Request,
    current_user: CurrentUser,
    _: User = Depends(require_roles("admin")),
    __: User = Depends(require_privileged_mfa),
    db: AsyncSession = Depends(get_db),
):
    await _locked_tenant(db, current_user.tenant_id)
    member = await db.scalar(
        select(User)
        .where(User.id == member_id, User.tenant_id == current_user.tenant_id)
        .with_for_update()
    )
    if not member:
        raise HTTPException(status_code=404, detail="Membro nao encontrado.")
    if member.role == "admin" and member.is_active and payload.role != "admin":
        active_admins = await db.scalar(
            select(func.count(User.id)).where(
                User.tenant_id == current_user.tenant_id,
                User.role == "admin",
                User.is_active.is_(True),
            )
        )
        if int(active_admins or 0) <= 1:
            raise HTTPException(status_code=409, detail="O ultimo administrador nao pode perder acesso.")
    member.role = payload.role
    await _audit(
        db,
        request,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        action="TEAM_MEMBER_ROLE_UPDATED",
        resource_type="user",
        resource_id=member.id,
        details={"role": member.role},
    )
    await db.commit()
    return _team_member(member)


@router.post("/team/{member_id}/deactivate", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_team_member(
    member_id: str,
    request: Request,
    current_user: CurrentUser,
    _: User = Depends(require_roles("admin")),
    __: User = Depends(require_privileged_mfa),
    db: AsyncSession = Depends(get_db),
):
    await _locked_tenant(db, current_user.tenant_id)
    member = await db.scalar(
        select(User)
        .where(User.id == member_id, User.tenant_id == current_user.tenant_id)
        .with_for_update()
    )
    if not member:
        raise HTTPException(status_code=404, detail="Membro nao encontrado.")
    if member.id == current_user.id:
        raise HTTPException(status_code=409, detail="Nao e possivel desativar a propria conta.")
    if member.role == "admin" and member.is_active:
        active_admins = await db.scalar(
            select(func.count(User.id)).where(
                User.tenant_id == current_user.tenant_id,
                User.role == "admin",
                User.is_active.is_(True),
            )
        )
        if int(active_admins or 0) <= 1:
            raise HTTPException(status_code=409, detail="O ultimo administrador nao pode perder acesso.")
    if member.is_active:
        member.is_active = False
        await _revoke_user_sessions(db, member)
    await _audit(
        db,
        request,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        action="TEAM_MEMBER_DEACTIVATED",
        resource_type="user",
        resource_id=member.id,
    )
    await db.commit()


@router.post("/team/{member_id}/reactivate", response_model=TeamMemberResponse)
async def reactivate_team_member(
    member_id: str,
    request: Request,
    current_user: CurrentUser,
    _: User = Depends(require_roles("admin")),
    __: User = Depends(require_privileged_mfa),
    db: AsyncSession = Depends(get_db),
):
    await ensure_tenant_write_access(db, current_user.tenant_id)
    tenant = await _locked_tenant(db, current_user.tenant_id)
    member = await db.scalar(
        select(User)
        .where(User.id == member_id, User.tenant_id == current_user.tenant_id)
        .with_for_update()
    )
    if not member:
        raise HTTPException(status_code=404, detail="Membro nao encontrado.")
    if not member.is_active:
        await _ensure_user_slot(db, tenant)
        member.is_active = True
    await _audit(
        db,
        request,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        action="TEAM_MEMBER_REACTIVATED",
        resource_type="user",
        resource_id=member.id,
    )
    await db.commit()
    return _team_member(member)


@router.get("/subscription", response_model=SubscriptionResponse)
async def subscription_summary(current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    tenant = await db.scalar(select(Tenant).where(Tenant.id == current_user.tenant_id))
    if not tenant:
        raise HTTPException(status_code=401, detail="Sessao invalida ou expirada.")
    active_users = await db.scalar(
        select(func.count(User.id)).where(User.tenant_id == tenant.id, User.is_active.is_(True))
    )
    storage_used_bytes = await document_storage_used(db, tenant.id)
    month_start = _utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    messages_used = await db.scalar(
        select(func.count(NotificationDelivery.id)).where(
            NotificationDelivery.tenant_id == tenant.id,
            NotificationDelivery.created_at >= month_start,
        )
    )
    cancellation_request = await db.scalar(
        select(SubscriptionRequest.id).where(
            SubscriptionRequest.tenant_id == tenant.id,
            SubscriptionRequest.request_type == "cancellation",
            SubscriptionRequest.status.in_(("received", "in_progress")),
        )
    )
    return SubscriptionResponse(
        plan=tenant.subscription_plan,
        status=tenant.subscription_status,
        trial_starts_at=tenant.trial_starts_at,
        trial_ends_at=tenant.trial_ends_at,
        subscription_ends_at=tenant.subscription_ends_at,
        cancel_at_period_end=tenant.cancel_at_period_end,
        quota_users=tenant.quota_users,
        active_users=int(active_users or 0),
        quota_storage_bytes=tenant.quota_storage_bytes,
        storage_used_bytes=int(storage_used_bytes or 0),
        quota_messages=tenant.quota_messages,
        messages_used=int(messages_used or 0),
        cancellation_request_pending=bool(cancellation_request),
    )


@router.patch("/office", response_model=ProfileResponse)
async def update_office(
    payload: OfficeUpdate,
    request: Request,
    current_user: CurrentUser,
    _: User = Depends(require_roles("admin")),
    __: User = Depends(require_privileged_mfa),
    db: AsyncSession = Depends(get_db),
):
    await ensure_tenant_write_access(db, current_user.tenant_id)
    tenant = await _locked_tenant(db, current_user.tenant_id)
    tenant.name = payload.name
    tenant.cnpj = payload.cnpj
    tenant.legal_name = payload.legal_name
    tenant.office_email = str(payload.office_email) if payload.office_email else None
    tenant.office_phone = payload.office_phone
    tenant.website = payload.website
    tenant.office_address = payload.office_address.model_dump() if payload.office_address else None
    tenant.timezone = payload.timezone
    tenant.signature_city = payload.signature_city
    await _audit(
        db,
        request,
        tenant_id=tenant.id,
        user_id=current_user.id,
        action="OFFICE_UPDATED",
        resource_type="tenant",
        resource_id=tenant.id,
    )
    await db.commit()
    return ProfileResponse(**_profile(current_user, tenant))


@router.get("/privacy", response_model=PrivacySettingsResponse)
async def privacy_settings(
    current_user: CurrentUser,
    _: User = Depends(require_privileged_mfa),
    db: AsyncSession = Depends(get_db),
):
    tenant = await db.scalar(select(Tenant).where(Tenant.id == current_user.tenant_id))
    if not tenant:
        raise HTTPException(status_code=401, detail="Sessao invalida ou expirada.")
    return _privacy_settings(tenant)


@router.patch("/privacy", response_model=PrivacySettingsResponse)
async def update_privacy_settings(
    payload: PrivacySettingsUpdate,
    request: Request,
    current_user: CurrentUser,
    _: User = Depends(require_roles("admin")),
    __: User = Depends(require_privileged_mfa),
    db: AsyncSession = Depends(get_db),
):
    tenant = await _locked_tenant(db, current_user.tenant_id)
    changes = payload.model_dump()
    for field, value in changes.items():
        setattr(tenant, field, str(value) if field == "privacy_contact" and value else value)
    await _audit(
        db,
        request,
        tenant_id=tenant.id,
        user_id=current_user.id,
        action="PRIVACY_SETTINGS_UPDATED",
        resource_type="tenant",
        resource_id=tenant.id,
        details={"fields": sorted(changes)},
    )
    await db.commit()
    return _privacy_settings(tenant)


@router.get("/privacy/requests", response_model=list[PrivacyRequestResponse])
async def list_privacy_requests(
    current_user: CurrentUser,
    _: User = Depends(require_privileged_mfa),
    db: AsyncSession = Depends(get_db),
):
    query = select(PrivacyRequest).where(PrivacyRequest.tenant_id == current_user.tenant_id)
    if current_user.role != "admin":
        query = query.where(PrivacyRequest.requested_by_user_id == current_user.id)
    rows = (await db.scalars(query.order_by(PrivacyRequest.created_at.desc()).limit(200))).all()
    return [_privacy_request(row) for row in rows]


@router.post("/privacy/requests", response_model=PrivacyRequestResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_privacy_request(
    payload: PrivacyRequestInput,
    request: Request,
    current_user: CurrentUser,
    _: User = Depends(require_privileged_mfa),
    db: AsyncSession = Depends(get_db),
):
    if payload.scope == "tenant" and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Somente administradores podem solicitar operacoes sobre todo o escritorio.")
    existing = await db.scalar(
        select(PrivacyRequest).where(
            PrivacyRequest.tenant_id == current_user.tenant_id,
            PrivacyRequest.requested_by_user_id == current_user.id,
            PrivacyRequest.request_type == payload.request_type,
            PrivacyRequest.scope == payload.scope,
            PrivacyRequest.status.in_(("received", "in_review")),
        )
    )
    if existing:
        return _privacy_request(existing)
    item = PrivacyRequest(
        tenant_id=current_user.tenant_id,
        requested_by_user_id=current_user.id,
        request_type=payload.request_type,
        scope=payload.scope,
        status="received",
        reason=payload.reason,
    )
    db.add(item)
    await db.flush()
    await _audit(
        db,
        request,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        action="PRIVACY_REQUEST_CREATED",
        resource_type="privacy_request",
        resource_id=item.id,
        details={"request_type": item.request_type, "scope": item.scope},
    )
    await db.commit()
    return _privacy_request(item)


@router.post("/onboarding", response_model=ProfileResponse)
async def complete_onboarding(
    payload: OnboardingUpdate,
    request: Request,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    await ensure_tenant_write_access(db, current_user.tenant_id)
    tenant = await _locked_tenant(db, current_user.tenant_id)
    if payload.office_name is not None:
        tenant.name = payload.office_name
    if "cnpj" in payload.model_fields_set:
        tenant.cnpj = payload.cnpj
    if "oab_number" in payload.model_fields_set:
        current_user.oab_number = payload.oab_number
    if "oab_uf" in payload.model_fields_set:
        current_user.oab_uf = payload.oab_uf
    await _audit(
        db,
        request,
        tenant_id=tenant.id,
        user_id=current_user.id,
        action="ACCOUNT_ONBOARDING_COMPLETED",
        resource_type="tenant",
        resource_id=tenant.id,
    )
    await db.commit()
    return ProfileResponse(**_profile(current_user, tenant))


async def _create_subscription_request(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    request_type: str,
    message: str | None,
) -> tuple[SubscriptionRequest, bool]:
    tenant = await _locked_tenant(db, tenant_id)
    existing = await db.scalar(
        select(SubscriptionRequest)
        .where(
            SubscriptionRequest.tenant_id == tenant.id,
            SubscriptionRequest.request_type == request_type,
            SubscriptionRequest.status.in_(("received", "in_progress")),
        )
        .with_for_update()
    )
    if existing:
        return existing, True
    subscription_request = SubscriptionRequest(
        tenant_id=tenant.id,
        requested_by_user_id=user_id,
        request_type=request_type,
        message=message,
    )
    db.add(subscription_request)
    await db.flush()
    return subscription_request, False


@router.post("/subscription/request", status_code=status.HTTP_202_ACCEPTED)
async def request_subscription(
    payload: SubscriptionRequestInput,
    request: Request,
    current_user: CurrentUser,
    _: User = Depends(require_roles("admin")),
    __: User = Depends(require_privileged_mfa),
    db: AsyncSession = Depends(get_db),
):
    subscription_request, existing = await _create_subscription_request(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        request_type="subscription",
        message=payload.message,
    )
    if not existing:
        await _audit(
            db,
            request,
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            action="SUBSCRIPTION_REQUESTED",
            resource_type="subscription_request",
            resource_id=subscription_request.id,
        )
        await db.commit()
    return {"status": "received"}


@router.post("/subscription/cancel", status_code=status.HTTP_202_ACCEPTED)
async def request_subscription_cancellation(
    payload: SubscriptionRequestInput,
    request: Request,
    current_user: CurrentUser,
    _: User = Depends(require_roles("admin")),
    __: User = Depends(require_privileged_mfa),
    db: AsyncSession = Depends(get_db),
):
    subscription_request, existing = await _create_subscription_request(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        request_type="cancellation",
        message=payload.message,
    )
    if not existing:
        await _audit(
            db,
            request,
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            action="SUBSCRIPTION_CANCELLATION_REQUESTED",
            resource_type="subscription_request",
            resource_id=subscription_request.id,
        )
        await db.commit()
    return {"status": "received"}


@router.post("/mfa/setup", response_model=MfaSetupResponse)
async def setup_mfa(
    request: Request,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    await _enforce_auth_rate_limit("mfa-setup", request, current_user.email, limit=5, window_seconds=600)
    _require_recent_password_session(request)
    current_user = await _locked_current_user(db, current_user)
    if current_user.mfa_enabled or current_user.mfa_secret_encrypted:
        raise HTTPException(status_code=409, detail="MFA ja esta habilitado.")
    secret = new_totp_secret()
    try:
        current_user.mfa_secret_encrypted = encrypt_mfa_secret(secret)
    except RuntimeError:
        raise HTTPException(status_code=503, detail="MFA temporariamente indisponivel.")
    await db.commit()
    issuer = quote("LegalTech", safe="")
    account_name = quote(current_user.email, safe="")
    return MfaSetupResponse(
        secret=secret,
        provisioning_uri=f"otpauth://totp/{issuer}:{account_name}?secret={secret}&issuer={issuer}&digits=6&period=30",
    )


@router.post("/mfa/confirm", response_model=MfaRecoveryCodesResponse)
async def confirm_mfa(
    payload: MfaCode,
    request: Request,
    response: Response,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    await _enforce_auth_rate_limit("mfa-confirm", request, current_user.email, limit=8, window_seconds=600)
    _require_recent_password_session(request)
    current_user = await _locked_current_user(db, current_user)
    if current_user.mfa_enabled or not current_user.mfa_secret_encrypted:
        raise HTTPException(status_code=400, detail="Configuracao MFA invalida.")
    try:
        counter = matching_totp_counter(
            decrypt_mfa_secret(current_user.mfa_secret_encrypted), payload.code
        )
    except RuntimeError:
        raise HTTPException(status_code=503, detail="MFA temporariamente indisponivel.")
    if counter is None:
        raise HTTPException(status_code=400, detail="Codigo MFA invalido.")
    now = _utcnow()
    current_user.mfa_enabled = True
    current_user.mfa_enrolled_at = now
    current_user.mfa_last_counter = counter
    recovery_codes = new_recovery_codes()
    for code in recovery_codes:
        db.add(
            AccountToken(
                user_id=current_user.id,
                tenant_id=current_user.tenant_id,
                token_type="mfa_recovery",
                token_hash=hash_account_token(code),
                expires_at=now + timedelta(days=365),
            )
        )
    auth_session = getattr(request.state, "auth_session", None)
    if auth_session:
        auth_session.mfa_verified_at = now
        from app.core.security import create_access_token

        _set_session_cookie(
            response,
            create_access_token(
                current_user.id,
                current_user.tenant_id,
                session_id=auth_session.id,
                mfa_verified=True,
            ),
        )
    await _audit(
        db,
        request,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        action="MFA_ENABLED",
        resource_type="user",
        resource_id=current_user.id,
    )
    await db.commit()
    return MfaRecoveryCodesResponse(recovery_codes=recovery_codes)


@router.post("/mfa/recovery-codes", response_model=MfaRecoveryCodesResponse)
async def regenerate_mfa_recovery_codes(
    payload: MfaCode,
    request: Request,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    await _enforce_auth_rate_limit("mfa-recovery", request, current_user.email, limit=5, window_seconds=600)
    current_user = await _locked_current_user(db, current_user)
    if not await _verify_current_mfa(db, current_user, payload.code):
        raise HTTPException(status_code=400, detail="Codigo MFA invalido.")
    now = _utcnow()
    tokens = (
        await db.execute(
            select(AccountToken)
            .where(
                AccountToken.user_id == current_user.id,
                AccountToken.tenant_id == current_user.tenant_id,
                AccountToken.token_type == "mfa_recovery",
                AccountToken.consumed_at.is_(None),
            )
            .with_for_update()
        )
    ).scalars()
    for token in tokens:
        token.consumed_at = now
    recovery_codes = new_recovery_codes()
    for code in recovery_codes:
        db.add(
            AccountToken(
                user_id=current_user.id,
                tenant_id=current_user.tenant_id,
                token_type="mfa_recovery",
                token_hash=hash_account_token(code),
                expires_at=now + timedelta(days=365),
            )
        )
    await _audit(
        db,
        request,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        action="MFA_RECOVERY_CODES_REGENERATED",
        resource_type="user",
        resource_id=current_user.id,
    )
    await db.commit()
    return MfaRecoveryCodesResponse(recovery_codes=recovery_codes)


@router.post("/mfa/disable", status_code=status.HTTP_204_NO_CONTENT)
async def disable_mfa(
    payload: MfaDisable,
    request: Request,
    response: Response,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    await _enforce_auth_rate_limit("mfa-disable", request, current_user.email, limit=5, window_seconds=600)
    current_user = await _locked_current_user(db, current_user)
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Senha atual invalida.")
    if not await _verify_current_mfa(db, current_user, payload.code):
        raise HTTPException(status_code=400, detail="Codigo MFA invalido.")
    current_user.mfa_enabled = False
    current_user.mfa_secret_encrypted = None
    current_user.mfa_enrolled_at = None
    current_user.mfa_last_counter = None
    await _revoke_user_sessions(db, current_user)
    await _audit(
        db,
        request,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        action="MFA_DISABLED",
        resource_type="user",
        resource_id=current_user.id,
    )
    await db.commit()
    clear_session_cookie(response)
