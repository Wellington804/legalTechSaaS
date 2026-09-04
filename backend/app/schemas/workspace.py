import re
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


CLIENT_STAGES = {"lead", "prospect", "client", "inactive"}
CASE_STATUSES = {"open", "paused", "closed", "archived"}
TASK_KINDS = {"task", "deadline", "hearing"}
TASK_STATUSES = {"pending", "in_progress", "completed", "cancelled"}
DOCUMENT_KINDS = {"document", "template", "note", "evidence"}
PARTY_SIDES = {"client", "opponent", "third_party"}
LEDGER_TYPES = {"fee", "payment", "expense", "time"}
LEDGER_STATUSES = {"draft", "posted", "reversed"}


def normalize_tax_id(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = re.sub(r"\D", "", value)
    if not normalized or len(normalized) not in {11, 14}:
        raise ValueError("CPF/CNPJ deve conter 11 ou 14 digitos")
    return normalized


def normalize_phone(value: str | None) -> str | None:
    if value is None:
        return None
    raw = value.strip()
    if not raw:
        return None
    normalized = re.sub(r"\D", "", raw)
    if raw.startswith("+"):
        if normalized.startswith("55"):
            local = normalized[2:]
            if len(local) not in {10, 11}:
                raise ValueError("telefone brasileiro deve conter 10 ou 11 digitos apos o codigo do pais")
            return f"+55{local}"
        if not 8 <= len(normalized) <= 15:
            raise ValueError("telefone deve conter entre 8 e 15 digitos")
        return f"+{normalized}"
    if normalized.startswith("55") and len(normalized) in {12, 13}:
        return f"+{normalized}"
    if normalized.startswith("0") and len(normalized) in {11, 12}:
        normalized = normalized[1:]
    if len(normalized) in {10, 11}:
        return f"+55{normalized}"
    raise ValueError("telefone brasileiro deve conter DDD e 10 ou 11 digitos")


def normalize_folder_name(value: str) -> str:
    value = " ".join(value.split())
    if not value or any(character in value for character in "/\\\x00"):
        raise ValueError("nome de pasta invalido")
    return value


def normalize_url(value: str) -> str:
    value = value.strip()
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("source_url deve usar http ou https")
    return value


class WorkspaceSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class WorkspaceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Address(WorkspaceInput):
    street: str = Field(min_length=2, max_length=200)
    number: str = Field(min_length=1, max_length=30)
    complement: str | None = Field(default=None, max_length=120)
    district: str | None = Field(default=None, max_length=120)
    city: str = Field(min_length=2, max_length=120)
    state: str = Field(min_length=2, max_length=2)
    postal_code: str = Field(min_length=8, max_length=10)

    @field_validator("state")
    @classmethod
    def normalize_state(cls, value: str) -> str:
        return value.upper()


REPRESENTATIVE_FIELDS = (
    "representative_name", "representative_tax_id", "representative_qualification",
    "representative_email", "representative_phone", "representative_address",
)


def required_text(value: str, field_name: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError(f"{field_name} e obrigatorio")
    return value


def safe_document_text(value: str | None) -> str | None:
    if value is not None and ("<script" in value.casefold() or "<html" in value.casefold()):
        raise ValueError("HTML ativo nao e aceito")
    return value


def normalized_due_at(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("due_at deve incluir fuso horario")
    return value.astimezone(timezone.utc)


class ClientCreate(WorkspaceInput):
    name: str = Field(min_length=2, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=32)
    tax_id: str | None = Field(default=None, max_length=20)
    stage: str = "lead"
    person_type: Literal["individual", "company"] = "individual"
    qualification: str | None = Field(default=None, max_length=500)
    occupation: str | None = Field(default=None, max_length=160)
    has_legal_representative: bool = False
    representative_name: str | None = Field(default=None, max_length=200)
    representative_tax_id: str | None = Field(default=None, max_length=20)
    representative_qualification: str | None = Field(default=None, max_length=500)
    representative_email: EmailStr | None = None
    representative_phone: str | None = Field(default=None, max_length=32)
    representative_address: Address | None = None
    address: Address | None = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return required_text(value, "name")

    @field_validator("representative_name", "representative_qualification")
    @classmethod
    def clean_representative_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("phone")
    @classmethod
    def clean_phone(cls, value: str | None) -> str | None:
        return normalize_phone(value)

    @field_validator("tax_id")
    @classmethod
    def clean_tax_id(cls, value: str | None) -> str | None:
        return normalize_tax_id(value)

    @field_validator("representative_tax_id")
    @classmethod
    def clean_representative_tax_id(cls, value: str | None) -> str | None:
        return normalize_tax_id(value)

    @field_validator("representative_phone")
    @classmethod
    def clean_representative_phone(cls, value: str | None) -> str | None:
        return normalize_phone(value)

    @model_validator(mode="after")
    def valid_representative(self):
        if self.has_legal_representative and not self.representative_name:
            raise ValueError("informe o nome do representante legal")
        if not self.has_legal_representative:
            for field_name in REPRESENTATIVE_FIELDS:
                setattr(self, field_name, None)
        return self

    @field_validator("stage")
    @classmethod
    def valid_stage(cls, value: str) -> str:
        if value not in CLIENT_STAGES:
            raise ValueError("stage invalido")
        return value


class ClientUpdate(WorkspaceInput):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=32)
    tax_id: str | None = Field(default=None, max_length=20)
    stage: str | None = None
    person_type: Literal["individual", "company"] | None = None
    qualification: str | None = Field(default=None, max_length=500)
    occupation: str | None = Field(default=None, max_length=160)
    has_legal_representative: bool | None = None
    representative_name: str | None = Field(default=None, max_length=200)
    representative_tax_id: str | None = Field(default=None, max_length=20)
    representative_qualification: str | None = Field(default=None, max_length=500)
    representative_email: EmailStr | None = None
    representative_phone: str | None = Field(default=None, max_length=32)
    representative_address: Address | None = None
    address: Address | None = None
    expected_revision: int = Field(ge=1)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        return required_text(value, "name") if value is not None else None

    @field_validator("representative_name", "representative_qualification")
    @classmethod
    def clean_representative_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("phone")
    @classmethod
    def clean_phone(cls, value: str | None) -> str | None:
        return normalize_phone(value)

    @field_validator("tax_id")
    @classmethod
    def clean_tax_id(cls, value: str | None) -> str | None:
        return normalize_tax_id(value)

    @field_validator("representative_tax_id")
    @classmethod
    def clean_representative_tax_id(cls, value: str | None) -> str | None:
        return normalize_tax_id(value)

    @field_validator("representative_phone")
    @classmethod
    def clean_representative_phone(cls, value: str | None) -> str | None:
        return normalize_phone(value)

    @model_validator(mode="after")
    def valid_representative(self):
        if self.has_legal_representative is True and not self.representative_name:
            raise ValueError("informe o nome do representante legal")
        return self

    @field_validator("stage")
    @classmethod
    def valid_stage(cls, value: str | None) -> str | None:
        if value is not None and value not in CLIENT_STAGES:
            raise ValueError("stage invalido")
        return value


class ClientResponse(WorkspaceSchema):
    id: str
    name: str
    email: EmailStr | None
    phone: str | None
    tax_id: str | None
    stage: str
    person_type: Literal["individual", "company"]
    qualification: str | None
    occupation: str | None
    has_legal_representative: bool
    representative_name: str | None
    representative_tax_id: str | None
    representative_qualification: str | None
    representative_email: EmailStr | None
    representative_phone: str | None
    representative_address: Address | None
    address: Address | None
    archived_at: datetime | None
    revision: int
    created_at: datetime
    updated_at: datetime


class ClientImport(WorkspaceInput):
    items: list[ClientCreate] = Field(min_length=1, max_length=200)


class WorkspaceMemberResponse(WorkspaceSchema):
    id: str
    full_name: str
    email: EmailStr
    role: str


class CaseCreate(WorkspaceInput):
    client_id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=2, max_length=300)
    number: str | None = Field(default=None, max_length=64)
    court: str | None = Field(default=None, max_length=300)
    status: str = "open"
    responsible_user_id: str = Field(min_length=1, max_length=64)
    restricted: bool = False

    @field_validator("status")
    @classmethod
    def valid_status(cls, value: str) -> str:
        if value not in CASE_STATUSES:
            raise ValueError("status invalido")
        return value

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        return required_text(value, "title")


class CaseUpdate(WorkspaceInput):
    title: str | None = Field(default=None, min_length=2, max_length=300)
    number: str | None = Field(default=None, max_length=64)
    court: str | None = Field(default=None, max_length=300)
    status: str | None = None
    responsible_user_id: str | None = Field(default=None, min_length=1, max_length=64)
    restricted: bool | None = None
    expected_revision: int = Field(ge=1)

    @field_validator("status")
    @classmethod
    def valid_status(cls, value: str | None) -> str | None:
        if value is not None and value not in CASE_STATUSES:
            raise ValueError("status invalido")
        return value

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("title nao pode ser nulo")
        return required_text(value, "title")


class CaseResponse(WorkspaceSchema):
    id: str
    client_id: str
    title: str
    number: str | None
    court: str | None
    status: str
    responsible_user_id: str
    restricted: bool
    archived_at: datetime | None
    revision: int
    created_at: datetime
    updated_at: datetime


class CasePartyCreate(WorkspaceInput):
    name: str = Field(min_length=2, max_length=200)
    tax_id: str | None = Field(default=None, max_length=20)
    side: str = "third_party"
    role: str | None = Field(default=None, max_length=100)

    @field_validator("tax_id")
    @classmethod
    def clean_tax_id(cls, value: str | None) -> str | None:
        return normalize_tax_id(value)

    @field_validator("side")
    @classmethod
    def valid_side(cls, value: str) -> str:
        if value not in PARTY_SIDES:
            raise ValueError("side invalido")
        return value

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return required_text(value, "name")


class CasePartyResponse(WorkspaceSchema):
    id: str
    case_id: str
    name: str
    tax_id: str | None
    side: str
    role: str | None
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CaseAccessCreate(WorkspaceInput):
    user_id: str = Field(min_length=1, max_length=64)


class CaseAccessResponse(WorkspaceSchema):
    id: str
    case_id: str
    user_id: str
    created_at: datetime


class TaskCreate(WorkspaceInput):
    request_id: UUID | None = None
    location: str | None = Field(default=None, max_length=300)
    contact: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=5000)
    case_id: str | None = Field(default=None, max_length=64)
    title: str = Field(min_length=2, max_length=300)
    kind: str = "task"
    due_at: datetime | None = None
    assigned_user_id: str | None = Field(default=None, max_length=64)
    status: str = "pending"
    manually_reviewed: bool = False

    @field_validator("kind")
    @classmethod
    def valid_kind(cls, value: str) -> str:
        if value not in TASK_KINDS:
            raise ValueError("kind invalido")
        return value

    @field_validator("status")
    @classmethod
    def valid_status(cls, value: str) -> str:
        if value not in TASK_STATUSES:
            raise ValueError("status invalido")
        return value

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        return required_text(value, "title")

    @field_validator("due_at")
    @classmethod
    def valid_due_at(cls, value: datetime | None) -> datetime | None:
        return normalized_due_at(value)


class TaskUpdate(WorkspaceInput):
    location: str | None = Field(default=None, max_length=300)
    contact: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=5000)
    title: str | None = Field(default=None, min_length=2, max_length=300)
    due_at: datetime | None = None
    assigned_user_id: str | None = Field(default=None, max_length=64)
    status: str | None = None
    manually_reviewed: bool | None = None
    expected_revision: int = Field(ge=1)

    @field_validator("status")
    @classmethod
    def valid_status(cls, value: str | None) -> str | None:
        if value is not None and value not in TASK_STATUSES:
            raise ValueError("status invalido")
        return value

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str | None) -> str | None:
        return required_text(value, "title") if value is not None else None

    @field_validator("due_at")
    @classmethod
    def valid_due_at(cls, value: datetime | None) -> datetime | None:
        return normalized_due_at(value)


class TaskResponse(WorkspaceSchema):
    location: str | None = None
    contact: str | None = None
    notes: str | None = None
    id: str
    request_id: str | None
    case_id: str | None
    title: str
    kind: str
    due_at: datetime | None
    assigned_user_id: str | None
    status: str
    manually_reviewed: bool
    revision: int
    created_at: datetime
    updated_at: datetime


class DocumentCreate(WorkspaceInput):
    content_format: Literal["plain", "markdown"] = "plain"
    case_id: str | None = Field(default=None, max_length=64)
    client_id: str | None = Field(default=None, max_length=64)
    folder_id: str | None = Field(default=None, max_length=64)
    kind: str = "document"
    document_type: Literal["general", "petition", "contract", "power_of_attorney", "notice", "correspondence"] = "general"
    title: str = Field(min_length=2, max_length=300)
    content_text: str | None = Field(default=None, max_length=1_000_000)

    @field_validator("kind")
    @classmethod
    def valid_kind(cls, value: str) -> str:
        if value not in DOCUMENT_KINDS:
            raise ValueError("kind invalido")
        return value

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        return required_text(value, "title")

    @field_validator("content_text")
    @classmethod
    def safe_content_text(cls, value: str | None) -> str | None:
        return safe_document_text(value)


class DocumentUpdate(WorkspaceInput):
    content_format: Literal["plain", "markdown"] | None = None
    title: str | None = Field(default=None, min_length=2, max_length=300)
    content_text: str | None = Field(default=None, max_length=1_000_000)
    expected_version: int | None = Field(default=None, ge=1)
    expected_revision: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def needs_concurrency_token(self):
        if self.expected_version is None and self.expected_revision is None:
            raise ValueError("expected_version ou expected_revision e obrigatorio")
        return self

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str | None) -> str | None:
        return required_text(value, "title") if value is not None else None

    @field_validator("content_text")
    @classmethod
    def safe_content_text(cls, value: str | None) -> str | None:
        return safe_document_text(value)


class DocumentResponse(WorkspaceSchema):
    content_format: Literal["plain", "markdown"] = "plain"
    id: str
    case_id: str | None
    client_id: str | None
    folder_id: str | None
    kind: str
    document_type: Literal["general", "petition", "contract", "power_of_attorney", "notice", "correspondence"] = "general"
    title: str
    content_text: str | None
    filename: str | None
    content_type: str | None
    file_size: int | None
    sha256_hash: str | None
    current_version: int
    review_status: Literal["draft", "in_review", "approved", "final"] = "draft"
    review_version: int | None
    reviewed_by_user_id: str | None
    reviewed_at: datetime | None
    revision: int
    archived_at: datetime | None
    deleted_at: datetime | None
    purge_after: datetime | None
    created_at: datetime
    updated_at: datetime


class DocumentVersionResponse(WorkspaceSchema):
    content_format: Literal["plain", "markdown"] = "plain"
    id: str
    document_id: str
    version: int
    content_text: str | None
    filename: str | None
    content_type: str | None
    file_size: int | None
    sha256_hash: str | None
    storage_status: str
    ocr_status: str
    processing_error: str | None
    created_by_user_id: str | None
    created_by_portal_grant_id: str | None
    created_at: datetime


class DocumentFolderCreate(WorkspaceInput):
    client_id: str = Field(min_length=1, max_length=64)
    case_id: str | None = Field(default=None, max_length=64)
    parent_id: str | None = Field(default=None, max_length=64)
    name: str = Field(min_length=1, max_length=160)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return normalize_folder_name(value)


class DocumentFolderUpdate(WorkspaceInput):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    parent_id: str | None = Field(default=None, max_length=64)
    expected_revision: int = Field(ge=1)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        return normalize_folder_name(value) if value is not None else None


class DocumentFolderResponse(WorkspaceSchema):
    id: str
    client_id: str
    case_id: str | None
    parent_id: str | None
    name: str
    revision: int
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class DocumentUploadCreate(WorkspaceInput):
    client_id: str = Field(min_length=1, max_length=64)
    case_id: str | None = Field(default=None, max_length=64)
    folder_id: str | None = Field(default=None, max_length=64)
    document_id: str | None = Field(default=None, max_length=64)
    expected_version: int | None = Field(default=None, ge=1)
    filename: str = Field(min_length=1, max_length=255)
    size: int = Field(gt=0, le=25 * 1024 * 1024)
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def version_is_required_for_existing_document(self):
        if bool(self.document_id) != bool(self.expected_version):
            raise ValueError("document_id e expected_version devem ser enviados juntos")
        return self


class DocumentUploadResponse(WorkspaceSchema):
    id: str
    status: str
    document_id: str | None
    filename: str
    expected_size: int
    expires_at: datetime
    error: str | None
    upload_url: str | None = None
    upload_headers: dict[str, str] | None = None


class DocumentMove(WorkspaceInput):
    folder_id: str | None = Field(default=None, max_length=64)
    expected_revision: int = Field(ge=1)


class LibraryEntryCreate(WorkspaceInput):
    title: str = Field(min_length=2, max_length=300)
    source_url: str = Field(min_length=8, max_length=2048)
    source_date: date | None = None
    note: str | None = Field(default=None, max_length=20_000)

    @field_validator("source_url")
    @classmethod
    def valid_url(cls, value: str) -> str:
        return normalize_url(value)

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        return required_text(value, "title")


class LibraryEntryResponse(WorkspaceSchema):
    id: str
    title: str
    source_url: str
    source_date: date | None
    note: str | None
    archived_at: datetime | None
    created_by_user_id: str
    created_at: datetime
    updated_at: datetime


class LibraryEntryUpdate(WorkspaceInput):
    title: str | None = Field(default=None, min_length=2, max_length=300)
    source_url: str | None = Field(default=None, min_length=8, max_length=2048)
    source_date: date | None = None
    note: str | None = Field(default=None, max_length=20_000)

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str | None) -> str | None:
        return required_text(value, "title") if value is not None else None

    @field_validator("source_url")
    @classmethod
    def valid_url(cls, value: str | None) -> str | None:
        return normalize_url(value) if value is not None else None


class PublicationCreate(WorkspaceInput):
    case_id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=2, max_length=500)
    source_url: str = Field(min_length=8, max_length=2048)
    published_at: date
    note: str | None = Field(default=None, max_length=20_000)

    @field_validator("source_url")
    @classmethod
    def valid_url(cls, value: str) -> str:
        return normalize_url(value)

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        return required_text(value, "title")


class PublicationResponse(WorkspaceSchema):
    id: str
    case_id: str
    title: str
    source_url: str
    published_at: date
    note: str | None
    source_kind: Literal["manual", "datajud"]
    acknowledged_at: datetime | None
    acknowledged_by_user_id: str | None
    created_at: datetime


class PublicationUpdate(WorkspaceInput):
    note: str | None = Field(default=None, max_length=20_000)


class LedgerEntryCreate(WorkspaceInput):
    case_id: str | None = Field(default=None, max_length=64)
    client_id: str | None = Field(default=None, max_length=64)
    entry_type: str
    amount: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    currency: str = Field(default="BRL", min_length=3, max_length=3)
    duration_minutes: int | None = Field(default=None, ge=1, le=1440)
    description: str = Field(min_length=2, max_length=500)

    @field_validator("entry_type")
    @classmethod
    def valid_type(cls, value: str) -> str:
        if value not in LEDGER_TYPES:
            raise ValueError("entry_type invalido")
        return value

    @field_validator("currency")
    @classmethod
    def clean_currency(cls, value: str) -> str:
        if not value.isalpha():
            raise ValueError("currency deve ter tres letras")
        return value.upper()

    @model_validator(mode="after")
    def validate_amount_for_type(self):
        if self.entry_type == "time" and self.duration_minutes is None:
            raise ValueError("duration_minutes e obrigatorio para apontamento de horas")
        if self.entry_type != "time" and self.amount <= 0:
            raise ValueError("amount deve ser maior que zero")
        if self.entry_type == "payment":
            raise ValueError("pagamentos exigem confirmacao manual explicita")
        return self

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: str) -> str:
        return required_text(value, "description")


class LedgerEntryResponse(WorkspaceSchema):
    id: str
    case_id: str | None
    client_id: str | None
    entry_type: str
    amount: Decimal
    currency: str
    duration_minutes: int | None
    description: str
    status: str
    manual_payment_confirmed_at: datetime | None
    manual_confirmation_reason: str | None
    reversal_of_id: str | None
    reversal_reason: str | None
    created_at: datetime
    updated_at: datetime


class LedgerEntryUpdate(WorkspaceInput):
    description: str = Field(min_length=2, max_length=500)

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: str) -> str:
        return required_text(value, "description")


class ManualPaymentCreate(WorkspaceInput):
    request_id: UUID
    case_id: str | None = Field(default=None, max_length=64)
    client_id: str | None = Field(default=None, max_length=64)
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    currency: str = Field(default="BRL", min_length=3, max_length=3)
    description: str = Field(min_length=2, max_length=500)
    confirmation_reason: str = Field(min_length=3, max_length=500)

    @field_validator("currency")
    @classmethod
    def clean_currency(cls, value: str) -> str:
        if not value.isalpha():
            raise ValueError("currency deve ter tres letras")
        return value.upper()

    @field_validator("description", "confirmation_reason")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return required_text(value, "texto")


class LedgerReverse(WorkspaceInput):
    reason: str = Field(min_length=3, max_length=500)


class ListResponse(WorkspaceSchema):
    items: list
    limit: int
