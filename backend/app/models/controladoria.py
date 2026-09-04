"""Persisted, tenant-scoped judicial control desk records.

This module intentionally does not calculate deadlines or dispatch work. A
``ControladoriaDeadlineReview`` only creates a workspace deadline task after
two distinct authorized users record explicit approvals.
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
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    text,
)

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ControladoriaMonitoringSubscription(Base):
    __tablename__ = "controladoria_monitoring_subscriptions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_controladoria_monitoring_subscriptions_tenant_id"),
        UniqueConstraint(
            "tenant_id", "case_id", "source_kind", "tribunal",
            name="uq_controladoria_monitoring_subscriptions_case_source",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["workspace_cases.tenant_id", "workspace_cases.id"],
            name="fk_controladoria_monitoring_subscriptions_case_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "created_by_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_controladoria_monitoring_subscriptions_creator_tenant",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "updated_by_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_controladoria_monitoring_subscriptions_updater_tenant",
        ),
        CheckConstraint(
            "source_kind IN ('datajud', 'escavador', 'djen', 'domicilio', 'tribunal_api')",
            name="ck_controladoria_monitoring_subscriptions_source_kind",
        ),
        CheckConstraint(
            "status IN ('active', 'paused', 'disabled')",
            name="ck_controladoria_monitoring_subscriptions_status",
        ),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    case_id = Column(String, nullable=False, index=True)
    source_kind = Column(String(16), nullable=False, default="datajud")
    provider_subscription_id = Column(String(128), nullable=True)
    provider_cursor = Column(String(512), nullable=True)
    tribunal = Column(String(20), nullable=False)
    process_number = Column(String(20), nullable=False)
    status = Column(String(16), nullable=False, default="active", index=True)
    last_checked_at = Column(DateTime(timezone=True), nullable=True)
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    last_error_code = Column(String(100), nullable=True)
    created_by_user_id = Column(String, nullable=False)
    updated_by_user_id = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class ControladoriaJudicialEvent(Base):
    __tablename__ = "controladoria_judicial_events"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_controladoria_judicial_events_tenant_id"),
        UniqueConstraint("tenant_id", "dedupe_key", name="uq_controladoria_judicial_events_dedupe"),
        ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["workspace_cases.tenant_id", "workspace_cases.id"],
            name="fk_controladoria_judicial_events_case_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "subscription_id"],
            ["controladoria_monitoring_subscriptions.tenant_id", "controladoria_monitoring_subscriptions.id"],
            name="fk_controladoria_judicial_events_subscription_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "created_by_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_controladoria_judicial_events_creator_tenant",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "triaged_by_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_controladoria_judicial_events_triager_tenant",
        ),
        CheckConstraint(
            "source_kind IN ('manual', 'datajud', 'escavador', 'djen', 'domicilio', 'tribunal_api')",
            name="ck_controladoria_judicial_events_source_kind",
        ),
        CheckConstraint(
            "triage_status IN ('pending', 'reviewed', 'discarded')",
            name="ck_controladoria_judicial_events_triage_status",
        ),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    case_id = Column(String, nullable=False, index=True)
    subscription_id = Column(String, nullable=True, index=True)
    source_kind = Column(String(16), nullable=False)
    source_event_id = Column(String(200), nullable=False)
    dedupe_key = Column(String(64), nullable=False)
    source_url = Column(String(2048), nullable=False)
    title = Column(String(500), nullable=False)
    source_content = Column(Text, nullable=True)
    source_metadata = Column(JSON, nullable=False, default=dict)
    occurred_at = Column(DateTime(timezone=True), nullable=True, index=True)
    retrieved_at = Column(DateTime(timezone=True), nullable=False, index=True)
    triage_status = Column(String(16), nullable=False, default="pending", index=True)
    triage_note = Column(Text, nullable=True)
    triaged_at = Column(DateTime(timezone=True), nullable=True)
    triaged_by_user_id = Column(String, nullable=True)
    created_by_user_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class ControladoriaDeadlineReview(Base):
    __tablename__ = "controladoria_deadline_reviews"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_controladoria_deadline_reviews_tenant_id"),
        UniqueConstraint("tenant_id", "event_id", name="uq_controladoria_deadline_reviews_event"),
        ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["workspace_cases.tenant_id", "workspace_cases.id"],
            name="fk_controladoria_deadline_reviews_case_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "event_id"],
            ["controladoria_judicial_events.tenant_id", "controladoria_judicial_events.id"],
            name="fk_controladoria_deadline_reviews_event_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "assigned_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_controladoria_deadline_reviews_assignee_tenant",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "suggested_by_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_controladoria_deadline_reviews_suggester_tenant",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "reviewed_by_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_controladoria_deadline_reviews_reviewer_tenant",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "task_id"],
            ["workspace_tasks.tenant_id", "workspace_tasks.id"],
            name="fk_controladoria_deadline_reviews_task_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "rule_id"],
            ["controladoria_deadline_rules.tenant_id", "controladoria_deadline_rules.id"],
            name="fk_controladoria_deadline_reviews_rule_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "first_approved_by_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_controladoria_deadline_reviews_first_approver_tenant",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "second_approved_by_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_controladoria_deadline_reviews_second_approver_tenant",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "source_stale_event_id"],
            ["controladoria_judicial_events.tenant_id", "controladoria_judicial_events.id"],
            name="fk_controladoria_deadline_reviews_stale_event_tenant",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "status IN ('suggested', 'first_approved', 'approved', 'rejected')",
            name="ck_controladoria_deadline_reviews_status",
        ),
        CheckConstraint(
            "(approval_policy_version = 1 AND status = 'approved' AND reviewed_at IS NOT NULL "
            "AND reviewed_by_user_id IS NOT NULL AND task_id IS NOT NULL) OR "
            "(approval_policy_version = 2 AND status = 'suggested' AND task_id IS NULL "
            "AND first_approved_by_user_id IS NULL AND second_approved_by_user_id IS NULL) OR "
            "(approval_policy_version = 2 AND status = 'first_approved' AND task_id IS NULL "
            "AND first_approved_by_user_id IS NOT NULL AND first_approved_at IS NOT NULL "
            "AND first_approval_note IS NOT NULL AND first_approval_calculation_sha256 IS NOT NULL "
            "AND second_approved_by_user_id IS NULL) OR "
            "(approval_policy_version = 2 AND status = 'approved' AND task_id IS NOT NULL "
            "AND first_approved_by_user_id IS NOT NULL AND first_approved_at IS NOT NULL "
            "AND second_approved_by_user_id IS NOT NULL AND second_approved_at IS NOT NULL "
            "AND first_approval_note IS NOT NULL AND second_approval_note IS NOT NULL "
            "AND first_approval_calculation_sha256 = second_approval_calculation_sha256 "
            "AND reviewed_by_user_id = second_approved_by_user_id AND reviewed_at IS NOT NULL "
            "AND first_approved_by_user_id <> second_approved_by_user_id) OR "
            "(approval_policy_version = 2 AND status = 'rejected' AND task_id IS NULL "
            "AND reviewed_by_user_id IS NOT NULL AND reviewed_at IS NOT NULL AND review_note IS NOT NULL)",
            name="ck_controladoria_deadline_reviews_human_approval",
        ),
        CheckConstraint(
            "(source_stale_at IS NULL) = (source_stale_event_id IS NULL)",
            name="ck_controladoria_deadline_reviews_stale_source",
        ),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    case_id = Column(String, nullable=False, index=True)
    event_id = Column(String, nullable=False, index=True)
    title = Column(String(300), nullable=False)
    suggested_due_at = Column(DateTime(timezone=True), nullable=False, index=True)
    suggested_basis = Column(Text, nullable=False)
    assigned_user_id = Column(String, nullable=True)
    rule_id = Column(String, nullable=True)
    rule_version = Column(Integer, nullable=True)
    calculation = Column(JSON, nullable=True)
    calculation_revision = Column(Integer, nullable=False, default=1)
    approval_policy_version = Column(Integer, nullable=False, default=2)
    status = Column(String(16), nullable=False, default="suggested", index=True)
    suggested_by_user_id = Column(String, nullable=False)
    first_approved_by_user_id = Column(String, nullable=True)
    first_approved_at = Column(DateTime(timezone=True), nullable=True)
    first_approval_note = Column(Text, nullable=True)
    first_approval_calculation_sha256 = Column(String(64), nullable=True)
    second_approved_by_user_id = Column(String, nullable=True)
    second_approved_at = Column(DateTime(timezone=True), nullable=True)
    second_approval_note = Column(Text, nullable=True)
    second_approval_calculation_sha256 = Column(String(64), nullable=True)
    source_stale_at = Column(DateTime(timezone=True), nullable=True)
    source_stale_event_id = Column(String, nullable=True)
    reviewed_by_user_id = Column(String, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    review_note = Column(Text, nullable=True)
    task_id = Column(String, nullable=True, unique=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class ControladoriaDeadlineRule(Base):
    __tablename__ = "controladoria_deadline_rules"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_controladoria_deadline_rules_tenant_id"),
        UniqueConstraint(
            "tenant_id", "rule_key", "version",
            name="uq_controladoria_deadline_rules_key_version",
        ),
        Index(
            "uq_controladoria_deadline_rules_active_key",
            "tenant_id",
            "rule_key",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        ForeignKeyConstraint(
            ["tenant_id", "created_by_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_controladoria_deadline_rules_creator_tenant",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "reviewed_by_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_controladoria_deadline_rules_reviewer_tenant",
        ),
        CheckConstraint("days > 0 AND days <= 3650", name="ck_controladoria_deadline_rules_days"),
        CheckConstraint(
            "counting_method IN ('business_days', 'calendar_days')",
            name="ck_controladoria_deadline_rules_counting_method",
        ),
        CheckConstraint(
            "start_mode IN ('next_business_day', 'same_business_day', 'next_calendar_day')",
            name="ck_controladoria_deadline_rules_start_mode",
        ),
        CheckConstraint(
            "due_adjustment IN ('none', 'next_business_day')",
            name="ck_controladoria_deadline_rules_due_adjustment",
        ),
        CheckConstraint(
            "status IN ('draft', 'active', 'rejected', 'retired')",
            name="ck_controladoria_deadline_rules_status",
        ),
        CheckConstraint(
            "(status = 'draft' AND reviewed_by_user_id IS NULL AND reviewed_at IS NULL) OR "
            "(status IN ('active', 'rejected', 'retired') AND reviewed_by_user_id IS NOT NULL "
            "AND reviewed_at IS NOT NULL AND reviewed_by_user_id <> created_by_user_id)",
            name="ck_controladoria_deadline_rules_reviewed",
        ),
        CheckConstraint("due_hour BETWEEN 0 AND 23", name="ck_controladoria_deadline_rules_due_hour"),
        CheckConstraint("due_minute BETWEEN 0 AND 59", name="ck_controladoria_deadline_rules_due_minute"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    rule_key = Column(String(100), nullable=False)
    version = Column(Integer, nullable=False)
    rite = Column(String(100), nullable=False, index=True)
    act_type = Column(String(100), nullable=False, index=True)
    tribunal = Column(String(20), nullable=False, index=True)
    local_code = Column(String(100), nullable=True)
    days = Column(Integer, nullable=False)
    counting_method = Column(String(20), nullable=False)
    start_mode = Column(String(30), nullable=False)
    due_adjustment = Column(String(30), nullable=False, default="next_business_day")
    timezone_name = Column(String(64), nullable=False, default="America/Sao_Paulo")
    due_hour = Column(Integer, nullable=False, default=23)
    due_minute = Column(Integer, nullable=False, default=59)
    legal_sources = Column(JSON, nullable=False, default=list)
    status = Column(String(16), nullable=False, default="draft", index=True)
    effective_from = Column(Date, nullable=False)
    effective_until = Column(Date, nullable=True)
    created_by_user_id = Column(String, nullable=False)
    reviewed_by_user_id = Column(String, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    review_note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class ControladoriaCalendarException(Base):
    __tablename__ = "controladoria_calendar_exceptions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_controladoria_calendar_exceptions_tenant_id"),
        UniqueConstraint(
            "tenant_id", "scope_kind", "scope_code", "starts_on", "ends_on", "kind",
            name="uq_controladoria_calendar_exceptions_scope_period",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "created_by_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_controladoria_calendar_exceptions_creator_tenant",
        ),
        CheckConstraint(
            "scope_kind IN ('national', 'tribunal', 'local')",
            name="ck_controladoria_calendar_exceptions_scope_kind",
        ),
        CheckConstraint(
            "kind IN ('holiday', 'suspension')",
            name="ck_controladoria_calendar_exceptions_kind",
        ),
        CheckConstraint("ends_on >= starts_on", name="ck_controladoria_calendar_exceptions_period"),
        CheckConstraint(
            "(scope_kind = 'national' AND scope_code = 'BR') OR "
            "(scope_kind IN ('tribunal', 'local') AND length(scope_code) >= 2)",
            name="ck_controladoria_calendar_exceptions_scope_code",
        ),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    scope_kind = Column(String(16), nullable=False, index=True)
    scope_code = Column(String(100), nullable=False, index=True)
    kind = Column(String(16), nullable=False)
    name = Column(String(200), nullable=False)
    starts_on = Column(Date, nullable=False, index=True)
    ends_on = Column(Date, nullable=False, index=True)
    source_url = Column(String(2048), nullable=False)
    source_name = Column(String(300), nullable=False)
    created_by_user_id = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class ControladoriaWorkflowTemplate(Base):
    __tablename__ = "controladoria_workflow_templates"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_controladoria_workflow_templates_tenant_id"),
        UniqueConstraint(
            "tenant_id", "name", "version",
            name="uq_controladoria_workflow_templates_name_version",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "created_by_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_controladoria_workflow_templates_creator_tenant",
        ),
        CheckConstraint("version > 0", name="ck_controladoria_workflow_templates_version"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    case_type = Column(String(100), nullable=True, index=True)
    version = Column(Integer, nullable=False, default=1)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_by_user_id = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class ControladoriaWorkflowTemplateStep(Base):
    __tablename__ = "controladoria_workflow_template_steps"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_controladoria_workflow_template_steps_tenant_id"),
        UniqueConstraint(
            "tenant_id", "template_id", "position",
            name="uq_controladoria_workflow_template_steps_position",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "template_id"],
            ["controladoria_workflow_templates.tenant_id", "controladoria_workflow_templates.id"],
            name="fk_controladoria_workflow_template_steps_template_tenant",
            ondelete="CASCADE",
        ),
        CheckConstraint("position > 0", name="ck_controladoria_workflow_template_steps_position"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    template_id = Column(String, nullable=False, index=True)
    position = Column(Integer, nullable=False)
    title = Column(String(300), nullable=False)
    instructions = Column(Text, nullable=True)
    is_required = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class ControladoriaWorkflowRun(Base):
    __tablename__ = "controladoria_workflow_runs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_controladoria_workflow_runs_tenant_id"),
        ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["workspace_cases.tenant_id", "workspace_cases.id"],
            name="fk_controladoria_workflow_runs_case_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "template_id"],
            ["controladoria_workflow_templates.tenant_id", "controladoria_workflow_templates.id"],
            name="fk_controladoria_workflow_runs_template_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "started_by_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_controladoria_workflow_runs_starter_tenant",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "completed_by_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_controladoria_workflow_runs_completer_tenant",
        ),
        CheckConstraint(
            "status IN ('open', 'completed', 'cancelled')",
            name="ck_controladoria_workflow_runs_status",
        ),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    case_id = Column(String, nullable=False, index=True)
    template_id = Column(String, nullable=False, index=True)
    template_name = Column(String(200), nullable=False)
    template_version = Column(Integer, nullable=False)
    status = Column(String(16), nullable=False, default="open", index=True)
    started_by_user_id = Column(String, nullable=False)
    completed_by_user_id = Column(String, nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    revision = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class ControladoriaWorkflowRunItem(Base):
    __tablename__ = "controladoria_workflow_run_items"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_controladoria_workflow_run_items_tenant_id"),
        UniqueConstraint(
            "tenant_id", "workflow_run_id", "position",
            name="uq_controladoria_workflow_run_items_position",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "workflow_run_id"],
            ["controladoria_workflow_runs.tenant_id", "controladoria_workflow_runs.id"],
            name="fk_controladoria_workflow_run_items_run_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "resolved_by_user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_controladoria_workflow_run_items_resolver_tenant",
        ),
        CheckConstraint("position > 0", name="ck_controladoria_workflow_run_items_position"),
        CheckConstraint(
            "status IN ('pending', 'completed', 'skipped')",
            name="ck_controladoria_workflow_run_items_status",
        ),
        CheckConstraint(
            "(status = 'pending' AND resolved_at IS NULL AND resolved_by_user_id IS NULL) "
            "OR (status IN ('completed', 'skipped') AND resolved_at IS NOT NULL AND resolved_by_user_id IS NOT NULL)",
            name="ck_controladoria_workflow_run_items_resolution",
        ),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    workflow_run_id = Column(String, nullable=False, index=True)
    position = Column(Integer, nullable=False)
    title = Column(String(300), nullable=False)
    instructions = Column(Text, nullable=True)
    is_required = Column(Boolean, nullable=False, default=True)
    status = Column(String(16), nullable=False, default="pending", index=True)
    resolved_by_user_id = Column(String, nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolution_note = Column(Text, nullable=True)
    revision = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
