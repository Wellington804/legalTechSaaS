"""API contracts for the judicial control desk.

All inbound source material is intentionally bounded. These contracts carry a
source record or a human suggestion; they never represent an inferred final
deadline.
"""

import json
from datetime import datetime, timezone
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


MAX_METADATA_BYTES = 20_000
SUPPORTED_DATAJUD_TRIBUNALS = frozenset(
    {"stj", "tst", "tse", "stm"}
    | {f"trf{i}" for i in range(1, 7)}
    | {f"trt{i}" for i in range(1, 25)}
    | {
        "tjac", "tjal", "tjam", "tjap", "tjba", "tjce", "tjdft", "tjes", "tjgo", "tjma",
        "tjmg", "tjms", "tjmt", "tjpa", "tjpb", "tjpe", "tjpi", "tjpr", "tjrj", "tjrn",
        "tjro", "tjrr", "tjrs", "tjsc", "tjse", "tjsp", "tjto", "tjmmg", "tjmrs", "tjmsp",
    }
    | {f"tre-{uf}" for uf in "ac al am ap ba ce dft es go ma mg ms mt pa pb pe pi pr rj rn ro rr rs sc se sp to".split()}
)


class ControladoriaSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid", str_strip_whitespace=True)


def _normalize_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"https", "http"} or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError("source_url deve ser uma URL HTTP(S) valida")
    return value


def _timezone_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("data e hora devem informar fuso horario")
    return value.astimezone(timezone.utc)


class MonitoringSubscriptionCreate(ControladoriaSchema):
    case_id: str = Field(min_length=1, max_length=64)
    tribunal: str | None = Field(default=None, min_length=2, max_length=20)

    @field_validator("tribunal")
    @classmethod
    def valid_tribunal(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.lower()
        if normalized not in SUPPORTED_DATAJUD_TRIBUNALS:
            raise ValueError("tribunal DataJud nao suportado")
        return normalized


class MonitoringSubscriptionUpdate(ControladoriaSchema):
    status: Literal["active", "paused", "disabled"]


class MonitoringSubscriptionResponse(ControladoriaSchema):
    id: str
    case_id: str
    source_kind: Literal["datajud", "escavador"]
    tribunal: str
    process_number: str
    status: Literal["active", "paused", "disabled"]
    last_checked_at: datetime | None
    last_success_at: datetime | None
    last_error_code: str | None
    created_at: datetime
    updated_at: datetime


class JudicialEventCreate(ControladoriaSchema):
    case_id: str = Field(min_length=1, max_length=64)
    subscription_id: str | None = Field(default=None, min_length=1, max_length=64)
    source_kind: Literal["manual", "datajud", "escavador"]
    source_event_id: str = Field(min_length=1, max_length=200)
    source_url: str = Field(min_length=8, max_length=2048)
    title: str = Field(min_length=2, max_length=500)
    source_content: str | None = Field(default=None, max_length=20_000)
    source_metadata: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime | None = None
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("source_url")
    @classmethod
    def valid_source_url(cls, value: str) -> str:
        return _normalize_url(value)

    @field_validator("occurred_at", "retrieved_at")
    @classmethod
    def timezone_aware(cls, value: datetime | None) -> datetime | None:
        return _timezone_aware(value) if value else None

    @field_validator("source_metadata")
    @classmethod
    def bounded_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        try:
            encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        except (TypeError, ValueError) as exc:
            raise ValueError("source_metadata deve conter apenas valores JSON") from exc
        if len(encoded.encode("utf-8")) > MAX_METADATA_BYTES:
            raise ValueError("source_metadata excede 20 KB")
        return value

    @model_validator(mode="after")
    def subscription_matches_source(self):
        if self.source_kind == "manual" and self.subscription_id is not None:
            raise ValueError("evento manual nao pode apontar para acompanhamento automatico")
        return self


class JudicialEventTriage(ControladoriaSchema):
    status: Literal["reviewed", "discarded"]
    note: str | None = Field(default=None, max_length=5_000)

    @model_validator(mode="after")
    def discard_requires_reason(self):
        if self.status == "discarded" and (not self.note or len(self.note.strip()) < 3):
            raise ValueError("descarte exige justificativa")
        return self


class JudicialEventResponse(ControladoriaSchema):
    id: str
    case_id: str
    subscription_id: str | None
    source_kind: Literal["manual", "datajud", "escavador"]
    source_event_id: str
    source_url: str
    title: str
    source_content: str | None
    source_metadata: dict[str, Any]
    occurred_at: datetime | None
    retrieved_at: datetime
    triage_status: Literal["pending", "reviewed", "discarded"]
    triage_note: str | None
    triaged_at: datetime | None
    triaged_by_user_id: str | None
    created_at: datetime
    updated_at: datetime


class DeadlineSuggestionCreate(ControladoriaSchema):
    event_id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=2, max_length=300)
    suggested_due_at: datetime
    suggested_basis: str = Field(min_length=5, max_length=5_000)
    assigned_user_id: str | None = Field(default=None, min_length=1, max_length=64)

    @field_validator("suggested_due_at")
    @classmethod
    def valid_due_at(cls, value: datetime) -> datetime:
        return _timezone_aware(value)


class DeadlineDecision(ControladoriaSchema):
    decision: Literal["approved", "rejected"]
    note: str = Field(min_length=3, max_length=5_000)


class DeadlineReviewResponse(ControladoriaSchema):
    id: str
    case_id: str
    event_id: str
    title: str
    suggested_due_at: datetime
    suggested_basis: str
    assigned_user_id: str | None
    status: Literal["suggested", "approved", "rejected"]
    suggested_by_user_id: str
    reviewed_by_user_id: str | None
    reviewed_at: datetime | None
    review_note: str | None
    task_id: str | None
    created_at: datetime
    updated_at: datetime
    event: JudicialEventResponse


class WorkflowTemplateStepCreate(ControladoriaSchema):
    position: int = Field(ge=1, le=100)
    title: str = Field(min_length=2, max_length=300)
    instructions: str | None = Field(default=None, max_length=5_000)
    is_required: bool = True


class WorkflowTemplateCreate(ControladoriaSchema):
    name: str = Field(min_length=2, max_length=200)
    case_type: str | None = Field(default=None, max_length=100)
    version: int = Field(default=1, ge=1, le=10_000)
    description: str | None = Field(default=None, max_length=5_000)
    steps: list[WorkflowTemplateStepCreate] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def unique_step_positions(self):
        positions = [step.position for step in self.steps]
        if len(positions) != len(set(positions)):
            raise ValueError("posicoes de checklist devem ser unicas")
        return self


class WorkflowTemplateStepResponse(WorkflowTemplateStepCreate):
    id: str
    template_id: str
    created_at: datetime


class WorkflowTemplateResponse(ControladoriaSchema):
    id: str
    name: str
    case_type: str | None
    version: int
    description: str | None
    is_active: bool
    created_at: datetime
    steps: list[WorkflowTemplateStepResponse] = Field(default_factory=list)


class WorkflowRunCreate(ControladoriaSchema):
    case_id: str = Field(min_length=1, max_length=64)
    template_id: str = Field(min_length=1, max_length=64)


class WorkflowRunItemUpdate(ControladoriaSchema):
    status: Literal["completed", "skipped"]
    resolution_note: str | None = Field(default=None, max_length=5_000)
    expected_revision: int = Field(ge=1)

    @model_validator(mode="after")
    def skipped_requires_reason(self):
        if self.status == "skipped" and (not self.resolution_note or len(self.resolution_note.strip()) < 3):
            raise ValueError("item ignorado exige justificativa")
        return self


class WorkflowRunComplete(ControladoriaSchema):
    expected_revision: int = Field(ge=1)


class WorkflowRunItemResponse(ControladoriaSchema):
    id: str
    workflow_run_id: str
    position: int
    title: str
    instructions: str | None
    is_required: bool
    status: Literal["pending", "completed", "skipped"]
    resolved_by_user_id: str | None
    resolved_at: datetime | None
    resolution_note: str | None
    revision: int
    created_at: datetime
    updated_at: datetime


class WorkflowRunResponse(ControladoriaSchema):
    id: str
    case_id: str
    template_id: str
    template_name: str
    template_version: int
    status: Literal["open", "completed", "cancelled"]
    started_by_user_id: str
    completed_by_user_id: str | None
    completed_at: datetime | None
    revision: int
    created_at: datetime
    updated_at: datetime
    items: list[WorkflowRunItemResponse] = Field(default_factory=list)


class ControladoriaListResponse(ControladoriaSchema):
    items: list[Any]
    limit: int
