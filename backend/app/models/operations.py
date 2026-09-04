"""Persisted, tenant-scoped commercial operations.

External payment and signature providers are deliberately represented as
receipts/events.  This module never treats a browser action as either payment
or a legally valid signature.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PublicIntakeConfig(Base):
    __tablename__ = "public_intake_configs"
    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_public_intake_configs_tenant"),
        UniqueConstraint("token_hash", name="uq_public_intake_configs_token"),
        UniqueConstraint("tenant_id", "id", name="uq_public_intake_configs_tenant_id"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False)
    enabled = Column(Boolean, nullable=False, default=False)
    form_title = Column(String(120), nullable=False, default="Fale com o escritório")
    notice_version = Column(String(64), nullable=False)
    consent_version = Column(String(64), nullable=False)
    notice_url = Column(String(2048), nullable=True)
    allowed_origin = Column(String(2048), nullable=True)
    revision = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class PublicIntake(Base):
    __tablename__ = "public_intakes"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_public_intakes_tenant_id"),
        UniqueConstraint("config_id", "idempotency_hash", name="uq_public_intakes_idempotency"),
        ForeignKeyConstraint(
            ["tenant_id", "config_id"],
            ["public_intake_configs.tenant_id", "public_intake_configs.id"],
            name="fk_public_intakes_config_tenant",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "converted_client_id"],
            ["workspace_clients.tenant_id", "workspace_clients.id"],
            name="fk_public_intakes_client_tenant",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "converted_case_id"],
            ["workspace_cases.tenant_id", "workspace_cases.id"],
            name="fk_public_intakes_case_tenant",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "converted_by_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_public_intakes_converter_tenant",
        ),
        CheckConstraint("status IN ('new', 'converted', 'archived')", name="ck_public_intakes_status"),
        CheckConstraint(
            "(converted_client_id IS NULL) = (converted_case_id IS NULL)",
            name="ck_public_intakes_conversion_pair",
        ),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    config_id = Column(String, nullable=False, index=True)
    idempotency_hash = Column(String(64), nullable=False)
    name = Column(String(200), nullable=False)
    email = Column(String(320), nullable=True)
    phone = Column(String(32), nullable=True)
    subject = Column(String(160), nullable=True)
    message = Column(Text, nullable=True)
    preferred_contact_at = Column(DateTime(timezone=True), nullable=True, index=True)
    consent_version = Column(String(64), nullable=False)
    consented_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    status = Column(String(16), nullable=False, default="new", index=True)
    converted_client_id = Column(String, nullable=True, index=True)
    converted_case_id = Column(String, nullable=True, index=True)
    converted_by_user_id = Column(String, nullable=True)
    converted_at = Column(DateTime(timezone=True), nullable=True)
    revision = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class FeeContract(Base):
    __tablename__ = "fee_contracts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_fee_contracts_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "client_id"],
            ["workspace_clients.tenant_id", "workspace_clients.id"],
            name="fk_fee_contracts_client_tenant",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["workspace_cases.tenant_id", "workspace_cases.id"],
            name="fk_fee_contracts_case_tenant",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "document_id"],
            ["workspace_documents.tenant_id", "workspace_documents.id"],
            name="fk_fee_contracts_document_tenant",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "created_by_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_fee_contracts_creator_tenant",
        ),
        CheckConstraint("status IN ('draft', 'active', 'closed', 'void')", name="ck_fee_contracts_status"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_fee_contracts_currency"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    client_id = Column(String, nullable=False, index=True)
    case_id = Column(String, nullable=True, index=True)
    document_id = Column(String, nullable=True, index=True)
    title = Column(String(200), nullable=False)
    currency = Column(String(3), nullable=False, default="BRL")
    status = Column(String(16), nullable=False, default="draft", index=True)
    terms_version = Column(String(64), nullable=False)
    revision = Column(Integer, nullable=False, default=1)
    created_by_user_id = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class FeeRule(Base):
    __tablename__ = "fee_rules"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_fee_rules_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "fee_contract_id"],
            ["fee_contracts.tenant_id", "fee_contracts.id"],
            name="fk_fee_rules_contract_tenant",
            ondelete="RESTRICT",
        ),
        CheckConstraint("rule_type IN ('fixed', 'hourly', 'success')", name="ck_fee_rules_type"),
        CheckConstraint(
            "(rule_type IN ('fixed', 'hourly') AND amount IS NOT NULL AND amount > 0 AND percentage IS NULL) "
            "OR (rule_type = 'success' AND amount IS NULL AND percentage IS NOT NULL AND percentage > 0 AND percentage <= 100)",
            name="ck_fee_rules_value",
        ),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    fee_contract_id = Column(String, nullable=False, index=True)
    rule_type = Column(String(16), nullable=False)
    amount = Column(Numeric(14, 2), nullable=True)
    percentage = Column(Numeric(5, 2), nullable=True)
    description = Column(String(500), nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    revision = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class TimeEntry(Base):
    __tablename__ = "time_entries"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_time_entries_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "fee_contract_id"],
            ["fee_contracts.tenant_id", "fee_contracts.id"],
            name="fk_time_entries_contract_tenant",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "fee_rule_id"],
            ["fee_rules.tenant_id", "fee_rules.id"],
            name="fk_time_entries_rule_tenant",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["workspace_cases.tenant_id", "workspace_cases.id"],
            name="fk_time_entries_case_tenant",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "created_by_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_time_entries_creator_tenant",
        ),
        CheckConstraint("status IN ('draft', 'approved', 'invoiced', 'void')", name="ck_time_entries_status"),
        CheckConstraint("duration_minutes BETWEEN 1 AND 1440", name="ck_time_entries_duration"),
        CheckConstraint("amount >= 0", name="ck_time_entries_amount"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    fee_contract_id = Column(String, nullable=False, index=True)
    fee_rule_id = Column(String, nullable=False, index=True)
    case_id = Column(String, nullable=False, index=True)
    duration_minutes = Column(Integer, nullable=False)
    occurred_at = Column(DateTime(timezone=True), nullable=False, index=True)
    rate_amount = Column(Numeric(14, 2), nullable=False)
    amount = Column(Numeric(14, 2), nullable=False)
    description = Column(String(500), nullable=False)
    status = Column(String(16), nullable=False, default="draft", index=True)
    revision = Column(Integer, nullable=False, default=1)
    created_by_user_id = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_invoices_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "fee_contract_id"],
            ["fee_contracts.tenant_id", "fee_contracts.id"],
            name="fk_invoices_contract_tenant",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "client_id"],
            ["workspace_clients.tenant_id", "workspace_clients.id"],
            name="fk_invoices_client_tenant",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["workspace_cases.tenant_id", "workspace_cases.id"],
            name="fk_invoices_case_tenant",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "created_by_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_invoices_creator_tenant",
        ),
        CheckConstraint("status IN ('draft', 'issued', 'partially_paid', 'paid', 'void', 'overdue')", name="ck_invoices_status"),
        CheckConstraint("total_amount > 0 AND received_amount >= 0 AND received_amount <= total_amount", name="ck_invoices_amounts"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    fee_contract_id = Column(String, nullable=False, index=True)
    client_id = Column(String, nullable=False, index=True)
    case_id = Column(String, nullable=True, index=True)
    description = Column(String(500), nullable=False)
    currency = Column(String(3), nullable=False, default="BRL")
    total_amount = Column(Numeric(14, 2), nullable=False)
    received_amount = Column(Numeric(14, 2), nullable=False, default=0)
    status = Column(String(20), nullable=False, default="draft", index=True)
    issued_at = Column(DateTime(timezone=True), nullable=True)
    revision = Column(Integer, nullable=False, default=1)
    created_by_user_id = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class Receivable(Base):
    __tablename__ = "receivables"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_receivables_tenant_id"),
        UniqueConstraint("invoice_id", "sequence", name="uq_receivables_invoice_sequence"),
        ForeignKeyConstraint(
            ["tenant_id", "invoice_id"],
            ["invoices.tenant_id", "invoices.id"],
            name="fk_receivables_invoice_tenant",
            ondelete="RESTRICT",
        ),
        CheckConstraint("status IN ('pending', 'partially_paid', 'paid', 'void', 'overdue')", name="ck_receivables_status"),
        CheckConstraint("amount > 0 AND paid_amount >= 0 AND paid_amount <= amount", name="ck_receivables_amounts"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    invoice_id = Column(String, nullable=False, index=True)
    sequence = Column(Integer, nullable=False)
    due_on = Column(Date, nullable=False, index=True)
    amount = Column(Numeric(14, 2), nullable=False)
    paid_amount = Column(Numeric(14, 2), nullable=False, default=0)
    status = Column(String(20), nullable=False, default="pending", index=True)
    revision = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class ProviderCredential(Base):
    """Encrypted provider credentials; secret material is never serialized."""

    __tablename__ = "operation_provider_credentials"
    __table_args__ = (
        UniqueConstraint("tenant_id", "purpose", "provider", "account_reference", name="uq_operation_provider_credential"),
        UniqueConstraint("purpose", "provider", "account_reference", name="uq_operation_provider_webhook_identity"),
        UniqueConstraint("tenant_id", "id", name="uq_operation_provider_credentials_tenant_id"),
        CheckConstraint("purpose IN ('signature', 'payment')", name="ck_operation_provider_credentials_purpose"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    purpose = Column(String(16), nullable=False)
    provider = Column(String(32), nullable=False)
    account_reference = Column(String(128), nullable=False)
    api_token_encrypted = Column(Text, nullable=True)
    webhook_secret_encrypted = Column(Text, nullable=False)
    enabled = Column(Boolean, nullable=False, default=False)
    revision = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class SignatureEnvelope(Base):
    __tablename__ = "signature_envelopes"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_signature_envelopes_tenant_id"),
        UniqueConstraint("tenant_id", "provider", "provider_account_reference", "provider_envelope_hash", name="uq_signature_envelopes_provider_reference"),
        ForeignKeyConstraint(
            ["tenant_id", "document_id"],
            ["workspace_documents.tenant_id", "workspace_documents.id"],
            name="fk_signature_envelopes_document_tenant",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "created_by_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_signature_envelopes_creator_tenant",
        ),
        CheckConstraint("status IN ('pending', 'signed', 'declined', 'expired')", name="ck_signature_envelopes_status"),
        CheckConstraint("dispatch_status IN ('not_dispatched', 'submitted', 'unknown', 'failed')", name="ck_signature_envelopes_dispatch"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    document_id = Column(String, nullable=False, index=True)
    document_version = Column(Integer, nullable=False)
    document_hash = Column(String(64), nullable=False)
    provider = Column(String(32), nullable=False)
    provider_account_reference = Column(String(128), nullable=False)
    provider_envelope_hash = Column(String(64), nullable=True)
    status = Column(String(16), nullable=False, default="pending", index=True)
    dispatch_status = Column(String(20), nullable=False, default="not_dispatched")
    expires_at = Column(DateTime(timezone=True), nullable=True)
    signed_at = Column(DateTime(timezone=True), nullable=True)
    declined_at = Column(DateTime(timezone=True), nullable=True)
    revision = Column(Integer, nullable=False, default=1)
    created_by_user_id = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class SignatureProviderEvent(Base):
    __tablename__ = "signature_provider_events"
    __table_args__ = (
        UniqueConstraint("tenant_id", "provider", "account_reference", "event_id", name="uq_signature_provider_event"),
        UniqueConstraint("tenant_id", "provider", "account_reference", "event_digest", name="uq_signature_provider_event_digest"),
        ForeignKeyConstraint(
            ["tenant_id", "envelope_id"],
            ["signature_envelopes.tenant_id", "signature_envelopes.id"],
            name="fk_signature_provider_events_envelope_tenant",
        ),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    envelope_id = Column(String, nullable=True, index=True)
    provider = Column(String(32), nullable=False)
    account_reference = Column(String(128), nullable=False)
    event_id = Column(String(128), nullable=False)
    event_digest = Column(String(64), nullable=False)
    event_type = Column(String(64), nullable=False)
    received_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class PaymentProviderEvent(Base):
    __tablename__ = "payment_provider_events"
    __table_args__ = (
        UniqueConstraint("tenant_id", "provider", "account_reference", "event_id", name="uq_payment_provider_event"),
        UniqueConstraint("tenant_id", "provider", "account_reference", "event_digest", name="uq_payment_provider_event_digest"),
        ForeignKeyConstraint(
            ["tenant_id", "receipt_id"],
            ["payment_receipts.tenant_id", "payment_receipts.id"],
            name="fk_payment_provider_events_receipt_tenant",
        ),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    receipt_id = Column(String, nullable=True, index=True)
    provider = Column(String(32), nullable=False)
    account_reference = Column(String(128), nullable=False)
    event_id = Column(String(128), nullable=False)
    event_digest = Column(String(64), nullable=False)
    event_type = Column(String(64), nullable=False)
    received_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class PaymentReceipt(Base):
    __tablename__ = "payment_receipts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_payment_receipts_tenant_id"),
        UniqueConstraint("tenant_id", "provider", "provider_account_reference", "provider_payment_hash", name="uq_payment_receipts_provider_payment"),
        ForeignKeyConstraint(
            ["tenant_id", "receivable_id"],
            ["receivables.tenant_id", "receivables.id"],
            name="fk_payment_receipts_receivable_tenant",
        ),
        CheckConstraint("status IN ('received', 'reversed')", name="ck_payment_receipts_status"),
        CheckConstraint("amount > 0", name="ck_payment_receipts_amount"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    receivable_id = Column(String, nullable=False, index=True)
    provider = Column(String(32), nullable=False)
    provider_account_reference = Column(String(128), nullable=False)
    provider_payment_hash = Column(String(64), nullable=False)
    amount = Column(Numeric(14, 2), nullable=False)
    currency = Column(String(3), nullable=False)
    status = Column(String(16), nullable=False, default="received")
    provider_occurred_at = Column(DateTime(timezone=True), nullable=False)
    reversed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
