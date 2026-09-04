"""HTTP contracts for persisted commercial operations."""

import re
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.schemas.workspace import normalize_phone, normalize_tax_id, required_text


MONEY = Decimal("0.01")
PROVIDER_RE = re.compile(r"^[a-z][a-z0-9_-]{1,31}$")


class OperationsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OperationsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)


def clean_currency(value: str) -> str:
    value = value.strip().upper()
    if len(value) != 3 or not value.isalpha():
        raise ValueError("currency deve usar ISO 4217 de tres letras")
    return value


def clean_provider(value: str) -> str:
    value = value.strip().lower()
    if not PROVIDER_RE.fullmatch(value):
        raise ValueError("provider invalido")
    return value


def clean_url(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError("URL deve usar HTTPS sem credenciais")
    return value.rstrip("/")


def aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime deve incluir fuso horario")
    return value.astimezone(timezone.utc)


class PublicIntakeConfigUpsert(OperationsInput):
    public_token: str | None = Field(default=None, min_length=32, max_length=512)
    enabled: bool = False
    form_title: str = Field(default="Fale com o escritório", min_length=2, max_length=120)
    notice_version: str = Field(min_length=1, max_length=64)
    consent_version: str = Field(min_length=1, max_length=64)
    notice_url: str | None = Field(default=None, max_length=2048)
    allowed_origin: str | None = Field(default=None, max_length=2048)
    expected_revision: int | None = Field(default=None, ge=1)

    @field_validator("form_title", "notice_version", "consent_version")
    @classmethod
    def required(cls, value: str) -> str:
        return required_text(value, "campo")

    @field_validator("notice_url", "allowed_origin")
    @classmethod
    def url(cls, value: str | None) -> str | None:
        return clean_url(value)

    @model_validator(mode="after")
    def enabled_requires_notice(self):
        if self.enabled and not self.notice_url:
            raise ValueError("notice_url e obrigatoria enquanto o formulario estiver ativo")
        return self


class PublicIntakeConfigResponse(OperationsResponse):
    id: str
    enabled: bool
    form_title: str
    notice_version: str
    consent_version: str
    notice_url: str | None
    allowed_origin: str | None
    revision: int
    created_at: datetime
    updated_at: datetime


class PublicIntakeFormResponse(BaseModel):
    form_title: str
    notice_version: str
    consent_version: str
    notice_url: str | None


class PublicIntakeSubmit(OperationsInput):
    name: str = Field(min_length=2, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=32)
    subject: str | None = Field(default=None, max_length=160)
    message: str | None = Field(default=None, max_length=4000)
    preferred_contact_at: datetime | None = None
    consent_version: str = Field(min_length=1, max_length=64)
    consent: Literal[True]

    @field_validator("name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        return required_text(value, "name")

    @field_validator("phone")
    @classmethod
    def valid_phone(cls, value: str | None) -> str | None:
        return normalize_phone(value)

    @field_validator("subject", "message")
    @classmethod
    def trim_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("preferred_contact_at")
    @classmethod
    def valid_preferred_contact(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        value = aware(value)
        if value <= datetime.now(timezone.utc):
            raise ValueError("horario preferencial deve estar no futuro")
        return value


class PublicIntakeReceived(BaseModel):
    intake_id: str
    existing: bool
    received: Literal[True] = True


class PublicIntakeResponse(OperationsResponse):
    id: str
    name: str
    email: EmailStr | None
    phone: str | None
    subject: str | None
    message: str | None
    preferred_contact_at: datetime | None
    consent_version: str
    consented_at: datetime
    status: Literal["new", "converted", "archived"]
    converted_client_id: str | None
    converted_case_id: str | None
    revision: int
    created_at: datetime
    updated_at: datetime


class IntakeConversion(OperationsInput):
    expected_revision: int = Field(ge=1)
    existing_client_id: str | None = Field(default=None, min_length=1, max_length=64)
    case_title: str = Field(min_length=2, max_length=300)
    responsible_user_id: str = Field(min_length=1, max_length=64)
    restricted: bool = False

    @field_validator("case_title")
    @classmethod
    def title(cls, value: str) -> str:
        return required_text(value, "case_title")


class IntakeConversionResponse(BaseModel):
    intake_id: str
    client_id: str
    case_id: str
    existing: bool


class FeeContractCreate(OperationsInput):
    client_id: str = Field(min_length=1, max_length=64)
    case_id: str | None = Field(default=None, max_length=64)
    document_id: str | None = Field(default=None, max_length=64)
    title: str = Field(min_length=2, max_length=200)
    currency: str = Field(default="BRL", min_length=3, max_length=3)
    terms_version: str = Field(min_length=1, max_length=64)

    @field_validator("title", "terms_version")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return required_text(value, "campo")

    @field_validator("currency")
    @classmethod
    def currency_value(cls, value: str) -> str:
        return clean_currency(value)


class FeeContractUpdate(OperationsInput):
    expected_revision: int = Field(ge=1)
    status: Literal["draft", "active", "closed", "void"]


class FeeContractResponse(OperationsResponse):
    id: str
    client_id: str
    case_id: str | None
    document_id: str | None
    title: str
    currency: str
    status: Literal["draft", "active", "closed", "void"]
    terms_version: str
    revision: int
    created_at: datetime
    updated_at: datetime


class FeeRuleCreate(OperationsInput):
    rule_type: Literal["fixed", "hourly", "success"]
    amount: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    percentage: Decimal | None = Field(default=None, gt=0, le=100, max_digits=5, decimal_places=2)
    description: str = Field(min_length=2, max_length=500)

    @field_validator("description")
    @classmethod
    def description_text(cls, value: str) -> str:
        return required_text(value, "description")

    @model_validator(mode="after")
    def value_matches_type(self):
        if self.rule_type in {"fixed", "hourly"} and (self.amount is None or self.percentage is not None):
            raise ValueError("regra fixa/horária exige amount e não aceita percentage")
        if self.rule_type == "success" and (self.percentage is None or self.amount is not None):
            raise ValueError("regra de êxito exige percentage e não aceita amount")
        return self


class FeeRuleResponse(OperationsResponse):
    id: str
    fee_contract_id: str
    rule_type: Literal["fixed", "hourly", "success"]
    amount: Decimal | None
    percentage: Decimal | None
    description: str
    active: bool
    revision: int
    created_at: datetime
    updated_at: datetime


class TimeEntryCreate(OperationsInput):
    fee_contract_id: str = Field(min_length=1, max_length=64)
    fee_rule_id: str = Field(min_length=1, max_length=64)
    case_id: str = Field(min_length=1, max_length=64)
    duration_minutes: int = Field(ge=1, le=1440)
    occurred_at: datetime
    description: str = Field(min_length=2, max_length=500)

    @field_validator("occurred_at")
    @classmethod
    def occurred(cls, value: datetime) -> datetime:
        return aware(value)

    @field_validator("description")
    @classmethod
    def desc(cls, value: str) -> str:
        return required_text(value, "description")


class TimeEntryUpdate(OperationsInput):
    expected_revision: int = Field(ge=1)
    status: Literal["draft", "approved", "void"]


class TimeEntryResponse(OperationsResponse):
    id: str
    fee_contract_id: str
    fee_rule_id: str
    case_id: str
    duration_minutes: int
    occurred_at: datetime
    rate_amount: Decimal
    amount: Decimal
    description: str
    status: Literal["draft", "approved", "invoiced", "void"]
    revision: int
    created_at: datetime
    updated_at: datetime


class InstallmentCreate(OperationsInput):
    due_on: date
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)


class InvoiceCreate(OperationsInput):
    fee_contract_id: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=2, max_length=500)
    total_amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    installments: list[InstallmentCreate] = Field(min_length=1, max_length=120)

    @field_validator("description")
    @classmethod
    def description_text(cls, value: str) -> str:
        return required_text(value, "description")

    @model_validator(mode="after")
    def installments_sum_to_total(self):
        if sum((item.amount for item in self.installments), Decimal()) != self.total_amount:
            raise ValueError("a soma das parcelas deve igualar total_amount")
        return self


class ExpectedRevision(OperationsInput):
    expected_revision: int = Field(ge=1)


class InvoiceResponse(OperationsResponse):
    id: str
    fee_contract_id: str
    client_id: str
    case_id: str | None
    description: str
    currency: str
    total_amount: Decimal
    received_amount: Decimal
    status: Literal["draft", "issued", "partially_paid", "paid", "void", "overdue"]
    issued_at: datetime | None
    revision: int
    created_at: datetime
    updated_at: datetime


class ReceivableResponse(OperationsResponse):
    id: str
    invoice_id: str
    sequence: int
    due_on: date
    amount: Decimal
    paid_amount: Decimal
    status: Literal["pending", "partially_paid", "paid", "void", "overdue"]
    revision: int
    created_at: datetime
    updated_at: datetime


class ProviderCredentialUpsert(OperationsInput):
    account_reference: str = Field(min_length=2, max_length=128)
    webhook_secret: str = Field(min_length=16, max_length=2048)
    api_token: str | None = Field(default=None, min_length=16, max_length=4096)
    enabled: bool = False
    expected_revision: int | None = Field(default=None, ge=1)

    @field_validator("account_reference")
    @classmethod
    def account_ref(cls, value: str) -> str:
        return required_text(value, "account_reference")


class ProviderCredentialResponse(OperationsResponse):
    id: str
    purpose: Literal["signature", "payment"]
    provider: str
    account_reference: str
    enabled: bool
    api_token_configured: bool
    revision: int
    updated_at: datetime


class SignatureEnvelopeCreate(OperationsInput):
    document_id: str = Field(min_length=1, max_length=64)
    document_version: int = Field(ge=1)
    provider: str = Field(min_length=2, max_length=32)
    account_reference: str = Field(min_length=2, max_length=128)
    expires_at: datetime | None = None

    @field_validator("provider")
    @classmethod
    def provider_value(cls, value: str) -> str:
        return clean_provider(value)

    @field_validator("expires_at")
    @classmethod
    def expires(cls, value: datetime | None) -> datetime | None:
        return aware(value) if value else None


class SignatureEnvelopeResponse(OperationsResponse):
    id: str
    document_id: str
    document_version: int
    document_hash: str
    provider: str
    provider_account_reference: str
    status: Literal["pending", "signed", "declined", "expired"]
    dispatch_status: Literal["not_dispatched", "submitted", "unknown", "failed"]
    expires_at: datetime | None
    signed_at: datetime | None
    declined_at: datetime | None
    revision: int
    created_at: datetime
    updated_at: datetime


class SignatureWebhookEvent(OperationsInput):
    event_id: str = Field(min_length=1, max_length=128)
    event_type: Literal["envelope.signed", "envelope.declined", "envelope.expired"]
    envelope_id: str = Field(min_length=1, max_length=64)
    provider_envelope_id: str = Field(min_length=1, max_length=512)


class PaymentWebhookEvent(OperationsInput):
    event_id: str = Field(min_length=1, max_length=128)
    event_type: Literal["payment.received", "payment.reversed"]
    provider_payment_id: str = Field(min_length=1, max_length=512)
    receivable_id: str = Field(min_length=1, max_length=64)
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    currency: str = Field(min_length=3, max_length=3)
    occurred_at: datetime

    @field_validator("currency")
    @classmethod
    def currency_value(cls, value: str) -> str:
        return clean_currency(value)

    @field_validator("occurred_at")
    @classmethod
    def occurred(cls, value: datetime) -> datetime:
        return aware(value)


class PaymentReceiptResponse(OperationsResponse):
    id: str
    receivable_id: str
    provider: str
    amount: Decimal
    currency: str
    status: Literal["received", "reversed"]
    provider_occurred_at: datetime
    reversed_at: datetime | None
    created_at: datetime
