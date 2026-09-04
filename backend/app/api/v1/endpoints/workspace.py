import asyncio
import base64
import hashlib
import json
import difflib
import unicodedata
import uuid
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from pathlib import PurePath
from urllib.parse import quote
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import RedirectResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import and_, case as sql_case, func, literal, literal_column, or_, select, union_all
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, get_current_user, require_tenant_write
from app.models.account import PrivacyRequest
from app.models.controladoria import ControladoriaJudicialEvent
from app.models.engagement import CaseMessage, CommunicationInboxItem
from app.models.notification import NotificationDelivery
from app.models.tenant import Tenant
from app.models.user import User
from app.services.push_service import enqueue_user_push
from app.models.workspace import (
    WorkspaceCase,
    WorkspaceCaseAccess,
    WorkspaceCaseParty,
    WorkspaceClient,
    WorkspaceDocument,
    WorkspaceDocumentFolder,
    WorkspaceDocumentReview,
    WorkspaceDocumentUpload,
    WorkspaceDocumentVersion,
    WorkspaceLedgerEntry,
    WorkspaceLibraryEntry,
    WorkspacePublication,
    WorkspaceTask,
)
from app.schemas.workspace import (
    CaseAccessCreate,
    CaseAccessResponse,
    CaseCreate,
    CasePartyCreate,
    CasePartyResponse,
    CaseResponse,
    CaseUpdate,
    ClientImport,
    ClientCreate,
    ClientResponse,
    ClientUpdate,
    DocumentCreate,
    DocumentFolderCreate,
    DocumentFolderResponse,
    DocumentFolderUpdate,
    DocumentMove,
    DocumentResponse,
    DocumentUploadCreate,
    DocumentUploadResponse,
    DocumentUpdate,
    DocumentVersionResponse,
    LedgerEntryCreate,
    LedgerEntryResponse,
    LedgerEntryUpdate,
    LedgerReverse,
    LibraryEntryCreate,
    LibraryEntryResponse,
    LibraryEntryUpdate,
    ListResponse,
    ManualPaymentCreate,
    PublicationCreate,
    PublicationResponse,
    PublicationUpdate,
    REPRESENTATIVE_FIELDS,
    TaskCreate,
    TaskResponse,
    TaskUpdate,
    WorkspaceMemberResponse,
)
from app.services.audit_service import AuditService
from app.services.client_import import parse_client_file
from app.services.document_text import TextExtractionError, extract_upload_text
from app.services.document_storage import create_download_url, create_upload_url, enabled as r2_enabled, quarantine_key
from app.services.document_tasks import process_upload
from app.services.workspace_service import (
    ADMIN_ROLES,
    CASE_MANAGER_ROLES,
    FINANCE_ROLES,
    authorized_case_query,
    bounded_limit,
    case_access_clause,
    document_scope,
    document_version_bytes,
    ensure_document_storage_capacity,
    get_case,
    get_client,
    get_document,
    get_task,
    active_tenant_user,
    read_validated_upload,
    ALLOWED_UPLOAD_TYPES,
    MAX_UPLOAD_BYTES,
    lock_workspace_tenant,
    require_case_write,
    require_document_write,
    require_finance_role,
    require_role,
    reset_document_review,
    require_task_write,
)


router = APIRouter(dependencies=[Depends(get_current_user)])


def list_payload(items, limit: int) -> dict:
    return {"items": items, "limit": limit}


def conflict(message: str = "Registro foi alterado por outra sessao.") -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message)


def task_values_match(task: WorkspaceTask, values: dict) -> bool:
    return all(getattr(task, field) == value for field, value in values.items())


async def audit_mutation(
    db: AsyncSession,
    request: Request,
    user: User,
    action: str,
    resource_type: str,
    resource_id: str,
    details: dict | None = None,
) -> None:
    await AuditService.log_action(
        db=db,
        tenant_id=user.tenant_id,
        user_id=user.id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details or {},
        ip_address=request.client.host if request.client else None,
        user_agent=(request.headers.get("user-agent") or "")[:512] or None,
    )


async def commit_mutation(
    db: AsyncSession,
    request: Request,
    user: User,
    action: str,
    resource_type: str,
    resource_id: str,
    details: dict | None = None,
) -> None:
    await audit_mutation(db, request, user, action, resource_type, resource_id, details)
    await db.commit()


async def ensure_case_reference(db: AsyncSession, user: User, case_id: str | None) -> None:
    if case_id:
        await get_case(db, user, case_id)


async def ensure_client_reference(db: AsyncSession, user: User, client_id: str | None) -> None:
    if client_id:
        await get_client(db, user, client_id)


async def authorized_task_statement(user: User):
    return (
        select(WorkspaceTask)
        .outerjoin(
            WorkspaceCase,
            and_(
                WorkspaceCase.id == WorkspaceTask.case_id,
                WorkspaceCase.tenant_id == WorkspaceTask.tenant_id,
            ),
        )
        .where(
            WorkspaceTask.tenant_id == user.tenant_id,
            or_(WorkspaceTask.case_id.is_(None), case_access_clause(user)),
        )
    )


@router.get("/clients", response_model=ListResponse)
async def list_clients(
    limit: int = Query(default=50, ge=1, le=200),
    *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    limit = bounded_limit(limit)
    records = (
        await db.execute(
            select(WorkspaceClient)
            .where(WorkspaceClient.tenant_id == current_user.tenant_id)
            .order_by(WorkspaceClient.updated_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return list_payload([ClientResponse.model_validate(record) for record in records], limit)


@router.post("/clients", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
async def create_client(
    payload: ClientCreate,
    request: Request,
    *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    require_role(current_user, CASE_MANAGER_ROLES)
    client = WorkspaceClient(tenant_id=current_user.tenant_id, **payload.model_dump())
    db.add(client)
    await db.flush()
    await commit_mutation(db, request, current_user, "WORKSPACE_CLIENT_CREATED", "workspace_clients", client.id)
    return ClientResponse.model_validate(client)


@router.put("/clients/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: str,
    payload: ClientUpdate,
    request: Request,
    *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    require_role(current_user, CASE_MANAGER_ROLES)
    client = await get_client(db, current_user, client_id)
    if client.revision != payload.expected_revision:
        raise conflict()
    changes = payload.model_dump(exclude_unset=True, exclude={"expected_revision"})
    if not changes:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Nenhuma alteracao informada.")
    if changes.get("has_legal_representative") is False:
        changes.update({field: None for field in REPRESENTATIVE_FIELDS})
    for field, value in changes.items():
        if field in {"name", "stage"} and value is None:
            continue
        setattr(client, field, value)
    client.revision += 1
    await commit_mutation(
        db, request, current_user, "WORKSPACE_CLIENT_UPDATED", "workspace_clients", client.id, {"fields": sorted(changes)}
    )
    return ClientResponse.model_validate(client)


@router.get("/clients/{client_id}", response_model=ClientResponse)
async def get_client_detail(
    client_id: str,
    *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    return ClientResponse.model_validate(await get_client(db, current_user, client_id))


@router.post("/clients/import")
async def import_clients(
    payload: ClientImport,
    request: Request,
    *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    require_role(current_user, CASE_MANAGER_ROLES)
    await lock_workspace_tenant(db, current_user.tenant_id)
    emails = {item.email.casefold() for item in payload.items if item.email}
    tax_ids = {item.tax_id for item in payload.items if item.tax_id}
    conditions = []
    if emails:
        conditions.append(func.lower(WorkspaceClient.email).in_(emails))
    if tax_ids:
        conditions.append(WorkspaceClient.tax_id.in_(tax_ids))
    existing_records = []
    if conditions:
        existing_records = (
            await db.execute(
                select(WorkspaceClient).where(
                    WorkspaceClient.tenant_id == current_user.tenant_id,
                    or_(*conditions),
                )
            )
        ).scalars().all()
    known_emails = {record.email.casefold() for record in existing_records if record.email}
    known_tax_ids = {record.tax_id for record in existing_records if record.tax_id}
    created = []
    skipped = []
    for index, item in enumerate(payload.items):
        if item.email and item.email.casefold() in known_emails:
            skipped.append({"index": index, "reason": "email_duplicado"})
            continue
        if item.tax_id and item.tax_id in known_tax_ids:
            skipped.append({"index": index, "reason": "tax_id_duplicado"})
            continue
        client = WorkspaceClient(tenant_id=current_user.tenant_id, **item.model_dump())
        db.add(client)
        created.append(client)
        if client.email:
            known_emails.add(client.email.casefold())
        if client.tax_id:
            known_tax_ids.add(client.tax_id)
    await db.flush()
    await commit_mutation(
        db,
        request,
        current_user,
        "WORKSPACE_CLIENTS_IMPORTED",
        "workspace_clients",
        current_user.tenant_id,
        {"created": len(created), "skipped": len(skipped)},
    )
    return {"created": [ClientResponse.model_validate(record) for record in created], "skipped": skipped}


@router.post("/clients/import-preview")
async def preview_client_import(
    file: UploadFile = File(...), *, current_user: CurrentUser,
):
    require_role(current_user, CASE_MANAGER_ROLES)
    content = await file.read(2 * 1024 * 1024 + 1)
    return parse_client_file(file.filename or "", content)


@router.post("/clients/import-file")
async def import_clients_file(
    request: Request,
    file: UploadFile = File(...),
    mapping: str = Form(...),
    default_stage: str = Form("lead"),
    *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    require_role(current_user, CASE_MANAGER_ROLES)
    content = await file.read(2 * 1024 * 1024 + 1)
    parsed = parse_client_file(file.filename or "", content)
    try:
        selected = json.loads(mapping)
        if not isinstance(selected, dict):
            raise ValueError
        selected = {key: value for key, value in selected.items() if value}
        if set(selected) - {"name", "email", "phone", "tax_id", "stage"}:
            raise ValueError
        if selected.get("name") not in parsed["columns"] or any(value not in parsed["columns"] for value in selected.values()):
            raise ValueError
        if default_stage not in {"lead", "prospect", "client"}:
            raise ValueError
    except (json.JSONDecodeError, TypeError, ValueError):
        raise HTTPException(422, "O mapeamento das colunas é inválido. Revise a prévia e tente novamente.") from None
    stages = {
        "lead": "lead", "novo": "lead", "novocontato": "lead", "contato": "lead",
        "prospect": "prospect", "ematendimento": "prospect", "oportunidade": "prospect",
        "client": "client", "cliente": "client", "ativo": "client",
    }
    items, errors = [], []
    for number, row in enumerate(parsed["rows"], 2):
        stage_raw = str(row.get(selected.get("stage", ""), "")).strip().lower().replace(" ", "")
        stage = stages.get(stage_raw, default_stage if not stage_raw else "")
        raw = {field: (row.get(column) or None) for field, column in selected.items() if field != "stage"}
        raw["stage"] = stage
        try:
            items.append(ClientCreate.model_validate(raw))
        except ValidationError as exc:
            errors.append({"row": number, "fields": sorted({str(error["loc"][0]) for error in exc.errors()})})
    if errors:
        summary = "; ".join(f"linha {item['row']}: {', '.join(item['fields'])}" for item in errors[:20])
        raise HTTPException(422, f"Corrija os campos indicados; nenhum cliente foi importado. {summary}")
    return await import_clients(ClientImport(items=items), request, current_user=current_user, db=db, _write=_write)


@router.get("/members", response_model=ListResponse)
async def list_workspace_members(
    limit: int = Query(default=50, ge=1, le=200),
    *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    limit = bounded_limit(limit)
    members = (
        await db.execute(
            select(User)
            .where(User.tenant_id == current_user.tenant_id, User.is_active.is_(True))
            .order_by(User.full_name.asc())
            .limit(limit)
        )
    ).scalars().all()
    return list_payload([WorkspaceMemberResponse.model_validate(member) for member in members], limit)


@router.get("/cases", response_model=ListResponse)
async def list_cases(
    client_id: str | None = Query(default=None, max_length=64),
    limit: int = Query(default=50, ge=1, le=200),
    *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    limit = bounded_limit(limit)
    statement = authorized_case_query(current_user)
    if client_id:
        await get_client(db, current_user, client_id)
        statement = statement.where(WorkspaceCase.client_id == client_id)
    records = (await db.execute(statement.order_by(WorkspaceCase.updated_at.desc()).limit(limit))).scalars().all()
    return list_payload([CaseResponse.model_validate(record) for record in records], limit)


@router.post("/cases", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
async def create_case(
    payload: CaseCreate,
    request: Request,
    *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    require_role(current_user, CASE_MANAGER_ROLES)
    await get_client(db, current_user, payload.client_id)
    responsible_user = await active_tenant_user(db, current_user.tenant_id, payload.responsible_user_id)
    if responsible_user.role not in CASE_MANAGER_ROLES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Responsavel deve ser advogado, socio ou administrador.")
    case = WorkspaceCase(tenant_id=current_user.tenant_id, **payload.model_dump())
    db.add(case)
    await db.flush()
    await commit_mutation(db, request, current_user, "WORKSPACE_CASE_CREATED", "workspace_cases", case.id)
    return CaseResponse.model_validate(case)


@router.get("/cases/{case_id}")
async def get_case_detail(
    case_id: str,
    *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    case = await get_case(db, current_user, case_id)
    client = await get_client(db, current_user, case.client_id)
    tasks_statement = await authorized_task_statement(current_user)
    tasks = (
        await db.execute(tasks_statement.where(WorkspaceTask.case_id == case.id).order_by(WorkspaceTask.due_at.asc().nullslast()).limit(200))
    ).scalars().all()
    documents = (
        await db.execute(document_scope(current_user).where(WorkspaceDocument.case_id == case.id).order_by(WorkspaceDocument.updated_at.desc()).limit(200))
    ).scalars().all()
    parties = (
        await db.execute(
            select(WorkspaceCaseParty)
            .where(WorkspaceCaseParty.tenant_id == current_user.tenant_id, WorkspaceCaseParty.case_id == case.id)
            .order_by(WorkspaceCaseParty.updated_at.desc())
            .limit(200)
        )
    ).scalars().all()
    return {
        "case": CaseResponse.model_validate(case),
        "client": ClientResponse.model_validate(client),
        "parties": [CasePartyResponse.model_validate(record) for record in parties],
        "tasks": [TaskResponse.model_validate(record) for record in tasks],
        "documents": [DocumentResponse.model_validate(record) for record in documents],
    }


@router.put("/cases/{case_id}", response_model=CaseResponse)
async def update_case(
    case_id: str,
    payload: CaseUpdate,
    request: Request,
    *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    case = await get_case(db, current_user, case_id, for_update=True)
    require_case_write(current_user, case)
    if case.revision != payload.expected_revision:
        raise conflict()
    changes = payload.model_dump(exclude_unset=True, exclude={"expected_revision"})
    if not changes:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Nenhuma alteracao informada.")
    if "responsible_user_id" in changes and changes["responsible_user_id"] is not None:
        responsible_user = await active_tenant_user(db, current_user.tenant_id, changes["responsible_user_id"])
        if responsible_user.role not in CASE_MANAGER_ROLES:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Responsavel deve ser advogado, socio ou administrador.")
    for field, value in changes.items():
        if field in {"title", "status", "responsible_user_id"} and value is None:
            continue
        setattr(case, field, value)
    if case.status == "archived" and case.archived_at is None:
        case.archived_at = datetime.now(timezone.utc)
    elif case.status != "archived":
        case.archived_at = None
    case.revision += 1
    await commit_mutation(
        db, request, current_user, "WORKSPACE_CASE_UPDATED", "workspace_cases", case.id, {"fields": sorted(changes)}
    )
    return CaseResponse.model_validate(case)


@router.get("/cases/{case_id}/parties", response_model=ListResponse)
async def list_case_parties(
    case_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    await get_case(db, current_user, case_id)
    limit = bounded_limit(limit)
    records = (
        await db.execute(
            select(WorkspaceCaseParty)
            .where(WorkspaceCaseParty.tenant_id == current_user.tenant_id, WorkspaceCaseParty.case_id == case_id)
            .order_by(WorkspaceCaseParty.updated_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return list_payload([CasePartyResponse.model_validate(record) for record in records], limit)


@router.post("/cases/{case_id}/parties", response_model=CasePartyResponse, status_code=status.HTTP_201_CREATED)
async def create_case_party(
    case_id: str,
    payload: CasePartyCreate,
    request: Request,
    *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    await get_case(db, current_user, case_id)
    require_role(current_user, ADMIN_ROLES)
    party = WorkspaceCaseParty(tenant_id=current_user.tenant_id, case_id=case_id, **payload.model_dump())
    db.add(party)
    await db.flush()
    await commit_mutation(db, request, current_user, "WORKSPACE_CASE_PARTY_CREATED", "workspace_case_parties", party.id)
    return CasePartyResponse.model_validate(party)


@router.get("/cases/{case_id}/access", response_model=ListResponse)
async def list_case_access(
    case_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    await get_case(db, current_user, case_id)
    require_role(current_user, ADMIN_ROLES)
    limit = bounded_limit(limit)
    records = (
        await db.execute(
            select(WorkspaceCaseAccess)
            .where(WorkspaceCaseAccess.tenant_id == current_user.tenant_id, WorkspaceCaseAccess.case_id == case_id)
            .order_by(WorkspaceCaseAccess.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return list_payload([CaseAccessResponse.model_validate(record) for record in records], limit)


@router.post("/cases/{case_id}/access", response_model=CaseAccessResponse, status_code=status.HTTP_201_CREATED)
async def grant_case_access(
    case_id: str,
    payload: CaseAccessCreate,
    request: Request,
    *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    await get_case(db, current_user, case_id)
    require_role(current_user, ADMIN_ROLES)
    await active_tenant_user(db, current_user.tenant_id, payload.user_id)
    existing = await db.scalar(
        select(WorkspaceCaseAccess).where(
            WorkspaceCaseAccess.tenant_id == current_user.tenant_id,
            WorkspaceCaseAccess.case_id == case_id,
            WorkspaceCaseAccess.user_id == payload.user_id,
        )
    )
    if existing:
        return CaseAccessResponse.model_validate(existing)
    access = WorkspaceCaseAccess(tenant_id=current_user.tenant_id, case_id=case_id, user_id=payload.user_id)
    db.add(access)
    await db.flush()
    await commit_mutation(db, request, current_user, "WORKSPACE_CASE_ACCESS_GRANTED", "workspace_case_access", access.id)
    return CaseAccessResponse.model_validate(access)


@router.delete("/cases/{case_id}/access/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_case_access(
    case_id: str,
    user_id: str,
    request: Request,
    *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    await get_case(db, current_user, case_id)
    require_role(current_user, ADMIN_ROLES)
    access = await db.scalar(
        select(WorkspaceCaseAccess)
        .where(
            WorkspaceCaseAccess.tenant_id == current_user.tenant_id,
            WorkspaceCaseAccess.case_id == case_id,
            WorkspaceCaseAccess.user_id == user_id,
        )
        .with_for_update()
    )
    if not access:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Permissao de caso nao encontrada.")
    access_id = access.id
    await db.delete(access)
    await commit_mutation(
        db,
        request,
        current_user,
        "WORKSPACE_CASE_ACCESS_REVOKED",
        "workspace_case_access",
        access_id,
        {"case_id": case_id, "user_id": user_id},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/tasks", response_model=ListResponse)
async def list_tasks(
    case_id: str | None = Query(default=None, max_length=64),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    assigned_user_id: str | None = Query(default=None, max_length=64),
    kind: str | None = Query(default=None, max_length=16),
    open_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    limit = bounded_limit(limit)
    statement = await authorized_task_statement(current_user)
    if case_id:
        await get_case(db, current_user, case_id)
        statement = statement.where(WorkspaceTask.case_id == case_id)
    if date_from:
        if date_from.tzinfo is None:
            raise HTTPException(422, "data inicial deve incluir fuso horario")
        statement = statement.where(WorkspaceTask.due_at >= date_from.astimezone(timezone.utc))
    if date_to:
        if date_to.tzinfo is None:
            raise HTTPException(422, "data final deve incluir fuso horario")
        statement = statement.where(WorkspaceTask.due_at < date_to.astimezone(timezone.utc))
    if date_from and date_to and date_from >= date_to:
        raise HTTPException(422, "intervalo de datas invalido")
    if assigned_user_id:
        await active_tenant_user(db, current_user.tenant_id, assigned_user_id)
        statement = statement.where(WorkspaceTask.assigned_user_id == assigned_user_id)
    if kind:
        if kind not in {"task", "deadline", "hearing"}:
            raise HTTPException(422, "tipo de compromisso invalido")
        statement = statement.where(WorkspaceTask.kind == kind)
    if open_only:
        statement = statement.where(WorkspaceTask.status.in_(("pending", "in_progress")))
    records = (await db.execute(statement.order_by(WorkspaceTask.due_at.asc().nullslast(), WorkspaceTask.updated_at.desc()).limit(limit))).scalars().all()
    return list_payload([TaskResponse.model_validate(record) for record in records], limit)


@router.post("/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    payload: TaskCreate,
    request: Request,
    *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    await ensure_case_reference(db, current_user, payload.case_id)
    if payload.case_id:
        case = await get_case(db, current_user, payload.case_id)
        if current_user.role == "paralegal":
            require_task_write(current_user)
        else:
            require_case_write(current_user, case)
    else:
        require_task_write(current_user)
    if payload.assigned_user_id:
        await active_tenant_user(db, current_user.tenant_id, payload.assigned_user_id)
    values = payload.model_dump(exclude={"request_id"})
    request_id = str(payload.request_id) if payload.request_id else None
    if request_id:
        existing = await db.scalar(
            select(WorkspaceTask).where(
                WorkspaceTask.tenant_id == current_user.tenant_id,
                WorkspaceTask.request_id == request_id,
            )
        )
        if existing:
            if task_values_match(existing, values):
                return TaskResponse.model_validate(existing)
            raise conflict("Chave de repeticao ja usada para outra tarefa.")
    task = WorkspaceTask(tenant_id=current_user.tenant_id, request_id=request_id, **values)
    try:
        async with db.begin_nested():
            db.add(task)
            await db.flush()
    except IntegrityError:
        if request_id:
            existing = await db.scalar(
                select(WorkspaceTask).where(
                    WorkspaceTask.tenant_id == current_user.tenant_id,
                    WorkspaceTask.request_id == request_id,
                )
            )
            if existing:
                if task_values_match(existing, values):
                    return TaskResponse.model_validate(existing)
                raise conflict("Chave de repeticao ja usada para outra tarefa.")
        raise
    if task.assigned_user_id:
        await enqueue_user_push(db, tenant_id=task.tenant_id, user_id=task.assigned_user_id,
                                event_key=f"task:{task.id}:assignment:{task.revision}",
                                kind="task_assigned", case_id=task.case_id, task_id=task.id)
    await commit_mutation(db, request, current_user, "WORKSPACE_TASK_CREATED", "workspace_tasks", task.id)
    return TaskResponse.model_validate(task)


@router.put("/tasks/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str,
    payload: TaskUpdate,
    request: Request,
    *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    task = await get_task(db, current_user, task_id, for_update=True)
    require_task_write(current_user, task)
    changes = payload.model_dump(exclude_unset=True, exclude={"expected_revision"})
    if not changes:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Nenhuma alteracao informada.")
    if task.revision != payload.expected_revision:
        if task_values_match(task, changes):
            return TaskResponse.model_validate(task)
        raise conflict()
    if "assigned_user_id" in changes and changes["assigned_user_id"]:
        await active_tenant_user(db, current_user.tenant_id, changes["assigned_user_id"])
    previous_assignee = task.assigned_user_id
    reminder_changed = any(field in changes and changes[field] != getattr(task, field)
                           for field in ("due_at", "status", "assigned_user_id", "manually_reviewed")
                           if changes.get(field) is not None or field in {"due_at", "assigned_user_id"})
    if "due_at" in changes and changes["due_at"] != task.due_at and changes.get("manually_reviewed") is not True:
        changes["manually_reviewed"] = False
    for field, value in changes.items():
        if field in {"title", "status", "manually_reviewed"} and value is None:
            continue
        setattr(task, field, value)
    task.revision += 1
    if reminder_changed:
        from app.services.routine_service import cancel_reminders
        await cancel_reminders(db, current_user.tenant_id, task.id)
    if task.assigned_user_id and task.assigned_user_id != previous_assignee:
        await db.flush()
        await enqueue_user_push(db, tenant_id=task.tenant_id, user_id=task.assigned_user_id,
                                event_key=f"task:{task.id}:assignment:{task.revision}",
                                kind="task_assigned", case_id=task.case_id, task_id=task.id)
    await commit_mutation(
        db, request, current_user, "WORKSPACE_TASK_UPDATED", "workspace_tasks", task.id, {"fields": sorted(changes)}
    )
    return TaskResponse.model_validate(task)


async def create_document_record(
    payload: DocumentCreate,
    request: Request,
    current_user: User,
    db: AsyncSession,
    *, commit: bool = True,
) -> WorkspaceDocument:
    if payload.kind == "template" and (payload.case_id or payload.client_id):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Modelo nao pode ser vinculado a caso ou cliente.")
    await ensure_case_reference(db, current_user, payload.case_id)
    await ensure_client_reference(db, current_user, payload.client_id)
    if payload.case_id:
        case = await get_case(db, current_user, payload.case_id)
        if payload.client_id and payload.client_id != case.client_id:
            raise HTTPException(status_code=422, detail="O processo nao pertence ao cliente informado.")
        if not payload.client_id:
            payload = payload.model_copy(update={"client_id": case.client_id})
        if current_user.role != "paralegal":
            require_case_write(current_user, case)
    elif payload.kind == "template":
        require_role(current_user, CASE_MANAGER_ROLES)
    if payload.folder_id:
        folder = await get_document_folder(db, current_user, payload.folder_id)
        if folder.client_id != payload.client_id or folder.case_id != payload.case_id:
            raise HTTPException(status_code=422, detail="A pasta deve pertencer ao mesmo cliente e processo.")
    await ensure_document_storage_capacity(
        db,
        current_user.tenant_id,
        document_version_bytes(payload.content_text),
    )
    document = WorkspaceDocument(tenant_id=current_user.tenant_id, **payload.model_dump())
    db.add(document)
    await db.flush()
    db.add(
        WorkspaceDocumentVersion(
            tenant_id=current_user.tenant_id,
            document_id=document.id,
            version=1,
            content_text=document.content_text,
            content_format=document.content_format,
            created_by_user_id=current_user.id,
        )
    )
    await db.flush()
    await audit_mutation(db, request, current_user, "WORKSPACE_DOCUMENT_CREATED", "workspace_documents", document.id)
    if commit:
        await db.commit()
    return document


async def update_document_record(
    document: WorkspaceDocument,
    payload: DocumentUpdate,
    request: Request,
    current_user: User,
    db: AsyncSession,
) -> WorkspaceDocument:
    require_document_write(current_user, document)
    if payload.expected_version is not None and document.current_version != payload.expected_version:
        raise conflict("Versao do documento desatualizada.")
    if payload.expected_revision is not None and document.revision != payload.expected_revision:
        raise conflict()
    changes = payload.model_dump(exclude_unset=True, exclude={"expected_version", "expected_revision"})
    if not changes:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Nenhuma alteracao informada.")
    if set(changes) == {"title"}:
        document.title = changes["title"]
        document.revision += 1
        await commit_mutation(db, request, current_user, "WORKSPACE_DOCUMENT_UPDATED", "workspace_documents", document.id, {"fields": ["title"]})
        return document
    current_file_version = await db.scalar(select(WorkspaceDocumentVersion).where(
        WorkspaceDocumentVersion.tenant_id == current_user.tenant_id,
        WorkspaceDocumentVersion.document_id == document.id,
        WorkspaceDocumentVersion.version == document.current_version,
    ))
    if current_file_version and current_file_version.object_key:
        raise HTTPException(status_code=422, detail="Edite o titulo ou envie uma nova versao do arquivo; o conteudo extraido nao pode substituir o original.")
    next_content_text = changes["content_text"] if "content_text" in changes else document.content_text
    await ensure_document_storage_capacity(
        db,
        current_user.tenant_id,
        document_version_bytes(next_content_text, document.file_content),
    )
    if "title" in changes and changes["title"] is not None:
        document.title = changes["title"]
    if "content_text" in changes:
        document.content_text = changes["content_text"]
    if changes.get("content_format"):
        document.content_format = changes["content_format"]
    document.current_version += 1
    document.revision += 1
    reset_document_review(document)
    db.add(
        WorkspaceDocumentVersion(
            tenant_id=current_user.tenant_id,
            document_id=document.id,
            version=document.current_version,
            content_text=document.content_text,
            content_format=document.content_format,
            filename=document.filename,
            content_type=document.content_type,
            file_content=document.file_content,
            file_size=document.file_size,
            sha256_hash=document.sha256_hash,
            created_by_user_id=current_user.id,
        )
    )
    await commit_mutation(
        db, request, current_user, "WORKSPACE_DOCUMENT_VERSION_CREATED", "workspace_documents", document.id, {"version": document.current_version}
    )
    return document


def normalized_folder_name(value: str) -> str:
    return unicodedata.normalize("NFKC", " ".join(value.split())).casefold()


async def get_document_folder(db: AsyncSession, user: User, folder_id: str, *, lock: bool = False) -> WorkspaceDocumentFolder:
    statement = select(WorkspaceDocumentFolder).where(
        WorkspaceDocumentFolder.id == folder_id,
        WorkspaceDocumentFolder.tenant_id == user.tenant_id,
        WorkspaceDocumentFolder.archived_at.is_(None),
    )
    folder = await db.scalar(statement.with_for_update() if lock else statement)
    if not folder:
        raise HTTPException(status_code=404, detail="Pasta nao encontrada.")
    if folder.case_id:
        await get_case(db, user, folder.case_id)
    return folder


async def validate_folder_scope(db: AsyncSession, user: User, client_id: str, case_id: str | None, parent_id: str | None = None) -> WorkspaceDocumentFolder | None:
    await get_client(db, user, client_id)
    if case_id:
        case = await get_case(db, user, case_id)
        if case.client_id != client_id:
            raise HTTPException(status_code=422, detail="O processo nao pertence ao cliente informado.")
    parent = await get_document_folder(db, user, parent_id) if parent_id else None
    if parent and (parent.client_id != client_id or parent.case_id != case_id):
        raise HTTPException(status_code=422, detail="A pasta-pai deve estar no mesmo cliente e processo.")
    depth = 0
    cursor = parent
    while cursor:
        depth += 1
        if depth >= 8:
            raise HTTPException(status_code=422, detail="A estrutura aceita no maximo 8 niveis de pastas.")
        cursor = await db.scalar(select(WorkspaceDocumentFolder).where(
            WorkspaceDocumentFolder.tenant_id == user.tenant_id,
            WorkspaceDocumentFolder.id == cursor.parent_id,
        )) if cursor.parent_id else None
    return parent


@router.get("/document-folders")
async def list_document_folders(
    client_id: str = Query(max_length=64),
    case_id: str | None = Query(default=None, max_length=64),
    *, current_user: CurrentUser, db: AsyncSession = Depends(get_db),
):
    await validate_folder_scope(db, current_user, client_id, case_id)
    records = (await db.scalars(select(WorkspaceDocumentFolder).where(
        WorkspaceDocumentFolder.tenant_id == current_user.tenant_id,
        WorkspaceDocumentFolder.client_id == client_id,
        WorkspaceDocumentFolder.case_id == case_id if case_id else WorkspaceDocumentFolder.case_id.is_(None),
        WorkspaceDocumentFolder.archived_at.is_(None),
    ).order_by(WorkspaceDocumentFolder.name).limit(500))).all()
    return {"items": [DocumentFolderResponse.model_validate(record) for record in records]}


@router.post("/document-folders", response_model=DocumentFolderResponse, status_code=201)
async def create_document_folder(
    payload: DocumentFolderCreate, request: Request, *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db), _write: User = Depends(require_tenant_write),
):
    require_role(current_user, CASE_MANAGER_ROLES | {"paralegal"})
    await validate_folder_scope(db, current_user, payload.client_id, payload.case_id, payload.parent_id)
    folder = WorkspaceDocumentFolder(
        tenant_id=current_user.tenant_id, **payload.model_dump(),
        normalized_name=normalized_folder_name(payload.name),
    )
    db.add(folder)
    try:
        await db.flush()
        await commit_mutation(db, request, current_user, "DOCUMENT_FOLDER_CREATED", "workspace_document_folders", folder.id)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Ja existe uma pasta com esse nome neste local.") from None
    return DocumentFolderResponse.model_validate(folder)


@router.put("/document-folders/{folder_id}", response_model=DocumentFolderResponse)
async def update_document_folder(
    folder_id: str, payload: DocumentFolderUpdate, request: Request, *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db), _write: User = Depends(require_tenant_write),
):
    require_role(current_user, CASE_MANAGER_ROLES | {"paralegal"})
    folder = await get_document_folder(db, current_user, folder_id, lock=True)
    if folder.revision != payload.expected_revision:
        raise conflict()
    if payload.parent_id == folder.id:
        raise HTTPException(status_code=422, detail="Uma pasta nao pode conter a si mesma.")
    if "parent_id" in payload.model_fields_set:
        parent = await validate_folder_scope(db, current_user, folder.client_id, folder.case_id, payload.parent_id)
        cursor = parent
        while cursor:
            if cursor.id == folder.id:
                raise HTTPException(status_code=422, detail="A movimentacao criaria um ciclo de pastas.")
            cursor = await db.scalar(select(WorkspaceDocumentFolder).where(
                WorkspaceDocumentFolder.tenant_id == current_user.tenant_id,
                WorkspaceDocumentFolder.id == cursor.parent_id,
            )) if cursor.parent_id else None
        folder.parent_id = payload.parent_id
    if payload.name is not None:
        folder.name = payload.name
        folder.normalized_name = normalized_folder_name(payload.name)
    folder.revision += 1
    try:
        await commit_mutation(db, request, current_user, "DOCUMENT_FOLDER_UPDATED", "workspace_document_folders", folder.id)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Ja existe uma pasta com esse nome neste local.") from None
    return DocumentFolderResponse.model_validate(folder)


@router.delete("/document-folders/{folder_id}", status_code=204)
async def archive_document_folder(
    folder_id: str, request: Request, *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db), _write: User = Depends(require_tenant_write),
):
    require_role(current_user, CASE_MANAGER_ROLES | {"paralegal"})
    folder = await get_document_folder(db, current_user, folder_id, lock=True)
    has_content = await db.scalar(select(WorkspaceDocument.id).where(
        WorkspaceDocument.tenant_id == current_user.tenant_id,
        WorkspaceDocument.folder_id == folder.id,
        WorkspaceDocument.deleted_at.is_(None),
    ).limit(1)) or await db.scalar(select(WorkspaceDocumentFolder.id).where(
        WorkspaceDocumentFolder.tenant_id == current_user.tenant_id,
        WorkspaceDocumentFolder.parent_id == folder.id,
        WorkspaceDocumentFolder.archived_at.is_(None),
    ).limit(1))
    if has_content:
        raise HTTPException(status_code=409, detail="Mova ou exclua o conteudo antes de remover a pasta.")
    folder.archived_at = datetime.now(timezone.utc)
    await commit_mutation(db, request, current_user, "DOCUMENT_FOLDER_ARCHIVED", "workspace_document_folders", folder.id)
    return Response(status_code=204)


@router.get("/documents", response_model=ListResponse)
async def list_documents(
    case_id: str | None = Query(default=None, max_length=64),
    client_id: str | None = Query(default=None, max_length=64),
    folder_id: str | None = Query(default=None, max_length=64),
    q: str | None = Query(default=None, min_length=2, max_length=200),
    trash: bool = False,
    general_only: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    limit = bounded_limit(limit)
    statement = document_scope(current_user)
    if case_id:
        await get_case(db, current_user, case_id)
        statement = statement.where(WorkspaceDocument.case_id == case_id)
    if client_id:
        await get_client(db, current_user, client_id)
        statement = statement.where(WorkspaceDocument.client_id == client_id)
    if general_only:
        statement = statement.where(WorkspaceDocument.case_id.is_(None))
    if folder_id:
        await get_document_folder(db, current_user, folder_id)
        statement = statement.where(WorkspaceDocument.folder_id == folder_id)
    statement = statement.where(WorkspaceDocument.deleted_at.is_not(None) if trash else WorkspaceDocument.deleted_at.is_(None))
    if q:
        cleaned = q.strip()
        like = f"%{cleaned}%"
        empty, space = literal_column("''"), literal_column("' '")
        searchable = func.coalesce(WorkspaceDocument.title, empty) + space + func.coalesce(WorkspaceDocument.filename, empty) + space + func.coalesce(WorkspaceDocument.content_text, empty)
        vector = func.to_tsvector(literal_column("'portuguese'"), searchable)
        statement = statement.where(or_(
            vector.op("@@")(func.websearch_to_tsquery("portuguese", cleaned)),
            WorkspaceDocument.title.ilike(like), WorkspaceDocument.filename.ilike(like),
        ))
    records = (await db.execute(statement.order_by(WorkspaceDocument.updated_at.desc()).limit(limit))).scalars().all()
    return list_payload([DocumentResponse.model_validate(record) for record in records], limit)


@router.post("/documents", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_document(
    payload: DocumentCreate,
    request: Request,
    *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    return DocumentResponse.model_validate(await create_document_record(payload, request, current_user, db))


@router.put("/documents/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: str,
    payload: DocumentUpdate,
    request: Request,
    *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    document = await get_document(db, current_user, document_id, for_update=True)
    return DocumentResponse.model_validate(await update_document_record(document, payload, request, current_user, db))


@router.get("/documents/{document_id}/versions")
async def list_document_versions(
    document_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    document = await get_document(db, current_user, document_id)
    limit = bounded_limit(limit)
    records = (
        await db.execute(
            select(WorkspaceDocumentVersion)
            .where(WorkspaceDocumentVersion.tenant_id == current_user.tenant_id, WorkspaceDocumentVersion.document_id == document.id)
            .order_by(WorkspaceDocumentVersion.version.desc())
            .limit(limit)
        )
    ).scalars().all()
    return {"items": [DocumentVersionResponse.model_validate(record) for record in records]}


class DocumentReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    status: str = Field(pattern="^(comment|in_review|approved|final|reopened)$")
    comment: str | None = Field(default=None, max_length=5000)
    expected_version: int = Field(ge=1)


@router.get("/documents/{document_id}/reviews")
async def list_document_reviews(
    document_id: str,
    *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    await get_document(db, current_user, document_id)
    rows = (await db.execute(
        select(WorkspaceDocumentReview, User.full_name)
        .join(User, and_(User.id == WorkspaceDocumentReview.created_by_user_id, User.tenant_id == WorkspaceDocumentReview.tenant_id))
        .where(WorkspaceDocumentReview.tenant_id == current_user.tenant_id, WorkspaceDocumentReview.document_id == document_id)
        .order_by(WorkspaceDocumentReview.created_at.desc())
        .limit(200)
    )).all()
    return {"items": [{
        "id": item.id, "version": item.version, "status": item.status,
        "comment": item.comment, "created_by_user_id": item.created_by_user_id,
        "created_by_name": name, "created_at": item.created_at,
    } for item, name in rows]}


@router.post("/documents/{document_id}/reviews", status_code=201)
async def create_document_review(
    document_id: str,
    payload: DocumentReviewInput,
    request: Request,
    *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    document = await get_document(db, current_user, document_id, for_update=True)
    require_document_write(current_user, document)
    if document.current_version != payload.expected_version:
        raise conflict("O documento mudou. Recarregue antes de registrar a revisao.")
    comment = payload.comment.strip() if payload.comment else None
    if payload.status in {"comment", "reopened"} and not comment:
        raise HTTPException(status_code=422, detail="Informe um comentario para este registro.")
    if payload.status in {"approved", "final"} and current_user.role not in CASE_MANAGER_ROLES:
        raise HTTPException(status_code=403, detail="Somente advogado ou socio pode aprovar a versao.")
    allowed = {
        "draft": {"comment", "in_review"},
        "in_review": {"comment", "approved", "reopened"},
        "approved": {"comment", "final", "reopened"},
        "final": {"comment", "reopened"},
    }
    if payload.status not in allowed[document.review_status]:
        raise HTTPException(status_code=409, detail="Esta mudanca nao corresponde a etapa atual da revisao.")
    if payload.status == "reopened":
        reset_document_review(document)
    elif payload.status != "comment":
        document.review_status = payload.status
        document.review_version = document.current_version
        if payload.status in {"approved", "final"}:
            document.reviewed_by_user_id = current_user.id
            document.reviewed_at = datetime.now(timezone.utc)
    document.revision += 1
    entry = WorkspaceDocumentReview(
        tenant_id=current_user.tenant_id, document_id=document.id,
        version=document.current_version, status=payload.status,
        comment=comment, created_by_user_id=current_user.id,
    )
    db.add(entry)
    await db.flush()
    await commit_mutation(
        db, request, current_user, "WORKSPACE_DOCUMENT_REVIEW_RECORDED",
        "workspace_documents", document.id,
        {"version": document.current_version, "status": payload.status},
    )
    return {"id": entry.id, "review_status": document.review_status, "version": entry.version}


@router.get("/documents/{document_id}/compare")
async def compare_document_versions(
    document_id: str,
    from_version: int = Query(ge=1),
    to_version: int = Query(ge=1),
    *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    document = await get_document(db, current_user, document_id)
    if from_version == to_version or max(from_version, to_version) > document.current_version:
        raise HTTPException(status_code=422, detail="Escolha duas versoes existentes e diferentes.")
    versions = (await db.scalars(select(WorkspaceDocumentVersion).where(
        WorkspaceDocumentVersion.tenant_id == current_user.tenant_id,
        WorkspaceDocumentVersion.document_id == document.id,
        WorkspaceDocumentVersion.version.in_((from_version, to_version)),
    ))).all()
    by_number = {item.version: item for item in versions}
    if len(by_number) != 2:
        raise HTTPException(status_code=404, detail="Versao nao encontrada.")
    before = (by_number[from_version].content_text or "").splitlines()
    after = (by_number[to_version].content_text or "").splitlines()
    diff = "\n".join(difflib.unified_diff(before, after, fromfile=f"versao-{from_version}", tofile=f"versao-{to_version}", lineterm=""))
    return {"from_version": from_version, "to_version": to_version, "diff": diff[:200_000]}


@router.post("/documents/{document_id}/upload", response_model=DocumentResponse)
async def upload_document_file(
    document_id: str,
    request: Request,
    expected_version: int = Form(ge=1),
    file: UploadFile = File(...),
    *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    document = await get_document(db, current_user, document_id, for_update=True)
    require_document_write(current_user, document)
    if document.deleted_at:
        raise HTTPException(status_code=409, detail="Restaure o arquivo antes de substitui-lo.")
    if document.current_version != expected_version:
        raise conflict("Versao do documento desatualizada.")
    filename, content_type, content, digest = await read_validated_upload(file)
    try:
        extracted_text = await asyncio.to_thread(extract_upload_text, content_type, content)
    except TextExtractionError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from None
    next_content_text = document.content_text or extracted_text
    await ensure_document_storage_capacity(
        db,
        current_user.tenant_id,
        document_version_bytes(next_content_text, content),
    )
    document.filename = filename
    document.content_type = content_type
    document.file_content = content
    document.file_size = len(content)
    document.sha256_hash = digest
    document.content_text = next_content_text
    document.current_version += 1
    document.revision += 1
    reset_document_review(document)
    db.add(
        WorkspaceDocumentVersion(
            tenant_id=current_user.tenant_id,
            document_id=document.id,
            version=document.current_version,
            content_text=document.content_text,
            content_format=document.content_format,
            filename=filename,
            content_type=content_type,
            file_content=content,
            file_size=len(content),
            sha256_hash=digest,
            created_by_user_id=current_user.id,
        )
    )
    await commit_mutation(
        db, request, current_user, "WORKSPACE_DOCUMENT_FILE_UPLOADED", "workspace_documents", document.id, {"version": document.current_version, "sha256": digest}
    )
    return DocumentResponse.model_validate(document)


@router.post("/document-uploads", status_code=201)
async def create_document_upload(
    payload: DocumentUploadCreate, request: Request, *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db), _write: User = Depends(require_tenant_write),
):
    if not r2_enabled():
        raise HTTPException(status_code=503, detail="Armazenamento R2 ainda nao foi configurado.")
    require_role(current_user, CASE_MANAGER_ROLES | {"paralegal"})
    filename = PurePath(payload.filename).name
    if filename != payload.filename or "\x00" in filename:
        raise HTTPException(status_code=422, detail="Nome de arquivo invalido.")
    content_type = ALLOWED_UPLOAD_TYPES.get(PurePath(filename).suffix.casefold())
    if not content_type:
        raise HTTPException(status_code=422, detail="Use PDF, DOCX, XLSX, TXT, JPG ou PNG.")
    if payload.size > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Arquivo excede 25 MB.")
    await validate_folder_scope(db, current_user, payload.client_id, payload.case_id, payload.folder_id)
    if payload.document_id:
        document = await get_document(db, current_user, payload.document_id)
        require_document_write(current_user, document)
        if document.deleted_at:
            raise HTTPException(status_code=409, detail="Restaure o arquivo antes de enviar uma nova versao.")
        if document.current_version != payload.expected_version:
            raise conflict("Versao do documento desatualizada.")
        if document.client_id != payload.client_id or document.case_id != payload.case_id:
            raise HTTPException(status_code=422, detail="O documento nao pertence ao cliente e processo informados.")
        if document.folder_id != payload.folder_id:
            raise HTTPException(status_code=422, detail="Mova o arquivo antes de enviar uma versao em outra pasta.")
    await ensure_document_storage_capacity(db, current_user.tenant_id, payload.size)
    upload = WorkspaceDocumentUpload(
        id=str(uuid.uuid4()),
        tenant_id=current_user.tenant_id, document_id=payload.document_id,
        expected_version=payload.expected_version, folder_id=payload.folder_id,
        client_id=payload.client_id, case_id=payload.case_id,
        filename=filename, content_type=content_type, expected_size=payload.size,
        expected_sha256=payload.sha256, object_key="pending", status="created",
        created_by_user_id=current_user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )
    upload.object_key = quarantine_key(current_user.tenant_id, upload.id)
    signed = await asyncio.to_thread(create_upload_url, upload.object_key, content_type, payload.sha256)
    db.add(upload)
    await commit_mutation(db, request, current_user, "DOCUMENT_UPLOAD_AUTHORIZED", "workspace_document_uploads", upload.id, {"size": payload.size, "content_type": content_type})
    return {**DocumentUploadResponse.model_validate(upload).model_dump(), "upload_url": signed["url"], "upload_headers": signed["headers"]}


@router.get("/document-storage")
async def document_storage_capability():
    return {"direct_uploads": r2_enabled(), "max_file_size": MAX_UPLOAD_BYTES, "formats": sorted(ALLOWED_UPLOAD_TYPES)}


@router.post("/documents/upload-file", response_model=DocumentResponse, status_code=201)
async def upload_new_document_legacy(
    request: Request,
    client_id: str = Form(max_length=64),
    case_id: str | None = Form(default=None, max_length=64),
    folder_id: str | None = Form(default=None, max_length=64),
    file: UploadFile = File(...),
    *, current_user: CurrentUser, db: AsyncSession = Depends(get_db), _write: User = Depends(require_tenant_write),
):
    if r2_enabled():
        raise HTTPException(status_code=409, detail="Use o upload direto seguro configurado para este ambiente.")
    require_role(current_user, CASE_MANAGER_ROLES | {"paralegal"})
    await validate_folder_scope(db, current_user, client_id, case_id, folder_id)
    filename, content_type, content, digest = await read_validated_upload(file)
    try:
        extracted = await asyncio.to_thread(extract_upload_text, content_type, content)
    except TextExtractionError:
        extracted = None
    await ensure_document_storage_capacity(db, current_user.tenant_id, document_version_bytes(extracted, content))
    document = WorkspaceDocument(
        tenant_id=current_user.tenant_id, client_id=client_id, case_id=case_id, folder_id=folder_id,
        kind="evidence", title=PurePath(filename).stem[:300], content_text=extracted,
        filename=filename, content_type=content_type, file_content=content, file_size=len(content), sha256_hash=digest,
    )
    db.add(document)
    await db.flush()
    db.add(WorkspaceDocumentVersion(
        tenant_id=current_user.tenant_id, document_id=document.id, version=1, content_text=extracted,
        filename=filename, content_type=content_type, file_content=content, file_size=len(content), sha256_hash=digest,
        created_by_user_id=current_user.id,
    ))
    await commit_mutation(db, request, current_user, "WORKSPACE_DOCUMENT_FILE_UPLOADED", "workspace_documents", document.id, {"version": 1, "sha256": digest, "storage": "database-development"})
    return DocumentResponse.model_validate(document)


@router.post("/document-uploads/{upload_id}/complete")
async def complete_document_upload(
    upload_id: str, request: Request, *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db), _write: User = Depends(require_tenant_write),
):
    upload = await db.scalar(select(WorkspaceDocumentUpload).where(
        WorkspaceDocumentUpload.id == upload_id,
        WorkspaceDocumentUpload.tenant_id == current_user.tenant_id,
        WorkspaceDocumentUpload.created_by_user_id == current_user.id,
    ).with_for_update())
    if not upload:
        raise HTTPException(status_code=404, detail="Upload nao encontrado.")
    if upload.expires_at <= datetime.now(timezone.utc) and upload.status == "created":
        upload.status = "expired"
        await db.commit()
        raise HTTPException(status_code=410, detail="A autorizacao de upload expirou.")
    if upload.status == "created":
        upload.status = "uploaded"
        await commit_mutation(db, request, current_user, "DOCUMENT_UPLOAD_RECEIVED", "workspace_document_uploads", upload.id)
    elif upload.status not in {"uploaded", "processing", "completed"}:
        raise HTTPException(status_code=409, detail=upload.error or "Upload nao pode ser processado.")
    if upload.status != "completed":
        try:
            process_upload.apply_async(args=[upload.id, upload.tenant_id], queue="documents")
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Upload recebido; processamento sera retomado quando a fila voltar.") from exc
    return DocumentUploadResponse.model_validate(upload)


@router.get("/document-uploads/{upload_id}", response_model=DocumentUploadResponse)
async def get_document_upload_status(
    upload_id: str, *, current_user: CurrentUser, db: AsyncSession = Depends(get_db),
):
    upload = await db.scalar(select(WorkspaceDocumentUpload).where(
        WorkspaceDocumentUpload.id == upload_id,
        WorkspaceDocumentUpload.tenant_id == current_user.tenant_id,
    ))
    if not upload:
        raise HTTPException(status_code=404, detail="Upload nao encontrado.")
    if upload.case_id:
        await get_case(db, current_user, upload.case_id)
    return DocumentUploadResponse.model_validate(upload)


@router.delete("/documents/{document_id}", status_code=204)
async def trash_document(
    document_id: str, request: Request, *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db), _write: User = Depends(require_tenant_write),
):
    document = await get_document(db, current_user, document_id, for_update=True)
    require_document_write(current_user, document)
    if not document.deleted_at:
        document.deleted_at = datetime.now(timezone.utc)
        document.purge_after = document.deleted_at + timedelta(days=30)
        document.revision += 1
        await commit_mutation(db, request, current_user, "WORKSPACE_DOCUMENT_TRASHED", "workspace_documents", document.id)
    return Response(status_code=204)


@router.put("/documents/{document_id}/move", response_model=DocumentResponse)
async def move_document(
    document_id: str, payload: DocumentMove, request: Request, *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db), _write: User = Depends(require_tenant_write),
):
    document = await get_document(db, current_user, document_id, for_update=True)
    require_document_write(current_user, document)
    if document.deleted_at:
        raise HTTPException(status_code=409, detail="Restaure o arquivo antes de move-lo.")
    if document.revision != payload.expected_revision:
        raise conflict()
    if payload.folder_id:
        folder = await get_document_folder(db, current_user, payload.folder_id)
        if folder.client_id != document.client_id or folder.case_id != document.case_id:
            raise HTTPException(status_code=422, detail="A pasta deve pertencer ao mesmo cliente e processo.")
    document.folder_id = payload.folder_id
    document.revision += 1
    await commit_mutation(db, request, current_user, "WORKSPACE_DOCUMENT_MOVED", "workspace_documents", document.id, {"folder_id": payload.folder_id})
    return DocumentResponse.model_validate(document)


@router.post("/documents/{document_id}/restore", response_model=DocumentResponse)
async def restore_document(
    document_id: str, request: Request, *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db), _write: User = Depends(require_tenant_write),
):
    document = await get_document(db, current_user, document_id, for_update=True)
    require_document_write(current_user, document)
    if document.deleted_at:
        document.deleted_at = None
        document.purge_after = None
        document.revision += 1
        await commit_mutation(db, request, current_user, "WORKSPACE_DOCUMENT_RESTORED", "workspace_documents", document.id)
    return DocumentResponse.model_validate(document)


@router.get("/documents/{document_id}/download")
async def download_document_file(
    document_id: str,
    *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    document = await get_document(db, current_user, document_id)
    if document.deleted_at:
        raise HTTPException(status_code=404, detail="Arquivo esta na lixeira.")
    version = await db.scalar(select(WorkspaceDocumentVersion).where(
        WorkspaceDocumentVersion.tenant_id == current_user.tenant_id,
        WorkspaceDocumentVersion.document_id == document.id,
        WorkspaceDocumentVersion.version == document.current_version,
    ))
    if version and version.object_key:
        if version.storage_status != "available":
            raise HTTPException(status_code=409, detail="Arquivo ainda nao esta disponivel.")
        url = await asyncio.to_thread(create_download_url, version.object_key, document.filename or "documento", document.content_type or "application/octet-stream")
        await AuditService.log_action(db, current_user.tenant_id, current_user.id, "WORKSPACE_DOCUMENT_DOWNLOADED", "workspace_documents", document.id, {"version": document.current_version})
        await db.commit()
        return RedirectResponse(url, status_code=307, headers={"Cache-Control": "private, no-store", "Referrer-Policy": "no-referrer"})
    if not document.file_content or not document.filename or not document.content_type:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Arquivo nao encontrado.")
    await AuditService.log_action(db, current_user.tenant_id, current_user.id, "WORKSPACE_DOCUMENT_DOWNLOADED", "workspace_documents", document.id, {"version": document.current_version})
    await db.commit()
    return Response(
        content=document.file_content,
        media_type=document.content_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(document.filename)}", "Cache-Control": "private, no-store"},
    )


@router.get("/templates", response_model=ListResponse)
async def list_templates(
    limit: int = Query(default=50, ge=1, le=200),
    *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    limit = bounded_limit(limit)
    records = (
        await db.execute(
            select(WorkspaceDocument)
            .where(WorkspaceDocument.tenant_id == current_user.tenant_id, WorkspaceDocument.kind == "template")
            .order_by(WorkspaceDocument.updated_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return list_payload([DocumentResponse.model_validate(record) for record in records], limit)


@router.post("/templates", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    payload: DocumentCreate,
    request: Request,
    *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    payload = payload.model_copy(update={"kind": "template", "case_id": None, "client_id": None})
    return DocumentResponse.model_validate(await create_document_record(payload, request, current_user, db))


@router.put("/templates/{document_id}", response_model=DocumentResponse)
async def update_template(
    document_id: str,
    payload: DocumentUpdate,
    request: Request,
    *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    document = await get_document(db, current_user, document_id, for_update=True)
    if document.kind != "template":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Modelo nao encontrado.")
    return DocumentResponse.model_validate(await update_document_record(document, payload, request, current_user, db))


@router.get("/library", response_model=ListResponse)
async def list_library_entries(
    limit: int = Query(default=50, ge=1, le=200),
    *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    limit = bounded_limit(limit)
    records = (
        await db.execute(
            select(WorkspaceLibraryEntry)
            .where(WorkspaceLibraryEntry.tenant_id == current_user.tenant_id)
            .order_by(WorkspaceLibraryEntry.updated_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return list_payload([LibraryEntryResponse.model_validate(record) for record in records], limit)


@router.post("/library", response_model=LibraryEntryResponse, status_code=status.HTTP_201_CREATED)
async def create_library_entry(
    payload: LibraryEntryCreate,
    request: Request,
    *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    require_role(current_user, CASE_MANAGER_ROLES)
    record = WorkspaceLibraryEntry(tenant_id=current_user.tenant_id, created_by_user_id=current_user.id, **payload.model_dump())
    db.add(record)
    await db.flush()
    await commit_mutation(db, request, current_user, "WORKSPACE_LIBRARY_ENTRY_CREATED", "workspace_library_entries", record.id)
    return LibraryEntryResponse.model_validate(record)


@router.put("/library/{entry_id}", response_model=LibraryEntryResponse)
async def update_library_entry(
    entry_id: str,
    payload: LibraryEntryUpdate,
    request: Request,
    *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    require_role(current_user, CASE_MANAGER_ROLES)
    record = await db.scalar(
        select(WorkspaceLibraryEntry).where(WorkspaceLibraryEntry.id == entry_id, WorkspaceLibraryEntry.tenant_id == current_user.tenant_id)
    )
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entrada de biblioteca nao encontrada.")
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Nenhuma alteracao informada.")
    for field, value in changes.items():
        if field == "title" and value is None:
            continue
        setattr(record, field, value)
    await commit_mutation(
        db, request, current_user, "WORKSPACE_LIBRARY_ENTRY_UPDATED", "workspace_library_entries", record.id, {"fields": sorted(changes)}
    )
    return LibraryEntryResponse.model_validate(record)


def publication_dedupe_key(payload: PublicationCreate) -> str:
    material = f"{payload.case_id}|{payload.source_url}|{payload.published_at.isoformat()}|{payload.title.strip().casefold()}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


@router.get("/publications", response_model=ListResponse)
async def list_publications(
    limit: int = Query(default=50, ge=1, le=200),
    *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    limit = bounded_limit(limit)
    records = (
        await db.execute(
            select(WorkspacePublication)
            .join(
                WorkspaceCase,
                and_(WorkspaceCase.id == WorkspacePublication.case_id, WorkspaceCase.tenant_id == WorkspacePublication.tenant_id),
            )
            .where(WorkspacePublication.tenant_id == current_user.tenant_id, case_access_clause(current_user))
            .order_by(WorkspacePublication.published_at.desc(), WorkspacePublication.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return list_payload([PublicationResponse.model_validate(record) for record in records], limit)


@router.post("/publications", response_model=PublicationResponse, status_code=status.HTTP_201_CREATED)
async def create_publication(
    payload: PublicationCreate,
    request: Request,
    *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    case = await get_case(db, current_user, payload.case_id)
    require_case_write(current_user, case)
    dedupe_key = publication_dedupe_key(payload)
    existing = await db.scalar(
        select(WorkspacePublication).where(
            WorkspacePublication.tenant_id == current_user.tenant_id,
            WorkspacePublication.dedupe_key == dedupe_key,
        )
    )
    if existing:
        return PublicationResponse.model_validate(existing)
    record = WorkspacePublication(
        tenant_id=current_user.tenant_id,
        created_by_user_id=current_user.id,
        dedupe_key=dedupe_key,
        **payload.model_dump(),
    )
    try:
        async with db.begin_nested():
            db.add(record)
            await db.flush()
    except IntegrityError:
        existing = await db.scalar(
            select(WorkspacePublication).where(
                WorkspacePublication.tenant_id == current_user.tenant_id,
                WorkspacePublication.dedupe_key == dedupe_key,
            )
        )
        if existing:
            return PublicationResponse.model_validate(existing)
        raise
    await commit_mutation(db, request, current_user, "WORKSPACE_PUBLICATION_RECORDED", "workspace_publications", record.id)
    return PublicationResponse.model_validate(record)


@router.put("/publications/{publication_id}", response_model=PublicationResponse)
async def update_publication(
    publication_id: str,
    payload: PublicationUpdate,
    request: Request,
    *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    record = await db.scalar(
        select(WorkspacePublication)
        .join(WorkspaceCase, and_(WorkspaceCase.id == WorkspacePublication.case_id, WorkspaceCase.tenant_id == WorkspacePublication.tenant_id))
        .where(
            WorkspacePublication.id == publication_id,
            WorkspacePublication.tenant_id == current_user.tenant_id,
            case_access_clause(current_user),
        )
    )
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Publicacao nao encontrada.")
    require_case_write(current_user, await get_case(db, current_user, record.case_id))
    if "note" not in payload.model_fields_set:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Nenhuma alteracao informada.")
    record.note = payload.note
    await commit_mutation(db, request, current_user, "WORKSPACE_PUBLICATION_UPDATED", "workspace_publications", record.id)
    return PublicationResponse.model_validate(record)


@router.post("/publications/{publication_id}/acknowledge", response_model=PublicationResponse)
async def acknowledge_publication(
    publication_id: str,
    request: Request,
    *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    record = await db.scalar(
        select(WorkspacePublication)
        .join(WorkspaceCase, and_(WorkspaceCase.id == WorkspacePublication.case_id, WorkspaceCase.tenant_id == WorkspacePublication.tenant_id))
        .where(
            WorkspacePublication.id == publication_id,
            WorkspacePublication.tenant_id == current_user.tenant_id,
            case_access_clause(current_user),
        )
        .with_for_update()
    )
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Publicacao nao encontrada.")
    record.acknowledged_at = record.acknowledged_at or datetime.now(timezone.utc)
    record.acknowledged_by_user_id = record.acknowledged_by_user_id or current_user.id
    await commit_mutation(db, request, current_user, "WORKSPACE_PUBLICATION_ACKNOWLEDGED", "workspace_publications", record.id)
    return PublicationResponse.model_validate(record)


async def get_ledger_entry(db: AsyncSession, user: User, entry_id: str, *, for_update: bool = False) -> WorkspaceLedgerEntry:
    statement = select(WorkspaceLedgerEntry).where(
        WorkspaceLedgerEntry.id == entry_id,
        WorkspaceLedgerEntry.tenant_id == user.tenant_id,
    )
    if for_update:
        statement = statement.with_for_update()
    entry = await db.scalar(statement)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lancamento nao encontrado.")
    if entry.case_id:
        await get_case(db, user, entry.case_id)
    return entry


@router.get("/ledger", response_model=ListResponse)
async def list_ledger_entries(
    case_id: str | None = Query(default=None, max_length=64),
    limit: int = Query(default=50, ge=1, le=200),
    *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    require_finance_role(current_user)
    limit = bounded_limit(limit)
    statement = select(WorkspaceLedgerEntry).where(WorkspaceLedgerEntry.tenant_id == current_user.tenant_id)
    if case_id:
        await get_case(db, current_user, case_id)
        statement = statement.where(WorkspaceLedgerEntry.case_id == case_id)
    records = (await db.execute(statement.order_by(WorkspaceLedgerEntry.created_at.desc()).limit(limit))).scalars().all()
    return list_payload([LedgerEntryResponse.model_validate(record) for record in records], limit)


@router.post("/ledger", response_model=LedgerEntryResponse, status_code=status.HTTP_201_CREATED)
async def create_ledger_entry(
    payload: LedgerEntryCreate,
    request: Request,
    *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    require_finance_role(current_user)
    await ensure_case_reference(db, current_user, payload.case_id)
    await ensure_client_reference(db, current_user, payload.client_id)
    entry = WorkspaceLedgerEntry(
        tenant_id=current_user.tenant_id,
        created_by_user_id=current_user.id,
        status="draft",
        **payload.model_dump(),
    )
    db.add(entry)
    await db.flush()
    await commit_mutation(db, request, current_user, "WORKSPACE_LEDGER_ENTRY_CREATED", "workspace_ledger_entries", entry.id)
    return LedgerEntryResponse.model_validate(entry)


@router.put("/ledger/{entry_id}", response_model=LedgerEntryResponse)
async def update_ledger_entry(
    entry_id: str,
    payload: LedgerEntryUpdate,
    request: Request,
    *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    require_finance_role(current_user)
    entry = await get_ledger_entry(db, current_user, entry_id, for_update=True)
    if entry.status != "draft":
        raise conflict("Somente lancamentos em rascunho podem ser alterados.")
    entry.description = payload.description
    await commit_mutation(db, request, current_user, "WORKSPACE_LEDGER_ENTRY_UPDATED", "workspace_ledger_entries", entry.id)
    return LedgerEntryResponse.model_validate(entry)


@router.post("/ledger/{entry_id}/post", response_model=LedgerEntryResponse)
async def post_ledger_entry(
    entry_id: str,
    request: Request,
    *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    require_finance_role(current_user)
    entry = await get_ledger_entry(db, current_user, entry_id, for_update=True)
    if entry.entry_type == "payment":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Pagamento exige confirmacao manual com motivo.")
    if entry.status != "draft":
        raise conflict("Lancamento ja foi processado.")
    entry.status = "posted"
    await commit_mutation(db, request, current_user, "WORKSPACE_LEDGER_ENTRY_POSTED", "workspace_ledger_entries", entry.id)
    return LedgerEntryResponse.model_validate(entry)


@router.post("/ledger/payments/manual", response_model=LedgerEntryResponse, status_code=status.HTTP_201_CREATED)
async def confirm_manual_payment(
    payload: ManualPaymentCreate,
    request: Request,
    *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    require_finance_role(current_user)
    await ensure_case_reference(db, current_user, payload.case_id)
    await ensure_client_reference(db, current_user, payload.client_id)
    request_id = str(payload.request_id)
    existing = await db.scalar(
        select(WorkspaceLedgerEntry).where(
            WorkspaceLedgerEntry.tenant_id == current_user.tenant_id,
            WorkspaceLedgerEntry.request_id == request_id,
        )
    )
    if existing:
        return LedgerEntryResponse.model_validate(existing)
    now = datetime.now(timezone.utc)
    entry = WorkspaceLedgerEntry(
        tenant_id=current_user.tenant_id,
        created_by_user_id=current_user.id,
        entry_type="payment",
        amount=payload.amount,
        currency=payload.currency,
        description=payload.description,
        status="posted",
        manual_payment_confirmed_at=now,
        manual_payment_confirmed_by_user_id=current_user.id,
        manual_confirmation_reason=payload.confirmation_reason,
        case_id=payload.case_id,
        client_id=payload.client_id,
        request_id=request_id,
    )
    try:
        async with db.begin_nested():
            db.add(entry)
            await db.flush()
    except IntegrityError:
        existing = await db.scalar(
            select(WorkspaceLedgerEntry).where(
                WorkspaceLedgerEntry.tenant_id == current_user.tenant_id,
                WorkspaceLedgerEntry.request_id == request_id,
            )
        )
        if existing:
            return LedgerEntryResponse.model_validate(existing)
        raise
    await commit_mutation(
        db, request, current_user, "WORKSPACE_MANUAL_PAYMENT_CONFIRMED", "workspace_ledger_entries", entry.id, {"reason_recorded": True}
    )
    return LedgerEntryResponse.model_validate(entry)


@router.post("/ledger/{entry_id}/reverse", response_model=LedgerEntryResponse)
async def reverse_ledger_entry(
    entry_id: str,
    payload: LedgerReverse,
    request: Request,
    *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    require_finance_role(current_user)
    entry = await get_ledger_entry(db, current_user, entry_id, for_update=True)
    if entry.status != "posted":
        raise conflict("Somente lancamentos contabilizados podem ser estornados.")
    entry.status = "reversed"
    entry.reversal_reason = payload.reason
    reversal = WorkspaceLedgerEntry(
        tenant_id=current_user.tenant_id,
        created_by_user_id=current_user.id,
        case_id=entry.case_id,
        client_id=entry.client_id,
        entry_type=entry.entry_type,
        amount=entry.amount,
        currency=entry.currency,
        duration_minutes=entry.duration_minutes,
        description=f"Estorno de {entry.id}",
        status="reversed",
        reversal_of_id=entry.id,
        reversal_reason=payload.reason,
    )
    db.add(reversal)
    await db.flush()
    await commit_mutation(
        db, request, current_user, "WORKSPACE_LEDGER_ENTRY_REVERSED", "workspace_ledger_entries", entry.id, {"reversal_entry_id": reversal.id}
    )
    return LedgerEntryResponse.model_validate(entry)


@router.get("/conflicts")
async def find_conflicts(
    q: str = Query(min_length=2, max_length=200),
    tax_id: str | None = Query(default=None, max_length=20),
    limit: int = Query(default=50, ge=1, le=200),
    *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    limit = bounded_limit(limit)
    query = q.strip()
    if not query:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Consulta invalida.")
    clients = (
        await db.execute(
            select(WorkspaceClient)
            .where(
                WorkspaceClient.tenant_id == current_user.tenant_id,
                or_(WorkspaceClient.name.ilike(f"%{query}%"), WorkspaceClient.tax_id == tax_id if tax_id else False),
            )
            .limit(limit)
        )
    ).scalars().all()
    parties = (
        await db.execute(
            select(WorkspaceCaseParty, WorkspaceCase)
            .join(
                WorkspaceCase,
                and_(WorkspaceCase.id == WorkspaceCaseParty.case_id, WorkspaceCase.tenant_id == WorkspaceCaseParty.tenant_id),
            )
            .where(
                WorkspaceCaseParty.tenant_id == current_user.tenant_id,
                case_access_clause(current_user),
                or_(WorkspaceCaseParty.name.ilike(f"%{query}%"), WorkspaceCaseParty.tax_id == tax_id if tax_id else False),
            )
            .limit(limit)
        )
    ).all()
    return {
        "query": query,
        "matches": [
            {"record_type": "client", "id": client.id, "name": client.name, "tax_id": client.tax_id, "source": "workspace_clients"}
            for client in clients
        ]
        + [
            {"record_type": "party", "id": party.id, "name": party.name, "tax_id": party.tax_id, "side": party.side, "case_id": case.id, "case_number": case.number, "source": "workspace_case_parties"}
            for party, case in parties
        ],
        "manual_review_required": True,
    }


@router.get("/search")
async def search_workspace(
    q: str = Query(min_length=2, max_length=200),
    limit: int = Query(default=20, ge=1, le=200),
    *, current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    limit = bounded_limit(limit)
    query = q.strip()
    if not query:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Consulta invalida.")
    def matches(*columns):
        return or_(*(column.contains(query, autoescape=True) for column in columns))

    def excerpt(value: str | None, maximum: int = 180) -> str | None:
        if not value:
            return None
        compact = " ".join(value.split())
        return compact if len(compact) <= maximum else f"{compact[:maximum - 1]}…"

    clients = (
        await db.execute(
            select(WorkspaceClient)
            .where(
                WorkspaceClient.tenant_id == current_user.tenant_id,
                WorkspaceClient.archived_at.is_(None),
                matches(
                    WorkspaceClient.name,
                    WorkspaceClient.email,
                    WorkspaceClient.phone,
                    WorkspaceClient.tax_id,
                ),
            )
            .order_by(WorkspaceClient.updated_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    cases = (
        await db.execute(
            authorized_case_query(current_user)
            .where(
                WorkspaceCase.archived_at.is_(None),
                matches(WorkspaceCase.title, WorkspaceCase.number, WorkspaceCase.court),
            )
            .order_by(WorkspaceCase.updated_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    documents = (
        await db.execute(
            document_scope(current_user)
            .where(
                WorkspaceDocument.deleted_at.is_(None),
                or_(
                    func.to_tsvector("portuguese", func.concat_ws(" ", WorkspaceDocument.title, WorkspaceDocument.filename, WorkspaceDocument.content_text)).op("@@")(func.websearch_to_tsquery("portuguese", query)),
                    matches(WorkspaceDocument.title, WorkspaceDocument.filename),
                ),
            )
            .order_by(WorkspaceDocument.updated_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    task_statement = await authorized_task_statement(current_user)
    tasks = (
        await db.execute(
            task_statement
            .where(matches(WorkspaceTask.title, WorkspaceTask.location, WorkspaceTask.contact, WorkspaceTask.notes))
            .order_by(WorkspaceTask.updated_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    publications = (
        await db.execute(
            select(WorkspacePublication)
            .join(
                WorkspaceCase,
                and_(
                    WorkspaceCase.id == WorkspacePublication.case_id,
                    WorkspaceCase.tenant_id == WorkspacePublication.tenant_id,
                ),
            )
            .where(
                WorkspacePublication.tenant_id == current_user.tenant_id,
                case_access_clause(current_user),
                matches(WorkspacePublication.title, WorkspacePublication.note),
            )
            .order_by(WorkspacePublication.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    library = (
        await db.execute(
            select(WorkspaceLibraryEntry)
            .where(
                WorkspaceLibraryEntry.tenant_id == current_user.tenant_id,
                WorkspaceLibraryEntry.archived_at.is_(None),
                matches(WorkspaceLibraryEntry.title, WorkspaceLibraryEntry.note, WorkspaceLibraryEntry.source_url),
            )
            .order_by(WorkspaceLibraryEntry.updated_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    messages = (
        await db.execute(
            select(CaseMessage)
            .join(
                WorkspaceCase,
                and_(WorkspaceCase.id == CaseMessage.case_id, WorkspaceCase.tenant_id == CaseMessage.tenant_id),
            )
            .where(
                CaseMessage.tenant_id == current_user.tenant_id,
                case_access_clause(current_user),
                CaseMessage.body.contains(query, autoescape=True),
            )
            .order_by(CaseMessage.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    results = [
        *(
            {
                "kind": "client",
                "id": record.id,
                "title": record.name,
                "subtitle": record.email or record.phone or "Cliente cadastrado",
                "snippet": record.tax_id,
                "href": "/dashboard/crm",
                "updated_at": record.updated_at,
            }
            for record in clients
        ),
        *(
            {
                "kind": "case",
                "id": record.id,
                "title": record.title,
                "subtitle": record.number or "Processo sem número judicial",
                "snippet": record.court,
                "href": f"/dashboard/cases/{record.id}",
                "updated_at": record.updated_at,
            }
            for record in cases
        ),
        *(
            {
                "kind": "document",
                "id": record.id,
                "title": record.title,
                "subtitle": record.filename or "Documento de texto",
                "snippet": excerpt(record.content_text),
                "href": f"/dashboard/cases/{record.case_id}" if record.case_id else "/dashboard/petitions/editor",
                "updated_at": record.updated_at,
            }
            for record in documents
        ),
        *(
            {
                "kind": "task",
                "id": record.id,
                "title": record.title,
                "subtitle": record.kind,
                "snippet": excerpt(record.notes or record.location),
                "href": f"/dashboard/cases/{record.case_id}" if record.case_id else "/dashboard/tasks",
                "updated_at": record.updated_at,
            }
            for record in tasks
        ),
        *(
            {
                "kind": "publication",
                "id": record.id,
                "title": record.title,
                "subtitle": "Andamento processual",
                "snippet": excerpt(record.note),
                "href": f"/dashboard/cases/{record.case_id}",
                "updated_at": record.created_at,
            }
            for record in publications
        ),
        *(
            {
                "kind": "library",
                "id": record.id,
                "title": record.title,
                "subtitle": "Biblioteca do escritório",
                "snippet": excerpt(record.note),
                "href": "/dashboard/library",
                "updated_at": record.updated_at,
            }
            for record in library
        ),
        *(
            {
                "kind": "message",
                "id": record.id,
                "title": "Mensagem do processo",
                "subtitle": record.channel,
                "snippet": excerpt(record.body),
                "href": f"/dashboard/cases/{record.case_id}",
                "updated_at": record.created_at,
            }
            for record in messages
        ),
    ]
    results.sort(key=lambda item: item["updated_at"], reverse=True)
    return {
        "clients": [ClientResponse.model_validate(record) for record in clients],
        "cases": [CaseResponse.model_validate(record) for record in cases],
        "documents": [DocumentResponse.model_validate(record) for record in documents],
        "results": results[:limit],
    }


async def grouped_counts(db: AsyncSession, statement, column) -> dict[str, int]:
    rows = (await db.execute(statement.with_only_columns(column, func.count()).group_by(column))).all()
    return {value: count for value, count in rows}


def daily_time_context(timezone_name: str, now: datetime | None = None) -> tuple[ZoneInfo, datetime, datetime]:
    office_tz = ZoneInfo(timezone_name)
    utc_now = now or datetime.now(timezone.utc)
    local_now = utc_now.astimezone(office_tz)
    tomorrow_start = (datetime.combine(local_now.date(), time.min, tzinfo=office_tz) + timedelta(days=1)).astimezone(timezone.utc)
    return office_tz, utc_now, tomorrow_start


def summarize_task_dates(
    records,
    now: datetime | None = None,
    timezone_name: str = "America/Sao_Paulo",
) -> dict[str, int]:
    _, utc_now, tomorrow_start = daily_time_context(timezone_name, now)
    return {
        "overdue": sum(1 for task in records if task.status not in {"completed", "cancelled"} and task.due_at and task.due_at < utc_now),
        "due_today": sum(1 for task in records if task.status not in {"completed", "cancelled"} and task.due_at and utc_now <= task.due_at < tomorrow_start),
        "upcoming": sum(1 for task in records if task.status not in {"completed", "cancelled"} and task.due_at and task.due_at >= tomorrow_start),
        "completed": sum(1 for task in records if task.status == "completed"),
        "hearings_upcoming": sum(1 for task in records if task.kind == "hearing" and task.status not in {"completed", "cancelled"} and task.due_at and task.due_at >= utc_now),
    }


async def task_counts(
    db: AsyncSession,
    user: User,
    *,
    now: datetime | None = None,
    timezone_name: str = "America/Sao_Paulo",
) -> dict[str, int]:
    _, utc_now, tomorrow_start = daily_time_context(timezone_name, now)
    statement = await authorized_task_statement(user)
    open_task = WorkspaceTask.status.in_(("pending", "in_progress"))
    row = (
        await db.execute(
            statement.with_only_columns(
                func.count(WorkspaceTask.id).filter(and_(open_task, WorkspaceTask.due_at < utc_now)).label("overdue"),
                func.count(WorkspaceTask.id).filter(
                    and_(open_task, WorkspaceTask.due_at >= utc_now, WorkspaceTask.due_at < tomorrow_start)
                ).label("due_today"),
                func.count(WorkspaceTask.id).filter(and_(open_task, WorkspaceTask.due_at >= tomorrow_start)).label("upcoming"),
                func.count(WorkspaceTask.id).filter(WorkspaceTask.status == "completed").label("completed"),
                func.count(WorkspaceTask.id).filter(
                    and_(
                        open_task,
                        WorkspaceTask.kind == "hearing",
                        WorkspaceTask.due_at >= utc_now,
                    )
                ).label("hearings_upcoming"),
                maintain_column_froms=True,
            )
        )
    ).one()
    return {key: int(getattr(row, key) or 0) for key in ("overdue", "due_today", "upcoming", "completed", "hearings_upcoming")}


def priority_actions(item: dict, user: User) -> list[str]:
    if item["source"] == "task":
        can_write = user.role in CASE_MANAGER_ROLES | {"paralegal"}
        if user.role == "paralegal" and item.get("assigned_user_id") not in {None, user.id}:
            can_write = False
        return ["complete", "reschedule"] if can_write else []
    if item["source"] != "case_without_action":
        return []
    if user.role == "paralegal" or user.role in ADMIN_ROLES:
        return ["create_next_action"]
    if user.role == "lawyer" and item.get("responsible_user_id") == user.id:
        return ["create_next_action"]
    return []


async def daily_priority_items(
    db: AsyncSession,
    user: User,
    *,
    now: datetime,
    tomorrow_start: datetime,
    limit: int = 20,
) -> list[dict]:
    open_task = WorkspaceTask.status.in_(("pending", "in_progress"))
    none_text = literal(None, type_=WorkspaceTask.title.type)
    none_int = literal(None, type_=WorkspaceTask.revision.type)
    none_bool = literal(None, type_=WorkspaceTask.manually_reviewed.type)
    task_rank = sql_case(
        (WorkspaceTask.due_at < now, 0),
        (
            and_(WorkspaceTask.due_at < tomorrow_start, WorkspaceTask.kind.in_(("deadline", "hearing"))),
            1,
        ),
        (WorkspaceTask.due_at < tomorrow_start, 2),
        else_=6,
    )
    task_review_rank = sql_case(
        (and_(WorkspaceTask.kind == "deadline", WorkspaceTask.manually_reviewed.is_(False)), 0),
        else_=1,
    )
    task_items = (
        select(
            literal("task").label("source"),
            task_rank.label("priority_rank"),
            task_review_rank.label("review_rank"),
            WorkspaceTask.due_at.label("relevant_at"),
            WorkspaceTask.id.label("item_id"),
            WorkspaceTask.title.label("title"),
            WorkspaceTask.case_id.label("case_id"),
            WorkspaceCase.title.label("case_title"),
            WorkspaceTask.kind.label("task_kind"),
            WorkspaceTask.status.label("status"),
            WorkspaceTask.revision.label("revision"),
            WorkspaceTask.manually_reviewed.label("manually_reviewed"),
            WorkspaceTask.assigned_user_id.label("assigned_user_id"),
            WorkspaceCase.responsible_user_id.label("responsible_user_id"),
            none_text.label("detail"),
        )
        .select_from(WorkspaceTask)
        .outerjoin(
            WorkspaceCase,
            and_(WorkspaceCase.id == WorkspaceTask.case_id, WorkspaceCase.tenant_id == WorkspaceTask.tenant_id),
        )
        .where(
            WorkspaceTask.tenant_id == user.tenant_id,
            or_(WorkspaceTask.case_id.is_(None), case_access_clause(user)),
            open_task,
        )
    )
    publication_items = (
        select(
            literal("publication").label("source"),
            literal(3).label("priority_rank"),
            literal(0).label("review_rank"),
            WorkspacePublication.created_at.label("relevant_at"),
            WorkspacePublication.id.label("item_id"),
            WorkspacePublication.title.label("title"),
            WorkspacePublication.case_id.label("case_id"),
            WorkspaceCase.title.label("case_title"),
            none_text.label("task_kind"),
            literal("unacknowledged").label("status"),
            none_int.label("revision"),
            none_bool.label("manually_reviewed"),
            none_text.label("assigned_user_id"),
            WorkspaceCase.responsible_user_id.label("responsible_user_id"),
            WorkspacePublication.source_kind.label("detail"),
        )
        .join(
            WorkspaceCase,
            and_(WorkspaceCase.id == WorkspacePublication.case_id, WorkspaceCase.tenant_id == WorkspacePublication.tenant_id),
        )
        .where(
            WorkspacePublication.tenant_id == user.tenant_id,
            WorkspacePublication.acknowledged_at.is_(None),
            case_access_clause(user),
        )
    )
    judicial_event_items = (
        select(
            literal("judicial_event").label("source"),
            literal(3).label("priority_rank"),
            literal(0).label("review_rank"),
            ControladoriaJudicialEvent.retrieved_at.label("relevant_at"),
            ControladoriaJudicialEvent.id.label("item_id"),
            ControladoriaJudicialEvent.title.label("title"),
            ControladoriaJudicialEvent.case_id.label("case_id"),
            WorkspaceCase.title.label("case_title"),
            none_text.label("task_kind"),
            ControladoriaJudicialEvent.triage_status.label("status"),
            none_int.label("revision"),
            none_bool.label("manually_reviewed"),
            none_text.label("assigned_user_id"),
            WorkspaceCase.responsible_user_id.label("responsible_user_id"),
            ControladoriaJudicialEvent.source_kind.label("detail"),
        )
        .join(
            WorkspaceCase,
            and_(
                WorkspaceCase.id == ControladoriaJudicialEvent.case_id,
                WorkspaceCase.tenant_id == ControladoriaJudicialEvent.tenant_id,
            ),
        )
        .where(
            ControladoriaJudicialEvent.tenant_id == user.tenant_id,
            ControladoriaJudicialEvent.triage_status == "pending",
            case_access_clause(user),
        )
    )
    communication_items = (
        select(
            literal("communication").label("source"),
            literal(4).label("priority_rank"),
            literal(0).label("review_rank"),
            NotificationDelivery.updated_at.label("relevant_at"),
            CaseMessage.id.label("item_id"),
            literal("Revisar comunicacao nao entregue").label("title"),
            CaseMessage.case_id.label("case_id"),
            WorkspaceCase.title.label("case_title"),
            none_text.label("task_kind"),
            NotificationDelivery.status.label("status"),
            none_int.label("revision"),
            none_bool.label("manually_reviewed"),
            none_text.label("assigned_user_id"),
            WorkspaceCase.responsible_user_id.label("responsible_user_id"),
            NotificationDelivery.error_code.label("detail"),
        )
        .select_from(CaseMessage)
        .join(
            NotificationDelivery,
            and_(
                NotificationDelivery.id == CaseMessage.delivery_id,
                NotificationDelivery.tenant_id == CaseMessage.tenant_id,
            ),
        )
        .join(
            WorkspaceCase,
            and_(WorkspaceCase.id == CaseMessage.case_id, WorkspaceCase.tenant_id == CaseMessage.tenant_id),
        )
        .where(
            CaseMessage.tenant_id == user.tenant_id,
            NotificationDelivery.status.in_(("failed", "unknown")),
            case_access_clause(user),
        )
    )
    open_task_exists = (
        select(WorkspaceTask.id)
        .where(
            WorkspaceTask.tenant_id == WorkspaceCase.tenant_id,
            WorkspaceTask.case_id == WorkspaceCase.id,
            WorkspaceTask.status.in_(("pending", "in_progress")),
        )
        .correlate(WorkspaceCase)
        .exists()
    )
    case_items = select(
        literal("case_without_action").label("source"),
        literal(5).label("priority_rank"),
        literal(0).label("review_rank"),
        WorkspaceCase.updated_at.label("relevant_at"),
        WorkspaceCase.id.label("item_id"),
        literal("Cadastrar proxima acao").label("title"),
        WorkspaceCase.id.label("case_id"),
        WorkspaceCase.title.label("case_title"),
        none_text.label("task_kind"),
        WorkspaceCase.status.label("status"),
        WorkspaceCase.revision.label("revision"),
        none_bool.label("manually_reviewed"),
        none_text.label("assigned_user_id"),
        WorkspaceCase.responsible_user_id.label("responsible_user_id"),
        none_text.label("detail"),
    ).where(
        WorkspaceCase.tenant_id == user.tenant_id,
        WorkspaceCase.status == "open",
        case_access_clause(user),
        ~open_task_exists,
    )
    queue = union_all(task_items, publication_items, judicial_event_items, communication_items, case_items).subquery("daily_priority_queue")
    rows = (
        await db.execute(
            select(queue)
            .order_by(
                queue.c.priority_rank.asc(),
                queue.c.review_rank.asc(),
                queue.c.relevant_at.asc().nullslast(),
                queue.c.item_id.asc(),
            )
            .limit(limit)
        )
    ).mappings().all()
    severity = {0: "critical", 1: "today", 2: "today", 3: "attention", 4: "attention", 5: "planning", 6: "upcoming"}
    destination = {
        "publication": "/dashboard/tracker",
        "judicial_event": "/dashboard/controladoria",
        "communication": "/dashboard/communications",
        "case_without_action": "/dashboard/tracker",
    }
    items = []
    for row in rows:
        item = dict(row)
        item["id"] = item.pop("item_id")
        item["severity"] = severity[item.pop("priority_rank")]
        item.pop("review_rank")
        item["href"] = (
            f"/dashboard/cases/{item['case_id']}"
            if item["case_id"]
            else destination.get(item["source"], "/dashboard/tasks")
        )
        if item["source"] in {"communication", "judicial_event"}:
            item["href"] = destination[item["source"]]
        item["actions"] = priority_actions(item, user)
        item.pop("assigned_user_id")
        item.pop("responsible_user_id")
        items.append(item)
    return items


async def daily_attention_counts(db: AsyncSession, user: User) -> dict[str, int | None]:
    pending_judicial_movements = await db.scalar(
        select(func.count(ControladoriaJudicialEvent.id))
        .join(
            WorkspaceCase,
            and_(
                WorkspaceCase.id == ControladoriaJudicialEvent.case_id,
                WorkspaceCase.tenant_id == ControladoriaJudicialEvent.tenant_id,
            ),
        )
        .where(
            ControladoriaJudicialEvent.tenant_id == user.tenant_id,
            ControladoriaJudicialEvent.triage_status == "pending",
            case_access_clause(user),
        )
    )
    communication_failures = await db.scalar(
        select(func.count(CaseMessage.id))
        .join(
            NotificationDelivery,
            and_(NotificationDelivery.id == CaseMessage.delivery_id, NotificationDelivery.tenant_id == CaseMessage.tenant_id),
        )
        .join(
            WorkspaceCase,
            and_(WorkspaceCase.id == CaseMessage.case_id, WorkspaceCase.tenant_id == CaseMessage.tenant_id),
        )
        .where(
            CaseMessage.tenant_id == user.tenant_id,
            NotificationDelivery.status.in_(("failed", "unknown")),
            case_access_clause(user),
        )
    )
    document_failures = await db.scalar(
        select(func.count(WorkspaceDocumentUpload.id))
        .outerjoin(
            WorkspaceCase,
            and_(WorkspaceCase.id == WorkspaceDocumentUpload.case_id, WorkspaceCase.tenant_id == WorkspaceDocumentUpload.tenant_id),
        )
        .where(
            WorkspaceDocumentUpload.tenant_id == user.tenant_id,
            WorkspaceDocumentUpload.status == "failed",
            or_(WorkspaceDocumentUpload.case_id.is_(None), case_access_clause(user)),
        )
    )
    financial_drafts = None
    if user.role in FINANCE_ROLES:
        financial_drafts = await db.scalar(
            select(func.count(WorkspaceLedgerEntry.id)).where(
                WorkspaceLedgerEntry.tenant_id == user.tenant_id,
                WorkspaceLedgerEntry.status == "draft",
            )
        )
    return {
        "pending_judicial_movements": int(pending_judicial_movements or 0),
        "communication_failures": int(communication_failures or 0),
        "document_failures": int(document_failures or 0),
        "financial_drafts": int(financial_drafts or 0) if financial_drafts is not None else None,
    }


async def fee_summary(db: AsyncSession, user: User) -> dict:
    if user.role not in FINANCE_ROLES:
        return None
    posted = await db.scalar(
        select(func.coalesce(func.sum(WorkspaceLedgerEntry.amount), Decimal("0.00"))).where(
            WorkspaceLedgerEntry.tenant_id == user.tenant_id,
            WorkspaceLedgerEntry.entry_type == "fee",
            WorkspaceLedgerEntry.status == "posted",
        )
    )
    pending = await db.scalar(
        select(func.coalesce(func.sum(WorkspaceLedgerEntry.amount), Decimal("0.00"))).where(
            WorkspaceLedgerEntry.tenant_id == user.tenant_id,
            WorkspaceLedgerEntry.entry_type == "fee",
            WorkspaceLedgerEntry.status == "draft",
        )
    )
    return {"currency": "BRL", "posted_amount": posted, "pending_amount": pending}


@router.get("/summary")
async def daily_summary(*, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    tenant = await db.get(Tenant, current_user.tenant_id)
    timezone_name = tenant.timezone if tenant else "America/Sao_Paulo"
    office_tz, utc_now, tomorrow_start = daily_time_context(timezone_name)
    clients_by_stage = await grouped_counts(
        db,
        select(WorkspaceClient).where(WorkspaceClient.tenant_id == current_user.tenant_id),
        WorkspaceClient.stage,
    )
    cases_by_status = await grouped_counts(db, authorized_case_query(current_user), WorkspaceCase.status)
    tasks = await task_counts(db, current_user, now=utc_now, timezone_name=timezone_name)
    open_task_exists = (
        select(WorkspaceTask.id)
        .where(
            WorkspaceTask.tenant_id == WorkspaceCase.tenant_id,
            WorkspaceTask.case_id == WorkspaceCase.id,
            WorkspaceTask.status.in_(("pending", "in_progress")),
        )
        .correlate(WorkspaceCase)
        .exists()
    )
    waiting_action = await db.scalar(
        authorized_case_query(current_user)
        .with_only_columns(func.count(WorkspaceCase.id), maintain_column_froms=True)
        .where(WorkspaceCase.status == "open", ~open_task_exists)
    )
    return {
        "generated_at": utc_now,
        "timezone": office_tz.key,
        "clients": {"total": sum(clients_by_stage.values()), "leads": clients_by_stage.get("lead", 0), "active": clients_by_stage.get("client", 0)},
        "cases": {"total": sum(cases_by_status.values()), "active": cases_by_status.get("open", 0), "waiting_action": int(waiting_action or 0), "restricted": await db.scalar(authorized_case_query(current_user).with_only_columns(func.count()).where(WorkspaceCase.restricted.is_(True))) or 0},
        "tasks": {key: tasks[key] for key in ("due_today", "overdue", "upcoming", "hearings_upcoming")},
        "priorities": await daily_priority_items(db, current_user, now=utc_now, tomorrow_start=tomorrow_start),
        "attention": await daily_attention_counts(db, current_user),
        "financial": await fee_summary(db, current_user),
    }


@router.get("/analytics")
async def workspace_analytics(*, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    clients_by_stage = await grouped_counts(
        db,
        select(WorkspaceClient).where(WorkspaceClient.tenant_id == current_user.tenant_id),
        WorkspaceClient.stage,
    )
    cases_by_status = await grouped_counts(db, authorized_case_query(current_user), WorkspaceCase.status)
    task_statement = await authorized_task_statement(current_user)
    task_records = (await db.execute(task_statement)).scalars().all()
    tenant = await db.get(Tenant, current_user.tenant_id)
    office_tz = ZoneInfo(tenant.timezone if tenant else "America/Sao_Paulo")
    today = datetime.now(timezone.utc).astimezone(office_tz).date()
    workload = {str(today + timedelta(days=offset)): 0 for offset in range(7)}
    for task in task_records:
        if task.due_at and task.status not in {"completed", "cancelled"}:
            day = str(task.due_at.astimezone(office_tz).date())
            if day in workload:
                workload[day] += 1
    return {
        "clients_by_stage": {stage: clients_by_stage.get(stage, 0) for stage in ("lead", "prospect", "client", "inactive")},
        "cases_by_status": {state: cases_by_status.get(state, 0) for state in ("open", "paused", "closed", "archived")},
        "tasks": await task_counts(db, current_user, timezone_name=office_tz.key),
        "workload_next_7_days": workload,
        "fees": await fee_summary(db, current_user),
    }


@router.get("/activity")
async def workspace_activity(*, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    clients = (await db.execute(select(WorkspaceClient).where(WorkspaceClient.tenant_id == current_user.tenant_id).order_by(WorkspaceClient.updated_at.desc()).limit(5))).scalars().all()
    cases = (await db.execute(authorized_case_query(current_user).order_by(WorkspaceCase.updated_at.desc()).limit(5))).scalars().all()
    tasks = (await db.execute((await authorized_task_statement(current_user)).order_by(WorkspaceTask.updated_at.desc()).limit(5))).scalars().all()
    items = [
        *({"id": row.id, "message": f"O cadastro de {row.name} foi atualizado.", "area": "Cliente", "created_at": row.updated_at, "href": "/dashboard/crm"} for row in clients),
        *({"id": row.id, "message": f"O processo {row.title} foi atualizado.", "area": "Processo", "created_at": row.updated_at, "href": f"/dashboard/cases/{row.id}"} for row in cases),
        *({"id": row.id, "message": f"O compromisso {row.title} foi atualizado.", "area": "Agenda", "created_at": row.updated_at, "href": "/dashboard/tasks"} for row in tasks),
    ]
    return {"items": sorted(items, key=lambda item: item["created_at"], reverse=True)[:8]}


EXPORT_PAGE_SIZE = 5


async def export_records(db: AsyncSession, statement, model, serializer):
    after_id = None
    first = True
    while True:
        page = statement
        if after_id:
            page = page.where(model.id > after_id)
        records = (await db.execute(page.order_by(model.id).limit(EXPORT_PAGE_SIZE))).scalars().all()
        if not records:
            return
        for record in records:
            if not first:
                yield ","
            first = False
            yield json.dumps(jsonable_encoder(serializer(record)), ensure_ascii=False, separators=(",", ":"))
        after_id = records[-1].id


def export_document_version(record: WorkspaceDocumentVersion) -> dict:
    payload = DocumentVersionResponse.model_validate(record).model_dump(mode="json")
    payload["file_content_base64"] = (
        base64.b64encode(record.file_content).decode("ascii") if record.file_content else None
    )
    return payload


@router.get("/export")
async def export_workspace(*, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    require_role(current_user, ADMIN_ROLES)
    tenant = await db.scalar(select(Tenant).where(Tenant.id == current_user.tenant_id))
    if not tenant:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessao invalida ou expirada.")
    tasks_statement = await authorized_task_statement(current_user)
    collections = (
        ("clients", select(WorkspaceClient).where(WorkspaceClient.tenant_id == current_user.tenant_id), WorkspaceClient, ClientResponse.model_validate),
        ("cases", authorized_case_query(current_user), WorkspaceCase, CaseResponse.model_validate),
        ("parties", select(WorkspaceCaseParty).where(WorkspaceCaseParty.tenant_id == current_user.tenant_id), WorkspaceCaseParty, CasePartyResponse.model_validate),
        ("tasks", tasks_statement, WorkspaceTask, TaskResponse.model_validate),
        ("documents", document_scope(current_user), WorkspaceDocument, DocumentResponse.model_validate),
        ("document_versions", select(WorkspaceDocumentVersion).where(WorkspaceDocumentVersion.tenant_id == current_user.tenant_id), WorkspaceDocumentVersion, export_document_version),
        ("document_reviews", select(WorkspaceDocumentReview).where(WorkspaceDocumentReview.tenant_id == current_user.tenant_id), WorkspaceDocumentReview, lambda record: {"id": record.id, "document_id": record.document_id, "version": record.version, "status": record.status, "comment": record.comment, "created_by_user_id": record.created_by_user_id, "created_at": record.created_at}),
        ("library", select(WorkspaceLibraryEntry).where(WorkspaceLibraryEntry.tenant_id == current_user.tenant_id), WorkspaceLibraryEntry, LibraryEntryResponse.model_validate),
        ("publications", select(WorkspacePublication).where(WorkspacePublication.tenant_id == current_user.tenant_id), WorkspacePublication, PublicationResponse.model_validate),
        ("ledger", select(WorkspaceLedgerEntry).where(WorkspaceLedgerEntry.tenant_id == current_user.tenant_id), WorkspaceLedgerEntry, LedgerEntryResponse.model_validate),
        ("case_messages", select(CaseMessage).where(CaseMessage.tenant_id == current_user.tenant_id), CaseMessage, lambda record: {"id": record.id, "case_id": record.case_id, "client_id": record.client_id, "channel": record.channel, "direction": record.direction, "body": record.body, "created_by_user_id": record.created_by_user_id, "read_at": record.read_at, "created_at": record.created_at}),
        ("communication_inbox", select(CommunicationInboxItem).where(CommunicationInboxItem.tenant_id == current_user.tenant_id), CommunicationInboxItem, lambda record: {"id": record.id, "channel": record.channel, "provider": record.provider, "sender_address": record.sender_address, "subject": record.subject, "body": record.body, "body_truncated": record.body_truncated, "has_attachments": record.has_attachments, "status": record.status, "matched_client_id": record.matched_client_id, "linked_case_id": record.linked_case_id, "linked_message_id": record.linked_message_id, "reviewed_by_user_id": record.reviewed_by_user_id, "reviewed_at": record.reviewed_at, "received_at": record.received_at, "created_at": record.created_at}),
        ("privacy_requests", select(PrivacyRequest).where(PrivacyRequest.tenant_id == current_user.tenant_id), PrivacyRequest, lambda record: {"id": record.id, "requested_by_user_id": record.requested_by_user_id, "request_type": record.request_type, "scope": record.scope, "status": record.status, "reason": record.reason, "resolution_note": record.resolution_note, "created_at": record.created_at, "resolved_at": record.resolved_at}),
    )

    async def stream_export():
        header = {
            "schema_version": 2,
            "generated_at": datetime.now(timezone.utc),
            "export_kind": "portable_data_export",
            "not_a_backup": True,
            "consistency": "live_read",
            "attachments_embedded_as_base64": True,
            "privacy_policy": {
                "notice_url": tenant.privacy_notice_url,
                "notice_version": tenant.privacy_notice_version,
                "contact": tenant.privacy_contact,
                "retention_days": tenant.data_retention_days,
            },
        }
        encoded_header = json.dumps(jsonable_encoder(header), ensure_ascii=False, separators=(",", ":"))
        yield encoded_header[:-1]
        for name, statement, model, serializer in collections:
            yield f',"{name}":['
            async for chunk in export_records(db, statement, model, serializer):
                yield chunk
            yield "]"
        yield "}"

    return StreamingResponse(
        stream_export(),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=workspace-export.json", "Cache-Control": "private, no-store"},
    )
