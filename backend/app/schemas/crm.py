from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


OpportunityStage = Literal["new", "qualified", "proposal", "won", "lost"]
OpportunitySource = Literal["manual", "intake", "referral", "website", "whatsapp", "email", "other"]


def clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def normalize_action_at(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("next_action_at deve incluir fuso horario")
    return value.astimezone(timezone.utc)


class CRMInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OpportunityCreate(CRMInput):
    request_id: UUID
    title: str = Field(min_length=2, max_length=200)
    stage: OpportunityStage = "new"
    source: OpportunitySource = "manual"
    estimated_value: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    next_action: str | None = Field(default=None, max_length=500)
    next_action_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=5000)
    client_id: str | None = Field(default=None, min_length=1, max_length=64)
    case_id: str | None = Field(default=None, min_length=1, max_length=64)
    intake_id: str | None = Field(default=None, min_length=1, max_length=64)
    owner_user_id: str | None = Field(default=None, min_length=1, max_length=64)

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("title e obrigatorio")
        return value

    @field_validator("next_action", "notes")
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        return clean_optional_text(value)

    @field_validator("next_action_at")
    @classmethod
    def valid_action_at(cls, value: datetime | None) -> datetime | None:
        return normalize_action_at(value)

    @model_validator(mode="after")
    def action_has_description(self):
        if self.next_action_at and not self.next_action:
            raise ValueError("informe a proxima acao quando houver data")
        return self


class OpportunityUpdate(CRMInput):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    stage: OpportunityStage | None = None
    source: OpportunitySource | None = None
    estimated_value: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    next_action: str | None = Field(default=None, max_length=500)
    next_action_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=5000)
    client_id: str | None = Field(default=None, min_length=1, max_length=64)
    case_id: str | None = Field(default=None, min_length=1, max_length=64)
    intake_id: str | None = Field(default=None, min_length=1, max_length=64)
    owner_user_id: str | None = Field(default=None, min_length=1, max_length=64)
    expected_revision: int = Field(ge=1)

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("title e obrigatorio")
        return value

    @field_validator("next_action", "notes")
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        return clean_optional_text(value)

    @field_validator("next_action_at")
    @classmethod
    def valid_action_at(cls, value: datetime | None) -> datetime | None:
        return normalize_action_at(value)

    @model_validator(mode="after")
    def required_fields_cannot_be_cleared(self):
        for field_name in ("title", "stage", "source"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} nao pode ser nulo")
        return self


class OpportunityArchive(CRMInput):
    expected_revision: int = Field(ge=1)


class OpportunityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    stage: OpportunityStage
    source: OpportunitySource
    estimated_value: Decimal | None
    next_action: str | None
    next_action_at: datetime | None
    notes: str | None
    client_id: str | None
    case_id: str | None
    intake_id: str | None
    owner_user_id: str | None
    revision: int
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class OpportunityListResponse(BaseModel):
    items: list[OpportunityResponse]
    limit: int
