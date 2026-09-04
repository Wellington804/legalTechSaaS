"""Tenant-scoped commercial operations and separately authenticated webhooks."""

import asyncio
from datetime import datetime, timezone
from urllib.parse import quote

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse, Response
from pydantic import ValidationError
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, _set_tenant_context, require_tenant_write
from app.core.request_body import read_limited_body
from app.models.operations import FeeContract, FeeRule, Invoice, ProviderCredential, PublicIntake, PublicIntakeConfig, Receivable, SignatureEnvelope, TimeEntry
from app.models.user import User
from app.models.workspace import WorkspaceCase, WorkspaceDocument
from app.schemas.operations import (
    ExpectedRevision,
    FeeContractCreate,
    FeeContractResponse,
    FeeContractUpdate,
    FeeRuleCreate,
    FeeRuleResponse,
    IntakeConversion,
    IntakeConversionResponse,
    InvoiceCreate,
    InvoiceResponse,
    PaymentReceiptResponse,
    PaymentWebhookEvent,
    ProviderCredentialResponse,
    ProviderCredentialUpsert,
    PublicIntakeConfigResponse,
    PublicIntakeConfigUpsert,
    PublicIntakeFormResponse,
    PublicIntakeReceived,
    PublicIntakeResponse,
    PublicIntakeSubmit,
    ReceivableResponse,
    SignatureEnvelopeCreate,
    SignatureEnvelopeResponse,
    SignatureWebhookEvent,
    TimeEntryCreate,
    TimeEntryResponse,
    TimeEntryUpdate,
    clean_provider,
)
from app.services.audit_service import AuditService
from app.services.operations import (
    SUPPORTED_SIGNATURE_PROVIDERS,
    apply_clicksign_event,
    apply_payment_event,
    apply_signature_event,
    convert_intake,
    create_fee_contract,
    create_invoice,
    create_or_get_public_intake,
    create_signature_envelope,
    create_time_entry,
    dispatch_signature_envelope,
    digest,
    enforce_public_intake_rate_limit,
    get_fee_contract,
    get_fee_rule,
    get_invoice,
    get_signature_envelope,
    resolve_public_intake_config,
    resolve_webhook_identity,
    queue_autentique_event,
    upsert_provider_credential,
    verify_hmac_webhook,
)
from app.services.clicksign_provider import CLICKSIGN_BASE_URLS, ClicksignSigner, parse_clicksign_webhook
from app.services.autentique_provider import AUTENTIQUE_PROVIDERS, AutentiqueSigner, parse_autentique_webhook
from app.services.document_storage import create_download_url
from app.services.provider_costs import record_provider_usage
from app.services.workspace_service import ADMIN_ROLES, FINANCE_ROLES, bounded_limit, case_access_clause, get_case, require_case_write, require_role


router = APIRouter()
public_router = APIRouter()
MAX_WEBHOOK_BYTES = 256 * 1024


def _protected_user(user: CurrentUser) -> User:
    return user


async def audit(
    db: AsyncSession,
    request: Request,
    tenant_id: str,
    user_id: str | None,
    action: str,
    resource_type: str,
    resource_id: str,
    details: dict | None = None,
) -> None:
    await AuditService.log_action(
        db,
        tenant_id,
        user_id,
        action,
        resource_type,
        resource_id,
        details or {},
        request.client.host if request.client else None,
        (request.headers.get("user-agent") or "")[:512] or None,
    )


def credential_response(record: ProviderCredential) -> ProviderCredentialResponse:
    return ProviderCredentialResponse(
        id=record.id,
        purpose=record.purpose,
        provider=record.provider,
        account_reference=record.account_reference,
        enabled=record.enabled,
        api_token_configured=bool(record.api_token_encrypted),
        revision=record.revision,
        updated_at=record.updated_at,
    )


async def current_config(db: AsyncSession, tenant_id: str, *, lock: bool = False) -> PublicIntakeConfig | None:
    statement = select(PublicIntakeConfig).where(PublicIntakeConfig.tenant_id == tenant_id)
    if lock:
        statement = statement.with_for_update()
    return await db.scalar(statement)


def assert_intake_origin(request: Request, config: PublicIntakeConfig) -> None:
    origin = request.headers.get("Origin")
    if config.allowed_origin and origin and origin.rstrip("/") != config.allowed_origin.rstrip("/"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Origem não autorizada.")


@public_router.get("/intake", response_model=PublicIntakeFormResponse)
async def public_intake_form(
    x_intake_token: str = Header(alias="X-Intake-Token", min_length=32, max_length=512),
    db: AsyncSession = Depends(get_db),
):
    config = await resolve_public_intake_config(db, x_intake_token)
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Formulário não encontrado.")
    return PublicIntakeFormResponse(
        form_title=config.form_title,
        notice_version=config.notice_version,
        consent_version=config.consent_version,
        notice_url=config.notice_url,
    )


@public_router.post("/intake", response_model=PublicIntakeReceived, status_code=status.HTTP_202_ACCEPTED)
async def submit_public_intake(
    body: PublicIntakeSubmit,
    request: Request,
    x_intake_token: str = Header(alias="X-Intake-Token", min_length=32, max_length=512),
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=128),
    db: AsyncSession = Depends(get_db),
):
    config = await resolve_public_intake_config(db, x_intake_token)
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Formulário não encontrado.")
    assert_intake_origin(request, config)
    await enforce_public_intake_rate_limit(request, config)
    record, existing = await create_or_get_public_intake(db, config, body, idempotency_key)
    await audit(db, request, config.tenant_id, None, "PUBLIC_INTAKE_RECEIVED", "public_intakes", record.id, {"existing": existing})
    await db.commit()
    return PublicIntakeReceived(intake_id=record.id, existing=existing)


@router.get("/intake-config", response_model=PublicIntakeConfigResponse)
async def get_intake_config(user: CurrentUser, db: AsyncSession = Depends(get_db)):
    require_role(user, ADMIN_ROLES)
    config = await current_config(db, user.tenant_id)
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Formulário público não configurado.")
    return PublicIntakeConfigResponse.model_validate(config)


@router.put("/intake-config", response_model=PublicIntakeConfigResponse)
async def put_intake_config(
    body: PublicIntakeConfigUpsert,
    request: Request,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    require_role(user, ADMIN_ROLES)
    config = await current_config(db, user.tenant_id, lock=True)
    if config:
        if body.expected_revision != config.revision:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Configuração foi alterada por outra sessão.")
        if body.public_token:
            config.token_hash = digest(body.public_token)
        config.enabled = body.enabled
        config.form_title = body.form_title
        config.notice_version = body.notice_version
        config.consent_version = body.consent_version
        config.notice_url = body.notice_url
        config.allowed_origin = body.allowed_origin
        config.revision += 1
    else:
        if not body.public_token:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="public_token é obrigatório na primeira configuração.")
        if body.expected_revision is not None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="expected_revision não é usado na primeira configuração.")
        config = PublicIntakeConfig(
            tenant_id=user.tenant_id,
            token_hash=digest(body.public_token),
            enabled=body.enabled,
            form_title=body.form_title,
            notice_version=body.notice_version,
            consent_version=body.consent_version,
            notice_url=body.notice_url,
            allowed_origin=body.allowed_origin,
        )
        db.add(config)
        await db.flush()
    await audit(db, request, user.tenant_id, user.id, "PUBLIC_INTAKE_CONFIGURED", "public_intake_configs", config.id)
    await db.commit()
    return PublicIntakeConfigResponse.model_validate(config)


@router.get("/intakes", response_model=dict)
async def list_intakes(
    status_value: str | None = Query(default=None, alias="status", pattern="^(new|converted|archived)$"),
    limit: int = Query(default=50, ge=1, le=200),
    *,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    require_role(user, FINANCE_ROLES | {"lawyer"})
    statement = select(PublicIntake).where(PublicIntake.tenant_id == user.tenant_id)
    if status_value:
        statement = statement.where(PublicIntake.status == status_value)
    records = (await db.execute(statement.order_by(PublicIntake.created_at.desc()).limit(bounded_limit(limit)))).scalars().all()
    return {"items": [PublicIntakeResponse.model_validate(record) for record in records], "limit": bounded_limit(limit)}


@router.post("/intakes/{intake_id}/convert", response_model=IntakeConversionResponse)
async def convert_public_intake(
    intake_id: str,
    body: IntakeConversion,
    request: Request,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    require_role(user, FINANCE_ROLES | {"lawyer"})
    intake, client, case, existing = await convert_intake(
        db,
        user,
        intake_id,
        expected_revision=body.expected_revision,
        existing_client_id=body.existing_client_id,
        case_title=body.case_title,
        responsible_user_id=body.responsible_user_id,
        restricted=body.restricted,
    )
    await audit(
        db,
        request,
        user.tenant_id,
        user.id,
        "PUBLIC_INTAKE_CONVERTED",
        "public_intakes",
        intake.id,
        {"client_id": client.id, "case_id": case.id, "client_reused": existing},
    )
    await db.commit()
    return IntakeConversionResponse(intake_id=intake.id, client_id=client.id, case_id=case.id, existing=existing)


@router.post("/fee-contracts", response_model=FeeContractResponse, status_code=status.HTTP_201_CREATED)
async def create_fee_contract_endpoint(
    body: FeeContractCreate,
    request: Request,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    require_role(user, FINANCE_ROLES)
    record = await create_fee_contract(db, user, body)
    await audit(db, request, user.tenant_id, user.id, "FEE_CONTRACT_CREATED", "fee_contracts", record.id)
    await db.commit()
    return FeeContractResponse.model_validate(record)


@router.get("/fee-contracts", response_model=dict)
async def list_fee_contracts(
    case_id: str | None = Query(default=None, max_length=64),
    client_id: str | None = Query(default=None, max_length=64),
    limit: int = Query(default=50, ge=1, le=200),
    *,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    require_role(user, FINANCE_ROLES)
    statement = select(FeeContract).where(FeeContract.tenant_id == user.tenant_id)
    if case_id:
        await get_case(db, user, case_id)
        statement = statement.where(FeeContract.case_id == case_id)
    if client_id:
        statement = statement.where(FeeContract.client_id == client_id)
    records = (await db.scalars(statement.order_by(FeeContract.created_at.desc()).limit(bounded_limit(limit)))).all()
    return {"items": [FeeContractResponse.model_validate(record) for record in records], "limit": bounded_limit(limit)}


@router.put("/fee-contracts/{contract_id}", response_model=FeeContractResponse)
async def update_fee_contract(
    contract_id: str,
    body: FeeContractUpdate,
    request: Request,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    require_role(user, FINANCE_ROLES)
    record = await get_fee_contract(db, user, contract_id, for_update=True)
    if record.revision != body.expected_revision:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Contrato foi alterado por outra sessão.")
    allowed = {"draft": {"active", "void"}, "active": {"closed", "void"}}
    if body.status == record.status:
        return FeeContractResponse.model_validate(record)
    if body.status not in allowed.get(record.status, set()):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Transição de contrato inválida.")
    record.status = body.status
    record.revision += 1
    await audit(db, request, user.tenant_id, user.id, "FEE_CONTRACT_STATUS_CHANGED", "fee_contracts", record.id, {"status": record.status})
    await db.commit()
    return FeeContractResponse.model_validate(record)


@router.post("/fee-contracts/{contract_id}/rules", response_model=FeeRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_fee_rule(
    contract_id: str,
    body: FeeRuleCreate,
    request: Request,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    require_role(user, FINANCE_ROLES)
    contract = await get_fee_contract(db, user, contract_id, for_update=True)
    if contract.status != "draft":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Regras só podem ser alteradas no rascunho.")
    rule = FeeRule(tenant_id=user.tenant_id, fee_contract_id=contract.id, **body.model_dump())
    db.add(rule)
    await db.flush()
    contract.revision += 1
    await audit(db, request, user.tenant_id, user.id, "FEE_RULE_CREATED", "fee_rules", rule.id, {"contract_id": contract.id})
    await db.commit()
    return FeeRuleResponse.model_validate(rule)


@router.post("/time-entries", response_model=TimeEntryResponse, status_code=status.HTTP_201_CREATED)
async def create_time_entry_endpoint(
    body: TimeEntryCreate,
    request: Request,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    require_role(user, FINANCE_ROLES | {"lawyer"})
    record = await create_time_entry(db, user, body)
    await audit(db, request, user.tenant_id, user.id, "TIME_ENTRY_CREATED", "time_entries", record.id, {"amount": str(record.amount)})
    await db.commit()
    return TimeEntryResponse.model_validate(record)


@router.get("/time-entries", response_model=dict)
async def list_time_entries(
    case_id: str | None = Query(default=None, max_length=64),
    limit: int = Query(default=50, ge=1, le=200),
    *,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    require_role(user, FINANCE_ROLES | {"lawyer"})
    statement = (
        select(TimeEntry)
        .join(WorkspaceCase, and_(WorkspaceCase.id == TimeEntry.case_id, WorkspaceCase.tenant_id == TimeEntry.tenant_id))
        .where(TimeEntry.tenant_id == user.tenant_id, case_access_clause(user))
    )
    if case_id:
        await get_case(db, user, case_id)
        statement = statement.where(TimeEntry.case_id == case_id)
    records = (await db.scalars(statement.order_by(TimeEntry.occurred_at.desc()).limit(bounded_limit(limit)))).all()
    return {"items": [TimeEntryResponse.model_validate(record) for record in records], "limit": bounded_limit(limit)}


@router.put("/time-entries/{entry_id}", response_model=TimeEntryResponse)
async def update_time_entry(
    entry_id: str,
    body: TimeEntryUpdate,
    request: Request,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    require_role(user, FINANCE_ROLES | {"lawyer"})
    record = await db.scalar(select(TimeEntry).where(TimeEntry.tenant_id == user.tenant_id, TimeEntry.id == entry_id).with_for_update())
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Apontamento não encontrado.")
    require_case_write(user, await get_case(db, user, record.case_id))
    if record.revision != body.expected_revision:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Apontamento foi alterado por outra sessão.")
    transitions = {"draft": {"approved", "void"}, "approved": {"void"}}
    if body.status not in transitions.get(record.status, set()):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Transição de apontamento inválida.")
    record.status = body.status
    record.revision += 1
    await audit(db, request, user.tenant_id, user.id, "TIME_ENTRY_STATUS_CHANGED", "time_entries", record.id, {"status": record.status})
    await db.commit()
    return TimeEntryResponse.model_validate(record)


@router.post("/invoices", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
async def create_invoice_endpoint(
    body: InvoiceCreate,
    request: Request,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    require_role(user, FINANCE_ROLES)
    invoice, receivables = await create_invoice(db, user, body)
    await audit(db, request, user.tenant_id, user.id, "INVOICE_CREATED", "invoices", invoice.id, {"installments": len(receivables)})
    await db.commit()
    return InvoiceResponse.model_validate(invoice)


@router.get("/invoices", response_model=dict)
async def list_invoices(
    status_value: str | None = Query(default=None, alias="status", pattern="^(draft|issued|partially_paid|paid|void|overdue)$"),
    limit: int = Query(default=50, ge=1, le=200),
    *,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    require_role(user, FINANCE_ROLES)
    statement = select(Invoice).where(Invoice.tenant_id == user.tenant_id)
    if status_value:
        statement = statement.where(Invoice.status == status_value)
    records = (await db.scalars(statement.order_by(Invoice.created_at.desc()).limit(bounded_limit(limit)))).all()
    return {"items": [InvoiceResponse.model_validate(record) for record in records], "limit": bounded_limit(limit)}


@router.get("/invoices/{invoice_id}", response_model=dict)
async def get_invoice_detail(invoice_id: str, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    require_role(user, FINANCE_ROLES)
    invoice = await get_invoice(db, user.tenant_id, invoice_id)
    receivables = (
        await db.execute(
            select(Receivable)
            .where(Receivable.tenant_id == user.tenant_id, Receivable.invoice_id == invoice.id)
            .order_by(Receivable.sequence)
        )
    ).scalars().all()
    return {"invoice": InvoiceResponse.model_validate(invoice), "receivables": [ReceivableResponse.model_validate(item) for item in receivables]}


@router.post("/invoices/{invoice_id}/issue", response_model=InvoiceResponse)
async def issue_invoice(
    invoice_id: str,
    body: ExpectedRevision,
    request: Request,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    require_role(user, FINANCE_ROLES)
    invoice = await get_invoice(db, user.tenant_id, invoice_id, for_update=True)
    if invoice.revision != body.expected_revision:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Fatura foi alterada por outra sessão.")
    if invoice.status != "draft":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Fatura já foi processada.")
    invoice.status = "issued"
    invoice.issued_at = datetime.now(timezone.utc)
    invoice.revision += 1
    await audit(db, request, user.tenant_id, user.id, "INVOICE_ISSUED", "invoices", invoice.id)
    await db.commit()
    return InvoiceResponse.model_validate(invoice)


@router.put("/provider-credentials/{purpose}/{provider}", response_model=ProviderCredentialResponse)
async def put_provider_credential(
    purpose: str,
    provider: str,
    body: ProviderCredentialUpsert,
    request: Request,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    require_role(user, ADMIN_ROLES)
    if purpose not in {"signature", "payment"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Finalidade de provedor inválida.")
    try:
        provider = clean_provider(provider)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Provedor inválido.") from exc
    if purpose == "signature" and provider not in SUPPORTED_SIGNATURE_PROVIDERS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Provedor de assinatura ainda não homologado.")
    if provider in AUTENTIQUE_PROVIDERS and not body.account_reference.isdecimal():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Informe o ID numérico da organização Autentique.")
    record = await upsert_provider_credential(db, user, purpose=purpose, provider=provider, body=body)
    await audit(db, request, user.tenant_id, user.id, "OPERATION_PROVIDER_CREDENTIAL_CONFIGURED", "operation_provider_credentials", record.id, {"purpose": purpose, "provider": provider})
    await db.commit()
    return credential_response(record)


@router.get("/provider-credentials", response_model=dict)
async def list_provider_credentials(user: CurrentUser, db: AsyncSession = Depends(get_db)):
    require_role(user, ADMIN_ROLES)
    records = (await db.scalars(
        select(ProviderCredential)
        .where(ProviderCredential.tenant_id == user.tenant_id)
        .order_by(ProviderCredential.purpose, ProviderCredential.provider)
    )).all()
    return {"items": [credential_response(record) for record in records]}


@router.get("/signature-providers", response_model=dict)
async def list_signature_providers(user: CurrentUser, db: AsyncSession = Depends(get_db)):
    require_role(user, FINANCE_ROLES | {"lawyer"})
    records = (await db.scalars(
        select(ProviderCredential)
        .where(
            ProviderCredential.tenant_id == user.tenant_id,
            ProviderCredential.purpose == "signature",
            ProviderCredential.enabled.is_(True),
            ProviderCredential.api_token_encrypted.is_not(None),
            ProviderCredential.provider.in_(tuple(SUPPORTED_SIGNATURE_PROVIDERS)),
        )
        .order_by(ProviderCredential.provider, ProviderCredential.account_reference)
    )).all()
    return {"items": [{"provider": record.provider, "account_reference": record.account_reference} for record in records]}


@router.get("/signature-envelopes", response_model=dict)
async def list_signature_envelopes(
    user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    require_role(user, FINANCE_ROLES | {"lawyer"})
    rows = (
        await db.scalars(
            select(SignatureEnvelope)
            .join(
                WorkspaceDocument,
                and_(
                    WorkspaceDocument.tenant_id == SignatureEnvelope.tenant_id,
                    WorkspaceDocument.id == SignatureEnvelope.document_id,
                ),
            )
            .outerjoin(
                WorkspaceCase,
                and_(
                    WorkspaceCase.tenant_id == WorkspaceDocument.tenant_id,
                    WorkspaceCase.id == WorkspaceDocument.case_id,
                ),
            )
            .where(
                SignatureEnvelope.tenant_id == user.tenant_id,
                (WorkspaceDocument.case_id.is_(None) | case_access_clause(user)),
            )
            .order_by(SignatureEnvelope.created_at.desc())
            .limit(limit)
        )
    ).all()
    return {"items": [SignatureEnvelopeResponse.model_validate(row) for row in rows], "limit": limit}


@router.post("/signature-envelopes", response_model=SignatureEnvelopeResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_signature_envelope_endpoint(
    body: SignatureEnvelopeCreate,
    request: Request,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    _write: User = Depends(require_tenant_write),
):
    require_role(user, FINANCE_ROLES | {"lawyer"})
    signer_type = AutentiqueSigner if body.provider in AUTENTIQUE_PROVIDERS else ClicksignSigner
    signer = signer_type(name=body.signer_name, email=str(body.signer_email), cpf=body.signer_cpf, authentication=body.authentication)
    envelope, material, credential, duplicate = await create_signature_envelope(
        db,
        user,
        request_key=body.request_key,
        document_id=body.document_id,
        document_version=body.document_version,
        provider=body.provider,
        account_reference=body.account_reference,
        signer=signer,
        expires_at=body.expires_at,
    )
    if duplicate:
        return SignatureEnvelopeResponse.model_validate(envelope)
    await audit(
        db,
        request,
        user.tenant_id,
        user.id,
        "SIGNATURE_ENVELOPE_SNAPSHOTTED",
        "signature_envelopes",
        envelope.id,
        {"document_id": envelope.document_id, "document_version": envelope.document_version, "document_hash": envelope.document_hash},
    )
    await db.commit()
    if material is None or credential is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Snapshot de assinatura indisponível.")
    dispatch_error = await dispatch_signature_envelope(envelope, credential, material, signer)
    await _set_tenant_context(db, user.tenant_id)
    if dispatch_error is None:
        await record_provider_usage(
            db,
            tenant_id=user.tenant_id,
            provider=envelope.provider,
            metric="document_created",
            idempotency_key=f"envelope:{envelope.id}",
            envelope_id=envelope.id,
        )
        await record_provider_usage(
            db,
            tenant_id=user.tenant_id,
            provider=envelope.provider,
            metric="signature_request_email",
            idempotency_key=f"email:{envelope.id}",
            envelope_id=envelope.id,
        )
    await audit(
        db,
        request,
        user.tenant_id,
        user.id,
        "SIGNATURE_ENVELOPE_DISPATCHED" if dispatch_error is None else "SIGNATURE_ENVELOPE_DISPATCH_FAILED",
        "signature_envelopes",
        envelope.id,
        {"provider": envelope.provider, "dispatch_status": envelope.dispatch_status},
    )
    await db.commit()
    if dispatch_error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(dispatch_error))
    return SignatureEnvelopeResponse.model_validate(envelope)


@router.get("/signature-envelopes/{envelope_id}/download")
async def download_signed_envelope(
    envelope_id: str,
    request: Request,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    require_role(user, FINANCE_ROLES | {"lawyer"})
    envelope = await get_signature_envelope(db, user, envelope_id)
    if not envelope.signed_file_available:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Documento assinado ainda não está disponível.")
    filename = envelope.signed_filename or f"documento-assinado-{envelope.provider}.pdf"
    await audit(db, request, user.tenant_id, user.id, "SIGNED_DOCUMENT_DOWNLOADED", "signature_envelopes", envelope.id, {"sha256": envelope.signed_file_hash})
    await db.commit()
    if envelope.signed_object_key:
        url = await asyncio.to_thread(create_download_url, envelope.signed_object_key, filename, "application/pdf")
        return RedirectResponse(url, status_code=307, headers={"Cache-Control": "private, no-store", "Referrer-Policy": "no-referrer"})
    if envelope.signed_file_content is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Arquivo assinado não encontrado.")
    return Response(
        content=envelope.signed_file_content,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}", "Cache-Control": "private, no-store"},
    )


async def webhook_identity_or_401(
    db: AsyncSession,
    raw: bytes,
    signature: str | None,
    *,
    purpose: str,
    provider: str,
    account_reference: str,
):
    try:
        provider = clean_provider(provider)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook não encontrado.") from exc
    identity = await resolve_webhook_identity(db, purpose=purpose, provider=provider, account_reference=account_reference)
    if not identity or not verify_hmac_webhook(raw, signature, identity.credential.webhook_secret_encrypted):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Assinatura de webhook inválida.")
    return identity


@public_router.post("/webhooks/signatures/{provider}", status_code=status.HTTP_200_OK)
async def signature_webhook(
    provider: str,
    request: Request,
    x_operation_account: str | None = Header(default=None, alias="X-Operation-Account", min_length=2, max_length=128),
    x_operation_signature: str | None = Header(default=None, alias="X-Operation-Signature", max_length=256),
    content_hmac: str | None = Header(default=None, alias="Content-Hmac", max_length=256),
    x_clicksign_signature: str | None = Header(default=None, alias="X-Clicksign-Signature", max_length=256),
    x_autentique_signature: str | None = Header(default=None, alias="X-Autentique-Signature", max_length=256),
    event_header: str | None = Header(default=None, alias="Event", max_length=128),
    db: AsyncSession = Depends(get_db),
):
    raw = await read_limited_body(request, MAX_WEBHOOK_BYTES, "Webhook muito grande.")
    if provider in CLICKSIGN_BASE_URLS:
        try:
            clicksign_event = parse_clicksign_webhook(raw, event_header)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payload de webhook inválido.") from exc
        identity = await webhook_identity_or_401(
            db,
            raw,
            content_hmac or x_clicksign_signature,
            purpose="signature",
            provider=provider,
            account_reference=clicksign_event.account_reference,
        )
        if clicksign_event.event_type is None:
            return {"received": True, "ignored": True}
        envelope, duplicate = await apply_clicksign_event(db, identity, clicksign_event, raw)
        await audit(db, request, identity.tenant_id, None, "SIGNATURE_PROVIDER_EVENT", "signature_envelopes", envelope.id, {"provider": identity.credential.provider, "event": clicksign_event.event_name, "duplicate": duplicate})
        await db.commit()
        return {"received": True, "duplicate": duplicate}
    if provider in AUTENTIQUE_PROVIDERS:
        try:
            autentique_event = parse_autentique_webhook(raw)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payload de webhook inválido.") from exc
        identity = await webhook_identity_or_401(
            db,
            raw,
            x_autentique_signature,
            purpose="signature",
            provider=provider,
            account_reference=autentique_event.account_reference,
        )
        if autentique_event.event_type is None:
            await record_provider_usage(
                db,
                tenant_id=identity.tenant_id,
                provider=provider,
                metric="webhook_received",
                idempotency_key=f"webhook:{autentique_event.event_id}",
            )
            await db.commit()
            return {"received": True, "ignored": True}
        envelope, queued_event, duplicate = await queue_autentique_event(db, identity, autentique_event, raw)
        await record_provider_usage(
            db,
            tenant_id=identity.tenant_id,
            provider=provider,
            metric="webhook_received",
            idempotency_key=f"webhook:{autentique_event.event_id}",
            envelope_id=envelope.id,
        )
        await audit(db, request, identity.tenant_id, None, "SIGNATURE_PROVIDER_EVENT", "signature_envelopes", envelope.id, {"provider": provider, "event": autentique_event.event_name, "duplicate": duplicate})
        await db.commit()
        if queued_event and autentique_event.event_type == "envelope.signed" and not duplicate:
            try:
                from app.services.autentique_tasks import process_autentique_signature_event

                process_autentique_signature_event.delay(queued_event.id, identity.tenant_id)
            except Exception:
                # Periodic reconciliation picks up the persisted event.
                pass
        return {"received": True, "duplicate": duplicate}
    if not x_operation_account:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Identidade do webhook ausente.")
    identity = await webhook_identity_or_401(db, raw, x_operation_signature, purpose="signature", provider=provider, account_reference=x_operation_account)
    try:
        event = SignatureWebhookEvent.model_validate_json(raw)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payload de webhook inválido.") from exc
    envelope, duplicate = await apply_signature_event(db, identity, event)
    await audit(db, request, identity.tenant_id, None, "SIGNATURE_PROVIDER_EVENT", "signature_envelopes", envelope.id, {"provider": identity.credential.provider, "event": event.event_type, "duplicate": duplicate})
    await db.commit()
    return {"received": True, "duplicate": duplicate}


@public_router.post("/webhooks/payments/{provider}", status_code=status.HTTP_202_ACCEPTED)
async def payment_webhook(
    provider: str,
    request: Request,
    x_operation_account: str = Header(alias="X-Operation-Account", min_length=2, max_length=128),
    x_operation_signature: str | None = Header(default=None, alias="X-Operation-Signature", max_length=256),
    db: AsyncSession = Depends(get_db),
):
    raw = await read_limited_body(request, MAX_WEBHOOK_BYTES, "Webhook muito grande.")
    identity = await webhook_identity_or_401(db, raw, x_operation_signature, purpose="payment", provider=provider, account_reference=x_operation_account)
    try:
        event = PaymentWebhookEvent.model_validate_json(raw)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payload de webhook inválido.") from exc
    receipt, duplicate = await apply_payment_event(db, identity, event)
    await audit(db, request, identity.tenant_id, None, "PAYMENT_PROVIDER_EVENT", "payment_receipts", receipt.id, {"provider": identity.credential.provider, "event": event.event_type, "duplicate": duplicate})
    await db.commit()
    return {"received": True, "duplicate": duplicate}
