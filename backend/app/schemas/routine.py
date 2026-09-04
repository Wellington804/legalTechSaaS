from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.workspace import WorkspaceInput, WorkspaceSchema, required_text, safe_document_text


class ChecklistCreate(WorkspaceInput):
    key: Literal["intake", "documents", "hearing"]
    request_id: UUID


class OutcomeCreate(WorkspaceInput):
    request_id: UUID
    title: str = Field(min_length=2, max_length=200)
    content_text: str = Field(min_length=1, max_length=5000)

    @field_validator("title", "content_text")
    @classmethod
    def validate_text(cls, value):
        return safe_document_text(required_text(value, "texto"))


class ReminderSet(WorkspaceInput):
    remind_at: datetime
    expected_revision: int = Field(ge=1)

    @field_validator("remind_at")
    @classmethod
    def require_timezone(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Informe data com fuso horario.")
        return value


class ReminderResponse(WorkspaceSchema):
    id: str
    task_id: str
    task_title: str
    case_id: str | None
    remind_at: datetime
    status: Literal["scheduled", "due", "cancelled"]
    push_status: Literal["not_requested", "pending", "accepted", "failed", "unknown", "unavailable"]
    acknowledged_at: datetime | None
