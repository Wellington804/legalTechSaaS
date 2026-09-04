"""Guided setup computed from existing records, plus deliberately submitted feedback."""
from datetime import datetime, timedelta, timezone
from math import ceil
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.account import _account_email_ready
from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import CurrentUser, ensure_tenant_write_access, require_privileged_mfa
from app.models.pilot import PilotFeedback
from app.models.tenant import Tenant
from app.models.user import User
from app.models.workspace import WorkspaceCase, WorkspaceClient, WorkspaceDocument, WorkspaceLedgerEntry, WorkspaceTask
from app.services.audit_service import AuditService
from app.services.workspace_service import authorized_case_query, document_scope, FINANCE_ROLES, require_role

router = APIRouter()
Step = Literal["profile", "client", "case", "task", "document", "finance"]
Area = Literal["dashboard", "account", "clients", "cases", "tasks", "documents", "finance", "communications", "other"]
STEPS = [
    ("profile", "Configure seu perfil profissional", "Informe nome, OAB e os dados do escritório.", "/dashboard/account"),
    ("client", "Cadastre o primeiro cliente", "Use somente os dados autorizados para este piloto controlado.", "/dashboard/crm"),
    ("case", "Abra um atendimento ou caso", "Vincule o cliente e defina o responsável.", "/dashboard/tracker"),
    ("task", "Registre a próxima ação", "Defina o que fazer a seguir; confira manualmente as datas.", "/dashboard/tasks"),
    ("document", "Anexe um documento", "Guarde um arquivo de teste no caso e confira o histórico.", "/dashboard/petitions/editor"),
    ("finance", "Registre honorários ou despesas", "Organize os valores sem presumir pagamento recebido.", "/dashboard/financeiro"),
]


class FeedbackInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    kind: Literal["problem", "weekly"]
    area: Area
    message: str = Field(min_length=1, max_length=3000)
    completed_steps: list[Step] = Field(default_factory=list, max_length=6)
    help_steps: list[Step] = Field(default_factory=list, max_length=6)
    consent: Literal[True]

    @field_validator("message")
    @classmethod
    def clean_message(cls, value):
        value = value.strip()
        if not value or "\x00" in value:
            raise ValueError("Descreva o problema sem dados de clientes.")
        return value

    @field_validator("consent", mode="before")
    @classmethod
    def explicit_consent(cls, value):
        if value is not True:
            raise ValueError("Confirme o envio do relato.")
        return value

    @field_validator("completed_steps", "help_steps")
    @classmethod
    def unique_steps(cls, value):
        return sorted(set(value))


def feedback_json(item):
    return {field: getattr(item, field) for field in ("id", "kind", "area", "message", "release", "completed_steps", "help_steps", "created_at")}


@router.get("/overview")
async def overview(user: CurrentUser, db: AsyncSession = Depends(get_db), _mfa=Depends(require_privileged_mfa)):
    tenant = await db.scalar(select(Tenant).where(Tenant.id == user.tenant_id))
    allowed_cases = authorized_case_query(user).with_only_columns(WorkspaceCase.id).where(WorkspaceCase.archived_at.is_(None))
    exists = lambda query: select(query.exists())
    done = {"profile": bool(user.full_name and user.oab_number and user.oab_uf and tenant.name)}
    done["client"] = bool(await db.scalar(exists(select(WorkspaceClient.id).where(WorkspaceClient.tenant_id == user.tenant_id, WorkspaceClient.archived_at.is_(None)))))
    done["case"] = bool(await db.scalar(exists(allowed_cases)))
    done["task"] = bool(await db.scalar(exists(select(WorkspaceTask.id).where(WorkspaceTask.tenant_id == user.tenant_id, WorkspaceTask.case_id.in_(allowed_cases)))))
    done["document"] = bool(await db.scalar(exists(document_scope(user).where(WorkspaceDocument.archived_at.is_(None), WorkspaceDocument.kind != "template", WorkspaceDocument.file_content.is_not(None)))))
    finance = user.role in FINANCE_ROLES
    done["finance"] = bool(await db.scalar(exists(select(WorkspaceLedgerEntry.id).where(WorkspaceLedgerEntry.tenant_id == user.tenant_id, WorkspaceLedgerEntry.entry_type.in_(("fee", "expense")), WorkspaceLedgerEntry.status != "reversed")))) if finance else False
    try:
        await ensure_tenant_write_access(db, tenant.id)
        write_allowed = True
    except HTTPException as exc:
        if exc.status_code != 402:
            raise
        write_allowed = False
    now = datetime.now(timezone.utc)
    end = tenant.trial_ends_at if tenant.subscription_status == "trial" else tenant.subscription_ends_at
    last_report = await db.scalar(select(func.max(PilotFeedback.created_at)).where(PilotFeedback.tenant_id == user.tenant_id, PilotFeedback.user_id == user.id, PilotFeedback.kind == "weekly"))
    return {
        "steps": [{"id": key, "title": title, "description": description, "href": href,
                   "status": "not_applicable" if key == "finance" and not finance else "done" if done[key] else "pending"}
                  for key, title, description, href in STEPS],
        "subscription": {"status": tenant.subscription_status, "ends_at": end,
                         "days_remaining": max(0, ceil((end - now).total_seconds() / 86400)) if end else None, "write_allowed": write_allowed},
        "security": {"email_verified": bool(user.email_verified_at), "mfa_enabled": user.mfa_enabled,
                     "environment": settings.ENVIRONMENT, "sentry_configured": bool(settings.SENTRY_DSN),
                     "account_email_configured": _account_email_ready(),
                     "https_configured": settings.FRONTEND_URL.startswith("https://") and settings.COOKIE_SECURE},
        "support_url": settings.SUPPORT_URL, "release": (settings.RELEASE or "local")[:100],
        "weekly": {"last_report_at": last_report, "next_review_at": (last_report or user.created_at or now) + timedelta(days=7)},
        "data_policy": "controlled_real_pilot",
    }


@router.get("/feedback")
async def list_feedback(user: CurrentUser, db: AsyncSession = Depends(get_db)):
    items = (await db.scalars(select(PilotFeedback).where(PilotFeedback.tenant_id == user.tenant_id,
        PilotFeedback.user_id == user.id).order_by(PilotFeedback.created_at.desc()).limit(20))).all()
    return {"items": [feedback_json(item) for item in items]}


@router.get("/feedback/team")
async def list_team_feedback(user: CurrentUser, db: AsyncSession = Depends(get_db)):
    require_role(user, {"admin", "partner"})
    rows = (await db.execute(
        select(PilotFeedback, User.full_name)
        .join(User, (User.tenant_id == PilotFeedback.tenant_id) & (User.id == PilotFeedback.user_id))
        .where(PilotFeedback.tenant_id == user.tenant_id)
        .order_by(PilotFeedback.created_at.desc())
        .limit(100)
    )).all()
    items = [feedback_json(item) | {"user_id": item.user_id, "user_name": name} for item, name in rows]
    return {"items": items, "summary": {
        "total": len(items),
        "problems": sum(item["kind"] == "problem" for item in items),
        "weekly_reviews": sum(item["kind"] == "weekly" for item in items),
        "last_report_at": items[0]["created_at"] if items else None,
    }}


@router.post("/feedback", status_code=201)
async def create_feedback(body: FeedbackInput, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    # Feedback remains available when a trial expires; it never extends the subscription.
    await db.scalar(select(User).where(User.tenant_id == user.tenant_id, User.id == user.id).with_for_update())
    existing = await db.scalar(select(PilotFeedback).where(PilotFeedback.tenant_id == user.tenant_id,
        PilotFeedback.user_id == user.id, PilotFeedback.request_id == str(body.request_id)))
    values = body.model_dump(exclude={"request_id", "consent"})
    if existing:
        if any(getattr(existing, key) != value for key, value in values.items()):
            raise HTTPException(409, "Identificador utilizado para outro relato.")
        return feedback_json(existing)
    count = await db.scalar(select(func.count()).select_from(PilotFeedback).where(PilotFeedback.tenant_id == user.tenant_id,
        PilotFeedback.user_id == user.id, PilotFeedback.created_at > datetime.now(timezone.utc) - timedelta(days=1)))
    if count >= 10:
        raise HTTPException(429, "Limite de 10 relatos por dia atingido. Utilize o contato de suporte.")
    item = PilotFeedback(tenant_id=user.tenant_id, user_id=user.id, request_id=str(body.request_id),
                         release=(settings.RELEASE or "local")[:100], **values)
    db.add(item)
    await db.flush()
    await AuditService.log_action(db, user.tenant_id, user.id, "PILOT_FEEDBACK_SUBMITTED", "pilot_feedback", item.id,
                                 {"kind": item.kind, "area": item.area})
    await db.commit()
    return feedback_json(item)
