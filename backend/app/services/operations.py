"""Commercial-operation invariants and provider boundary helpers."""

import asyncio
import hashlib
import hmac
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal
from urllib.parse import urljoin, urlsplit

import httpx
from fastapi import HTTPException, Request, status
from sqlalchemy import func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import Base
from app.core.dependencies import _set_tenant_context
from app.core.redis_cache import cache_manager
from app.core.security import decrypt_mfa_secret, encrypt_mfa_secret
from app.models.branding import BrandExport
from app.models.operations import (
    FeeContract,
    FeeRule,
    Invoice,
    PaymentProviderEvent,
    PaymentReceipt,
    ProviderCredential,
    PublicIntake,
    PublicIntakeConfig,
    Receivable,
    SignatureEnvelope,
    SignatureProviderEvent,
    TimeEntry,
)
from app.models.user import User
from app.models.workspace import WorkspaceCase, WorkspaceClient, WorkspaceDocument, WorkspaceDocumentVersion
from app.schemas.operations import (
    FeeContractCreate,
    FeeRuleCreate,
    InvoiceCreate,
    PaymentWebhookEvent,
    ProviderCredentialUpsert,
    PublicIntakeSubmit,
    SignatureWebhookEvent,
    TimeEntryCreate,
)
from app.services.clicksign_provider import (
    CLICKSIGN_BASE_URLS,
    ClicksignDispatchError,
    ClicksignSigner,
    ClicksignWebhook,
    fetch_clicksign_signed_pdf,
    submit_clicksign_envelope,
)
from app.services.autentique_provider import (
    AUTENTIQUE_PROVIDERS,
    AutentiqueDispatchError,
    AutentiqueSigner,
    AutentiqueWebhook,
    fetch_autentique_signed_pdf,
    submit_autentique_document,
)
from app.services.document_storage import enabled as document_storage_enabled
from app.services.document_storage import put as put_document_object
from app.services.document_storage import read as read_document_object
from app.services.document_storage import scan as scan_document_content
from app.services.workspace_service import CASE_MANAGER_ROLES, active_tenant_user, get_case, get_client, get_document, lock_workspace_tenant, require_case_write


MONEY = Decimal("0.01")
PUBLIC_INTAKES_PER_MINUTE = 12
SUPPORTED_SIGNATURE_PROVIDERS = set(CLICKSIGN_BASE_URLS) | set(AUTENTIQUE_PROVIDERS)
SignatureSigner = ClicksignSigner | AutentiqueSigner


def money(value: Decimal) -> Decimal:
    if not value.is_finite():
        raise ValueError("valor monetário inválido")
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def digest(value: str | bytes) -> str:
    return hashlib.sha256(value.encode("utf-8") if isinstance(value, str) else value).hexdigest()


def idempotency_digest(scope: str, key: str) -> str:
    return digest(f"{scope}:{key}")


def provider_reference_digest(provider: str, account_reference: str, reference: str) -> str:
    return digest(f"{provider}:{account_reference}:{reference}")


def document_version_digest(version: WorkspaceDocumentVersion) -> str:
    """Uses the immutable version bytes, never a mutable document row."""
    if version.sha256_hash:
        return version.sha256_hash
    if version.file_content is not None:
        return digest(version.file_content)
    return digest((version.content_text or "").encode("utf-8"))


def verify_hmac_webhook(raw: bytes, signature: str | None, encrypted_secret: str) -> bool:
    """Normalised adapter webhook verifier; provider parsers supply the raw body."""
    if not signature:
        return False
    try:
        secret = decrypt_mfa_secret(encrypted_secret)
    except RuntimeError:
        return False
    candidate = signature.strip()
    algorithm, separator, value = candidate.partition("=")
    if separator:
        if algorithm.casefold() != "sha256":
            return False
        candidate = value
    candidate = candidate.strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", candidate):
        return False
    expected = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(candidate, expected)


class FixedHostHttpClient:
    """Small transport primitive for a reviewed provider adapter.

    The host is fixed at construction; individual envelope payloads cannot
    select an URL, and redirects are refused rather than followed.
    """

    def __init__(self, base_url: str):
        parsed = urlsplit(base_url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("provider base URL must be credential-free HTTPS")
        self.base_url = base_url.rstrip("/") + "/"
        self.host = parsed.netloc.casefold()

    async def post_json(self, path: str, payload: dict, headers: dict[str, str]) -> httpx.Response:
        if not path.startswith("/") or path.startswith("//"):
            raise ValueError("provider path must be absolute and hostless")
        target = urljoin(self.base_url, path.lstrip("/"))
        if urlsplit(target).netloc.casefold() != self.host:
            raise ValueError("provider path escaped fixed host")
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=False) as client:
            response = await client.post(target, json=payload, headers=headers)
        if 300 <= response.status_code < 400:
            raise RuntimeError("provider redirect refused")
        return response


@dataclass(frozen=True)
class WebhookIdentity:
    credential: ProviderCredential
    tenant_id: str


@dataclass(frozen=True)
class SignatureMaterial:
    filename: str
    content: bytes
    sha256: str


async def enforce_public_intake_rate_limit(request: Request, config: PublicIntakeConfig) -> None:
    """Fail closed when the shared rate limiter is unavailable."""
    client = cache_manager.redis_client
    if client is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Rate limiter indisponível")
    address = request.client.host if request.client else "unknown"
    key = f"legaltech:public-intake:{config.id}:{digest(address)[:24]}"
    try:
        count = await client.eval(
            "local n=redis.call('INCR',KEYS[1]); if n==1 then redis.call('EXPIRE',KEYS[1],60) end; return n",
            1,
            key,
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Rate limiter indisponível") from exc
    if int(count) > PUBLIC_INTAKES_PER_MINUTE:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Limite de solicitações atingido")


async def resolve_public_intake_config(db: AsyncSession, token: str) -> PublicIntakeConfig | None:
    """Resolve an opaque public token through a narrow SECURITY DEFINER lookup."""
    token_hash = digest(token)
    if db.bind and db.bind.dialect.name == "postgresql":
        tenant_id = await db.scalar(
            text("SELECT public.public_intake_tenant_for_token(:token_hash)"),
            {"token_hash": token_hash},
        )
        if not tenant_id:
            return None
        await _set_tenant_context(db, tenant_id)
    return await db.scalar(
        select(PublicIntakeConfig).where(PublicIntakeConfig.token_hash == token_hash, PublicIntakeConfig.enabled.is_(True))
    )


async def get_intake(db: AsyncSession, tenant_id: str, intake_id: str, *, for_update: bool = False) -> PublicIntake:
    statement = select(PublicIntake).where(PublicIntake.tenant_id == tenant_id, PublicIntake.id == intake_id)
    if for_update:
        statement = statement.with_for_update()
    record = await db.scalar(statement)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Solicitação não encontrada.")
    return record


async def create_or_get_public_intake(
    db: AsyncSession,
    config: PublicIntakeConfig,
    body: PublicIntakeSubmit,
    idempotency_key: str,
) -> tuple[PublicIntake, bool]:
    if body.consent_version != config.consent_version:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="A versão do consentimento está desatualizada.")
    key_hash = idempotency_digest(config.id, idempotency_key)
    existing = await db.scalar(
        select(PublicIntake).where(PublicIntake.config_id == config.id, PublicIntake.idempotency_hash == key_hash)
    )
    if existing:
        return existing, True
    record = PublicIntake(
        tenant_id=config.tenant_id,
        config_id=config.id,
        idempotency_hash=key_hash,
        name=body.name,
        email=str(body.email) if body.email else None,
        phone=body.phone,
        subject=body.subject,
        message=body.message,
        preferred_contact_at=body.preferred_contact_at,
        consent_version=body.consent_version,
    )
    try:
        async with db.begin_nested():
            db.add(record)
            await db.flush()
    except IntegrityError:
        existing = await db.scalar(
            select(PublicIntake).where(PublicIntake.config_id == config.id, PublicIntake.idempotency_hash == key_hash)
        )
        if existing:
            return existing, True
        raise
    return record, False


async def convert_intake(
    db: AsyncSession,
    user: User,
    intake_id: str,
    *,
    expected_revision: int,
    existing_client_id: str | None,
    case_title: str,
    responsible_user_id: str,
    restricted: bool,
) -> tuple[PublicIntake, WorkspaceClient, WorkspaceCase, bool]:
    """Single tenant lock plus persisted conversion IDs make retries safe."""
    await lock_workspace_tenant(db, user.tenant_id)
    intake = await get_intake(db, user.tenant_id, intake_id, for_update=True)
    if intake.status == "converted":
        client = await get_client(db, user, intake.converted_client_id)
        case = await get_case(db, user, intake.converted_case_id)
        return intake, client, case, True
    if intake.status != "new" or intake.revision != expected_revision:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Solicitação foi alterada por outra sessão.")
    if user.role == "lawyer" and responsible_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Advogado só pode converter para caso próprio.")
    responsible = await active_tenant_user(db, user.tenant_id, responsible_user_id)
    if responsible.role not in CASE_MANAGER_ROLES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Responsável sem permissão para casos.")

    reused = False
    if existing_client_id:
        client = await get_client(db, user, existing_client_id)
        reused = True
    elif intake.email or intake.phone:
        identities = []
        if intake.email:
            identities.append(func.lower(WorkspaceClient.email) == intake.email.casefold())
        if intake.phone:
            identities.append(WorkspaceClient.phone == intake.phone)
        matches = (
            await db.execute(
                select(WorkspaceClient)
                .where(WorkspaceClient.tenant_id == user.tenant_id, or_(*identities))
                .with_for_update()
            )
        ).scalars().all()
        if len(matches) > 1:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Há mais de um cliente com este e-mail; selecione o cliente existente.")
        if matches:
            client = matches[0]
            reused = True
        else:
            client = WorkspaceClient(
                tenant_id=user.tenant_id,
                name=intake.name,
                email=intake.email,
                phone=intake.phone,
                stage="client",
            )
            db.add(client)
            await db.flush()
    else:
        client = WorkspaceClient(tenant_id=user.tenant_id, name=intake.name, phone=intake.phone, stage="client")
        db.add(client)
        await db.flush()
    if client.stage == "inactive":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cliente existente está inativo.")
    if client.stage != "client":
        client.stage = "client"
        client.revision += 1
    case = WorkspaceCase(
        tenant_id=user.tenant_id,
        client_id=client.id,
        title=case_title,
        responsible_user_id=responsible_user_id,
        restricted=restricted,
        status="open",
    )
    db.add(case)
    await db.flush()
    intake.status = "converted"
    intake.converted_client_id = client.id
    intake.converted_case_id = case.id
    intake.converted_by_user_id = user.id
    intake.converted_at = datetime.now(timezone.utc)
    intake.revision += 1
    return intake, client, case, reused


async def get_fee_contract(db: AsyncSession, user: User, contract_id: str, *, for_update: bool = False) -> FeeContract:
    statement = select(FeeContract).where(FeeContract.tenant_id == user.tenant_id, FeeContract.id == contract_id)
    if for_update:
        statement = statement.with_for_update()
    contract = await db.scalar(statement)
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contrato de honorários não encontrado.")
    if contract.case_id:
        await get_case(db, user, contract.case_id)
    return contract


async def get_fee_rule(db: AsyncSession, tenant_id: str, rule_id: str, *, for_update: bool = False) -> FeeRule:
    statement = select(FeeRule).where(FeeRule.tenant_id == tenant_id, FeeRule.id == rule_id)
    if for_update:
        statement = statement.with_for_update()
    rule = await db.scalar(statement)
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Regra de honorários não encontrada.")
    return rule


async def get_invoice(db: AsyncSession, tenant_id: str, invoice_id: str, *, for_update: bool = False) -> Invoice:
    statement = select(Invoice).where(Invoice.tenant_id == tenant_id, Invoice.id == invoice_id)
    if for_update:
        statement = statement.with_for_update()
    invoice = await db.scalar(statement)
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fatura não encontrada.")
    return invoice


async def create_fee_contract(db: AsyncSession, user: User, body: FeeContractCreate) -> FeeContract:
    client = await get_client(db, user, body.client_id)
    if client.stage == "inactive":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cliente inativo.")
    if body.case_id:
        case = await get_case(db, user, body.case_id)
        if case.client_id != client.id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Caso não pertence ao cliente.")
    if body.document_id:
        document = await get_document(db, user, body.document_id)
        if document.client_id and document.client_id != client.id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Documento não pertence ao cliente.")
        if body.case_id and document.case_id and document.case_id != body.case_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Documento não pertence ao caso.")
    record = FeeContract(tenant_id=user.tenant_id, created_by_user_id=user.id, **body.model_dump())
    db.add(record)
    await db.flush()
    return record


async def create_time_entry(db: AsyncSession, user: User, body: TimeEntryCreate) -> TimeEntry:
    contract = await get_fee_contract(db, user, body.fee_contract_id)
    if contract.status != "active":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Contrato de honorários não está ativo.")
    if contract.case_id and contract.case_id != body.case_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Caso não pertence ao contrato.")
    case = await get_case(db, user, body.case_id)
    require_case_write(user, case)
    rule = await get_fee_rule(db, user.tenant_id, body.fee_rule_id)
    if rule.fee_contract_id != contract.id or rule.rule_type != "hourly" or not rule.active or rule.amount is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Selecione uma regra horária ativa do contrato.")
    rate = money(Decimal(rule.amount))
    amount = money(rate * Decimal(body.duration_minutes) / Decimal(60))
    record = TimeEntry(
        tenant_id=user.tenant_id,
        created_by_user_id=user.id,
        rate_amount=rate,
        amount=amount,
        **body.model_dump(),
    )
    db.add(record)
    await db.flush()
    return record


async def create_invoice(db: AsyncSession, user: User, body: InvoiceCreate) -> tuple[Invoice, list[Receivable]]:
    contract = await get_fee_contract(db, user, body.fee_contract_id)
    if contract.status != "active":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Contrato de honorários não está ativo.")
    total = money(body.total_amount)
    installments = [(item.due_on, money(item.amount)) for item in body.installments]
    if sum((amount for _, amount in installments), Decimal()) != total:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="A soma das parcelas não confere.")
    invoice = Invoice(
        tenant_id=user.tenant_id,
        fee_contract_id=contract.id,
        client_id=contract.client_id,
        case_id=contract.case_id,
        description=body.description,
        currency=contract.currency,
        total_amount=total,
        created_by_user_id=user.id,
    )
    db.add(invoice)
    await db.flush()
    receivables = [
        Receivable(tenant_id=user.tenant_id, invoice_id=invoice.id, sequence=index, due_on=due_on, amount=amount)
        for index, (due_on, amount) in enumerate(installments, 1)
    ]
    db.add_all(receivables)
    await db.flush()
    return invoice, receivables


async def upsert_provider_credential(
    db: AsyncSession,
    user: User,
    *,
    purpose: Literal["signature", "payment"],
    provider: str,
    body: ProviderCredentialUpsert,
) -> ProviderCredential:
    existing = await db.scalar(
        select(ProviderCredential)
        .where(
            ProviderCredential.tenant_id == user.tenant_id,
            ProviderCredential.purpose == purpose,
            ProviderCredential.provider == provider,
            ProviderCredential.account_reference == body.account_reference,
        )
        .with_for_update()
    )
    if existing:
        if body.expected_revision != existing.revision:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Credencial foi alterada por outra sessão.")
        existing.webhook_secret_encrypted = encrypt_mfa_secret(body.webhook_secret)
        if body.api_token is not None:
            existing.api_token_encrypted = encrypt_mfa_secret(body.api_token)
        existing.enabled = body.enabled
        existing.revision += 1
        return existing
    if body.expected_revision is not None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="expected_revision só é usado ao atualizar a credencial.")
    record = ProviderCredential(
        tenant_id=user.tenant_id,
        purpose=purpose,
        provider=provider,
        account_reference=body.account_reference,
        webhook_secret_encrypted=encrypt_mfa_secret(body.webhook_secret),
        api_token_encrypted=encrypt_mfa_secret(body.api_token) if body.api_token else None,
        enabled=body.enabled,
    )
    db.add(record)
    await db.flush()
    return record


def _signature_filename(document: WorkspaceDocument, version: WorkspaceDocumentVersion) -> str:
    candidate = version.filename if version.content_type == "application/pdf" else None
    if candidate and candidate.casefold().endswith(".pdf"):
        return candidate[:255]
    stem = re.sub(r"[^0-9A-Za-zÀ-ÿ._ -]+", "", document.title).strip(" ._") or "documento"
    return f"{stem[:247]}.pdf"


async def _read_signature_material(
    db: AsyncSession,
    user: User,
    document: WorkspaceDocument,
    version: WorkspaceDocumentVersion,
) -> SignatureMaterial:
    content: bytes | None = None
    expected_hash: str | None = None
    if version.content_type == "application/pdf":
        if version.object_key:
            if version.storage_status != "available":
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="O PDF ainda não está disponível para assinatura.")
            content = await asyncio.to_thread(read_document_object, version.object_key)
        else:
            content = version.file_content
        expected_hash = version.sha256_hash
    else:
        export = await db.scalar(
            select(BrandExport)
            .where(
                BrandExport.tenant_id == user.tenant_id,
                BrandExport.document_id == document.id,
                BrandExport.document_version == version.version,
            )
            .order_by(BrandExport.created_at.desc())
            .limit(1)
        )
        if export:
            if export.pdf_object_key:
                content = await asyncio.to_thread(read_document_object, export.pdf_object_key)
            else:
                content = export.pdf
            expected_hash = export.sha256_pdf
    if not content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Gere a exportação PDF da versão atual antes de solicitar assinatura.",
        )
    if len(content) > 25 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="O PDF para assinatura excede 25 MB.")
    actual_hash = digest(content)
    if expected_hash and not hmac.compare_digest(actual_hash, expected_hash):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A integridade do PDF para assinatura não confere.")
    if not content.startswith(b"%PDF-"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="A assinatura exige um arquivo PDF válido.")
    return SignatureMaterial(filename=_signature_filename(document, version), content=content, sha256=actual_hash)


async def create_signature_envelope(
    db: AsyncSession,
    user: User,
    *,
    request_key: str,
    document_id: str,
    document_version: int,
    provider: str,
    account_reference: str,
    signer: SignatureSigner,
    expires_at: datetime | None,
) -> tuple[SignatureEnvelope, SignatureMaterial | None, ProviderCredential | None, bool]:
    if provider not in SUPPORTED_SIGNATURE_PROVIDERS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Provedor de assinatura ainda não homologado.")
    request_hash = idempotency_digest(f"signature:{user.tenant_id}", request_key)
    existing = await db.scalar(
        select(SignatureEnvelope).where(
            SignatureEnvelope.tenant_id == user.tenant_id,
            SignatureEnvelope.request_hash == request_hash,
        )
    )
    if existing:
        await get_document(db, user, existing.document_id)
        return existing, None, None, True
    document = await get_document(db, user, document_id)
    if document.current_version != document_version:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A assinatura exige a versão atual do documento.")
    version = await db.scalar(
        select(WorkspaceDocumentVersion).where(
            WorkspaceDocumentVersion.tenant_id == user.tenant_id,
            WorkspaceDocumentVersion.document_id == document_id,
            WorkspaceDocumentVersion.version == document_version,
        )
    )
    if not version:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Snapshot do documento não encontrado.")
    credential = await db.scalar(
        select(ProviderCredential).where(
            ProviderCredential.tenant_id == user.tenant_id,
            ProviderCredential.purpose == "signature",
            ProviderCredential.provider == provider,
            ProviderCredential.account_reference == account_reference,
            ProviderCredential.enabled.is_(True),
        )
    )
    if not credential or not credential.api_token_encrypted:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Provedor de assinatura não configurado.")
    if expires_at and expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Expiração deve estar no futuro.")
    material = await _read_signature_material(db, user, document, version)
    envelope = SignatureEnvelope(
        tenant_id=user.tenant_id,
        document_id=document.id,
        document_version=document_version,
        document_hash=material.sha256,
        request_hash=request_hash,
        provider=provider,
        provider_account_reference=account_reference,
        dispatch_status="unknown",
        expires_at=expires_at,
        created_by_user_id=user.id,
    )
    try:
        async with db.begin_nested():
            db.add(envelope)
            await db.flush()
    except IntegrityError:
        existing = await db.scalar(
            select(SignatureEnvelope).where(
                SignatureEnvelope.tenant_id == user.tenant_id,
                SignatureEnvelope.request_hash == request_hash,
            )
        )
        if not existing:
            raise
        await get_document(db, user, existing.document_id)
        return existing, None, None, True
    return envelope, material, credential, False


def _store_provider_ids(
    envelope: SignatureEnvelope,
    *,
    provider_envelope_id: str | None,
    provider_document_id: str | None,
) -> None:
    if provider_envelope_id:
        envelope.provider_envelope_id_encrypted = encrypt_mfa_secret(provider_envelope_id)
        envelope.provider_envelope_hash = provider_reference_digest(
            envelope.provider, envelope.provider_account_reference, provider_envelope_id
        )
    if provider_document_id:
        envelope.provider_document_id_encrypted = encrypt_mfa_secret(provider_document_id)
        envelope.provider_document_hash = provider_reference_digest(
            envelope.provider, envelope.provider_account_reference, provider_document_id
        )


async def dispatch_signature_envelope(
    envelope: SignatureEnvelope,
    credential: ProviderCredential,
    material: SignatureMaterial,
    signer: SignatureSigner,
) -> ClicksignDispatchError | AutentiqueDispatchError | None:
    try:
        access_token = decrypt_mfa_secret(credential.api_token_encrypted or "")
    except RuntimeError:
        envelope.dispatch_status = "failed"
        envelope.revision += 1
        return ClicksignDispatchError("Credencial do provedor de assinatura indisponível.", ambiguous=False)
    if envelope.provider in AUTENTIQUE_PROVIDERS:
        try:
            submission = await submit_autentique_document(
                access_token=access_token,
                account_reference=envelope.provider_account_reference,
                local_envelope_id=envelope.id,
                filename=material.filename,
                pdf=material.content,
                pdf_sha256=material.sha256,
                signer=AutentiqueSigner(
                    name=signer.name,
                    email=signer.email,
                    cpf=signer.cpf,
                    authentication=signer.authentication,
                ),
                expires_at=envelope.expires_at,
            )
        except ValueError as exc:
            failure = AutentiqueDispatchError(str(exc), ambiguous=False)
            envelope.dispatch_status = "failed"
            envelope.revision += 1
            return failure
        except AutentiqueDispatchError as exc:
            _store_provider_ids(
                envelope,
                provider_envelope_id=exc.document_id,
                provider_document_id=exc.document_id,
            )
            envelope.dispatch_status = "unknown" if exc.ambiguous else "failed"
            envelope.revision += 1
            return exc
        _store_provider_ids(
            envelope,
            provider_envelope_id=submission.document_id,
            provider_document_id=submission.document_id,
        )
        envelope.dispatch_status = "submitted"
        envelope.revision += 1
        return None
    try:
        submission = await submit_clicksign_envelope(
            provider=envelope.provider,
            access_token=access_token,
            local_envelope_id=envelope.id,
            filename=material.filename,
            pdf=material.content,
            pdf_sha256=material.sha256,
            signer=signer,
            expires_at=envelope.expires_at,
        )
    except ClicksignDispatchError as exc:
        _store_provider_ids(
            envelope,
            provider_envelope_id=exc.envelope_id,
            provider_document_id=exc.document_id,
        )
        envelope.dispatch_status = "unknown" if exc.ambiguous else "failed"
        envelope.revision += 1
        return exc
    _store_provider_ids(
        envelope,
        provider_envelope_id=submission.envelope_id,
        provider_document_id=submission.document_id,
    )
    envelope.dispatch_status = "submitted"
    envelope.revision += 1
    return None


async def resolve_webhook_identity(
    db: AsyncSession,
    *,
    purpose: Literal["signature", "payment"],
    provider: str,
    account_reference: str,
) -> WebhookIdentity | None:
    """Gets a tenant only through a migration-owned SECURITY DEFINER function."""
    if not (db.bind and db.bind.dialect.name == "postgresql"):
        return None
    row = (
        await db.execute(
            text("SELECT * FROM public.operation_webhook_identity(:purpose, :provider, :account_reference)"),
            {"purpose": purpose, "provider": provider, "account_reference": account_reference},
        )
    ).first()
    if not row or not row[0]:
        return None
    tenant_id = row[0]
    await _set_tenant_context(db, tenant_id)
    credential = await db.scalar(
        select(ProviderCredential).where(
            ProviderCredential.tenant_id == tenant_id,
            ProviderCredential.purpose == purpose,
            ProviderCredential.provider == provider,
            ProviderCredential.account_reference == account_reference,
            ProviderCredential.enabled.is_(True),
        )
    )
    return WebhookIdentity(credential=credential, tenant_id=tenant_id) if credential else None


async def apply_signature_event(
    db: AsyncSession,
    identity: WebhookIdentity,
    event: SignatureWebhookEvent,
) -> tuple[SignatureEnvelope, bool]:
    envelope = await db.scalar(
        select(SignatureEnvelope)
        .where(
            SignatureEnvelope.tenant_id == identity.tenant_id,
            SignatureEnvelope.id == event.envelope_id,
            SignatureEnvelope.provider == identity.credential.provider,
            SignatureEnvelope.provider_account_reference == identity.credential.account_reference,
        )
        .with_for_update()
    )
    if not envelope:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Envelope não encontrado.")
    reference_hash = provider_reference_digest(identity.credential.provider, identity.credential.account_reference, event.provider_envelope_id)
    if envelope.provider_envelope_hash and envelope.provider_envelope_hash != reference_hash:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Referência externa não confere.")
    event_row = SignatureProviderEvent(
        tenant_id=identity.tenant_id,
        envelope_id=envelope.id,
        provider=identity.credential.provider,
        account_reference=identity.credential.account_reference,
        event_id=event.event_id,
        event_digest=idempotency_digest(f"{identity.credential.provider}:{identity.credential.account_reference}", event.event_id),
        event_type=event.event_type,
    )
    try:
        async with db.begin_nested():
            db.add(event_row)
            await db.flush()
    except IntegrityError:
        return envelope, True
    if envelope.status == "pending":
        envelope.provider_envelope_hash = reference_hash
        envelope.status = {"envelope.signed": "signed", "envelope.declined": "declined", "envelope.expired": "expired"}[event.event_type]
        now = datetime.now(timezone.utc)
        if envelope.status == "signed":
            envelope.signed_at = now
        elif envelope.status == "declined":
            envelope.declined_at = now
        envelope.revision += 1
    return envelope, False


async def get_signature_envelope(
    db: AsyncSession,
    user: User,
    envelope_id: str,
    *,
    for_update: bool = False,
) -> SignatureEnvelope:
    statement = select(SignatureEnvelope).where(
        SignatureEnvelope.tenant_id == user.tenant_id,
        SignatureEnvelope.id == envelope_id,
    )
    if for_update:
        statement = statement.with_for_update()
    envelope = await db.scalar(statement)
    if not envelope:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Envelope não encontrado.")
    await get_document(db, user, envelope.document_id)
    return envelope


async def _store_signed_artifact(
    db: AsyncSession,
    envelope: SignatureEnvelope,
    pdf: bytes,
) -> None:
    signed_hash = digest(pdf)
    if envelope.signed_file_hash:
        if not hmac.compare_digest(envelope.signed_file_hash, signed_hash):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="O provedor retornou conteúdo diferente para um documento assinado já preservado.",
            )
        return
    await asyncio.to_thread(scan_document_content, pdf)
    document = await db.scalar(
        select(WorkspaceDocument).where(
            WorkspaceDocument.tenant_id == envelope.tenant_id,
            WorkspaceDocument.id == envelope.document_id,
        )
    )
    stem = re.sub(r"[^0-9A-Za-zÀ-ÿ._ -]+", "", document.title if document else "documento").strip(" ._") or "documento"
    filename = f"{stem[:225]}-assinado-{envelope.provider}.pdf"
    envelope.signed_filename = filename
    envelope.signed_file_size = len(pdf)
    envelope.signed_file_hash = signed_hash
    if document_storage_enabled():
        key = f"signatures/{envelope.tenant_id}/{envelope.id}/signed.pdf"
        await asyncio.to_thread(put_document_object, key, pdf, "application/pdf", filename)
        envelope.signed_object_key = key
        envelope.signed_file_content = None
    else:
        envelope.signed_file_content = pdf


async def apply_clicksign_event(
    db: AsyncSession,
    identity: WebhookIdentity,
    event: ClicksignWebhook,
    raw: bytes,
) -> tuple[SignatureEnvelope, bool]:
    reference_hash = (
        provider_reference_digest(identity.credential.provider, identity.credential.account_reference, event.provider_document_id)
        if event.provider_document_id
        else None
    )
    selectors = []
    if event.local_envelope_id:
        selectors.append(SignatureEnvelope.id == event.local_envelope_id)
    if reference_hash:
        selectors.append(SignatureEnvelope.provider_document_hash == reference_hash)
    if not selectors:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Webhook não identifica o envelope.")
    base_filter = (
        SignatureEnvelope.tenant_id == identity.tenant_id,
        SignatureEnvelope.provider == identity.credential.provider,
        SignatureEnvelope.provider_account_reference == identity.credential.account_reference,
        or_(*selectors),
    )
    envelope = await db.scalar(select(SignatureEnvelope).where(*base_filter))
    if not envelope:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Envelope não encontrado.")
    if reference_hash and envelope.provider_document_hash and envelope.provider_document_hash != reference_hash:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Documento externo não confere.")
    event_digest = digest(raw)
    duplicate = await db.scalar(
        select(SignatureProviderEvent.id).where(
            SignatureProviderEvent.tenant_id == identity.tenant_id,
            SignatureProviderEvent.provider == identity.credential.provider,
            SignatureProviderEvent.account_reference == identity.credential.account_reference,
            or_(
                SignatureProviderEvent.event_id == event.event_id,
                SignatureProviderEvent.event_digest == event_digest,
            ),
        )
    )
    if duplicate:
        return envelope, True
    signed_pdf: bytes | None = None
    if event.event_type == "envelope.signed" and not envelope.signed_file_available:
        if not envelope.provider_envelope_id_encrypted or not envelope.provider_document_id_encrypted:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Referências da Clicksign não foram preservadas.")
        try:
            access_token = decrypt_mfa_secret(identity.credential.api_token_encrypted or "")
            provider_envelope_id = decrypt_mfa_secret(envelope.provider_envelope_id_encrypted)
            provider_document_id = decrypt_mfa_secret(envelope.provider_document_id_encrypted)
            signed_pdf = await fetch_clicksign_signed_pdf(
                provider=identity.credential.provider,
                access_token=access_token,
                envelope_id=provider_envelope_id,
                document_id=provider_document_id,
            )
            await _set_tenant_context(db, identity.tenant_id)
        except (RuntimeError, ClicksignDispatchError) as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Arquivo assinado ainda não pôde ser preservado; o webhook deve ser reenviado.",
            ) from exc
    envelope = await db.scalar(select(SignatureEnvelope).where(*base_filter).with_for_update())
    if not envelope:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Envelope não encontrado.")
    event_row = SignatureProviderEvent(
        tenant_id=identity.tenant_id,
        envelope_id=envelope.id,
        provider=identity.credential.provider,
        account_reference=identity.credential.account_reference,
        event_id=event.event_id,
        event_digest=event_digest,
        event_type=event.event_type or event.event_name,
    )
    try:
        async with db.begin_nested():
            db.add(event_row)
            await db.flush()
    except IntegrityError:
        return envelope, True
    if event.event_type == "envelope.signed" and signed_pdf is not None:
        await _store_signed_artifact(db, envelope, signed_pdf)
    if event.event_type and envelope.status == "pending":
        envelope.status = {
            "envelope.signed": "signed",
            "envelope.declined": "declined",
            "envelope.expired": "expired",
        }[event.event_type]
        now = datetime.now(timezone.utc)
        if envelope.status == "signed":
            if not envelope.signed_file_available:
                raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Arquivo assinado ainda não foi preservado.")
            envelope.signed_at = now
        elif envelope.status == "declined":
            envelope.declined_at = now
        envelope.revision += 1
    return envelope, False


async def queue_autentique_event(
    db: AsyncSession,
    identity: WebhookIdentity,
    event: AutentiqueWebhook,
    raw: bytes,
) -> tuple[SignatureEnvelope, SignatureProviderEvent | None, bool]:
    """Persist an authenticated notification before acknowledging it.

    The worker performs provider queries and PDF download. Rejections are a
    small local transition and can be applied in this transaction.
    """
    if not event.provider_document_id or not event.event_type:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Webhook não identifica o documento.")
    reference_hash = provider_reference_digest(
        identity.credential.provider,
        identity.credential.account_reference,
        event.provider_document_id,
    )
    envelope = await db.scalar(
        select(SignatureEnvelope)
        .where(
            SignatureEnvelope.tenant_id == identity.tenant_id,
            SignatureEnvelope.provider == identity.credential.provider,
            SignatureEnvelope.provider_account_reference == identity.credential.account_reference,
            SignatureEnvelope.provider_document_hash == reference_hash,
        )
        .with_for_update()
    )
    if not envelope:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Envelope não encontrado.")
    event_digest = digest(raw)
    existing = await db.scalar(
        select(SignatureProviderEvent).where(
            SignatureProviderEvent.tenant_id == identity.tenant_id,
            SignatureProviderEvent.provider == identity.credential.provider,
            SignatureProviderEvent.account_reference == identity.credential.account_reference,
            or_(
                SignatureProviderEvent.event_id == event.event_id,
                SignatureProviderEvent.event_digest == event_digest,
            ),
        )
    )
    if existing:
        return envelope, existing, True
    event_row = SignatureProviderEvent(
        tenant_id=identity.tenant_id,
        envelope_id=envelope.id,
        provider=identity.credential.provider,
        account_reference=identity.credential.account_reference,
        event_id=event.event_id,
        event_digest=event_digest,
        event_type=event.event_type,
    )
    try:
        async with db.begin_nested():
            db.add(event_row)
            await db.flush()
    except IntegrityError:
        return envelope, None, True
    if event.event_type in {"envelope.declined", "envelope.expired"} and envelope.status == "pending":
        envelope.status = "declined" if event.event_type == "envelope.declined" else "expired"
        if envelope.status == "declined":
            envelope.declined_at = datetime.now(timezone.utc)
        envelope.revision += 1
    return envelope, event_row, False


async def finalize_queued_autentique_event(
    db: AsyncSession,
    *,
    tenant_id: str,
    event_id: str,
) -> str:
    event_row = await db.scalar(
        select(SignatureProviderEvent).where(
            SignatureProviderEvent.tenant_id == tenant_id,
            SignatureProviderEvent.id == event_id,
            SignatureProviderEvent.provider == "autentique",
        )
    )
    if not event_row or event_row.event_type != "envelope.signed" or not event_row.envelope_id:
        return "ignored"
    envelope = await db.scalar(
        select(SignatureEnvelope).where(
            SignatureEnvelope.tenant_id == tenant_id,
            SignatureEnvelope.id == event_row.envelope_id,
            SignatureEnvelope.provider == "autentique",
        )
    )
    if not envelope:
        return "ignored"
    if envelope.signed_file_available:
        return "already_finalized"
    credential = await db.scalar(
        select(ProviderCredential).where(
            ProviderCredential.tenant_id == tenant_id,
            ProviderCredential.purpose == "signature",
            ProviderCredential.provider == "autentique",
            ProviderCredential.account_reference == envelope.provider_account_reference,
            ProviderCredential.enabled.is_(True),
        )
    )
    if not credential or not credential.api_token_encrypted or not envelope.provider_document_id_encrypted:
        return "credential_unavailable"
    try:
        pdf = await fetch_autentique_signed_pdf(
            access_token=decrypt_mfa_secret(credential.api_token_encrypted),
            account_reference=credential.account_reference,
            document_id=decrypt_mfa_secret(envelope.provider_document_id_encrypted),
        )
    except (RuntimeError, AutentiqueDispatchError):
        return "provider_deferred"
    await _set_tenant_context(db, tenant_id)
    envelope = await db.scalar(
        select(SignatureEnvelope)
        .where(SignatureEnvelope.tenant_id == tenant_id, SignatureEnvelope.id == event_row.envelope_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not envelope:
        return "ignored"
    await _store_signed_artifact(db, envelope, pdf)
    if envelope.status == "pending":
        envelope.status = "signed"
        envelope.signed_at = datetime.now(timezone.utc)
        envelope.revision += 1
    return "finalized"


async def apply_payment_event(
    db: AsyncSession,
    identity: WebhookIdentity,
    event: PaymentWebhookEvent,
) -> tuple[PaymentReceipt, bool]:
    receivable = await db.scalar(
        select(Receivable).where(Receivable.tenant_id == identity.tenant_id, Receivable.id == event.receivable_id).with_for_update()
    )
    if not receivable:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recebível não encontrado.")
    invoice = await get_invoice(db, identity.tenant_id, receivable.invoice_id, for_update=True)
    if invoice.status not in {"issued", "partially_paid", "paid", "overdue"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Fatura não está emitida para reconciliação.")
    if invoice.currency != event.currency:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Moeda do provedor não confere.")
    event_row = PaymentProviderEvent(
        tenant_id=identity.tenant_id,
        provider=identity.credential.provider,
        account_reference=identity.credential.account_reference,
        event_id=event.event_id,
        event_digest=idempotency_digest(f"{identity.credential.provider}:{identity.credential.account_reference}", event.event_id),
        event_type=event.event_type,
    )
    try:
        async with db.begin_nested():
            db.add(event_row)
            await db.flush()
    except IntegrityError:
        receipt = await db.scalar(
            select(PaymentReceipt)
            .join(PaymentProviderEvent, PaymentProviderEvent.receipt_id == PaymentReceipt.id)
            .where(
                PaymentProviderEvent.tenant_id == identity.tenant_id,
                PaymentProviderEvent.provider == identity.credential.provider,
                PaymentProviderEvent.account_reference == identity.credential.account_reference,
                PaymentProviderEvent.event_id == event.event_id,
            )
        )
        if receipt:
            return receipt, True
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Evento de pagamento em processamento.")
    payment_hash = provider_reference_digest(identity.credential.provider, identity.credential.account_reference, event.provider_payment_id)
    receipt = await db.scalar(
        select(PaymentReceipt)
        .where(
            PaymentReceipt.tenant_id == identity.tenant_id,
            PaymentReceipt.provider == identity.credential.provider,
            PaymentReceipt.provider_account_reference == identity.credential.account_reference,
            PaymentReceipt.provider_payment_hash == payment_hash,
        )
        .with_for_update()
    )
    if event.event_type == "payment.received":
        if receipt:
            event_row.receipt_id = receipt.id
            return receipt, True
        amount = money(event.amount)
        outstanding = money(Decimal(receivable.amount) - Decimal(receivable.paid_amount))
        if amount > outstanding:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Pagamento excede o saldo do recebível.")
        receipt = PaymentReceipt(
            tenant_id=identity.tenant_id,
            receivable_id=receivable.id,
            provider=identity.credential.provider,
            provider_account_reference=identity.credential.account_reference,
            provider_payment_hash=payment_hash,
            amount=amount,
            currency=event.currency,
            provider_occurred_at=event.occurred_at,
        )
        db.add(receipt)
        await db.flush()
        receivable.paid_amount = money(Decimal(receivable.paid_amount) + amount)
        invoice.received_amount = money(Decimal(invoice.received_amount) + amount)
        receivable.status = "paid" if receivable.paid_amount == receivable.amount else "partially_paid"
        invoice.status = "paid" if invoice.received_amount == invoice.total_amount else "partially_paid"
        receivable.revision += 1
        invoice.revision += 1
    else:
        if not receipt or receipt.receivable_id != receivable.id or receipt.status != "received":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Recebimento original não está disponível para estorno.")
        if money(Decimal(receipt.amount)) != money(event.amount):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Valor de estorno não confere.")
        receipt.status = "reversed"
        receipt.reversed_at = datetime.now(timezone.utc)
        amount = money(Decimal(receipt.amount))
        receivable.paid_amount = money(Decimal(receivable.paid_amount) - amount)
        invoice.received_amount = money(Decimal(invoice.received_amount) - amount)
        receivable.status = "pending" if receivable.paid_amount == 0 else "partially_paid"
        invoice.status = "issued" if invoice.received_amount == 0 else "partially_paid"
        receivable.revision += 1
        invoice.revision += 1
    event_row.receipt_id = receipt.id
    return receipt, False
