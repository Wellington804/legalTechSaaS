from datetime import datetime
from typing import Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


UFS = frozenset({"AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"})
EnrollmentType = Literal["principal", "supplementary", "transfer", "other"]
EnrollmentStatus = Literal["planning", "gathering", "submitted", "awaiting_response", "completed", "paused"]


class OABInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OABResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)


def optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


class OABSourceResponse(OABResponse):
    uf: str
    state_name: str
    official_url: str
    directory_url: str
    provision_url: str
    source_version: str
    source_checked_at: datetime
    notice: str


class OABSourceList(OABResponse):
    items: list[OABSourceResponse]
    count: int


class OABEnrollmentCreate(OABInput):
    request_id: uuid.UUID
    uf: str
    enrollment_type: EnrollmentType
    status: EnrollmentStatus = "planning"
    protocol: str | None = Field(default=None, max_length=120)

    @field_validator("uf")
    @classmethod
    def valid_uf(cls, value: str) -> str:
        value = value.strip().upper()
        if value not in UFS:
            raise ValueError("UF invalida")
        return value

    @field_validator("protocol")
    @classmethod
    def clean_protocol(cls, value: str | None) -> str | None:
        return optional_text(value)


class OABEnrollmentUpdate(OABInput):
    expected_revision: int = Field(ge=1)
    uf: str | None = None
    enrollment_type: EnrollmentType | None = None
    status: EnrollmentStatus | None = None
    protocol: str | None = Field(default=None, max_length=120)

    @field_validator("uf")
    @classmethod
    def valid_uf(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().upper()
        if value not in UFS:
            raise ValueError("UF invalida")
        return value

    @field_validator("protocol")
    @classmethod
    def clean_protocol(cls, value: str | None) -> str | None:
        return optional_text(value)

    @model_validator(mode="after")
    def has_change(self):
        if not (self.model_fields_set - {"expected_revision"}):
            raise ValueError("informe ao menos uma alteracao")
        return self


class OABChecklistItemCreate(OABInput):
    request_id: uuid.UUID
    title: str = Field(min_length=1, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)
    is_completed: bool = False

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("titulo e obrigatorio")
        return value

    @field_validator("notes")
    @classmethod
    def clean_notes(cls, value: str | None) -> str | None:
        return optional_text(value)


class OABChecklistItemUpdate(OABInput):
    expected_revision: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)
    is_completed: bool | None = None

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("titulo e obrigatorio")
        return value

    @field_validator("notes")
    @classmethod
    def clean_notes(cls, value: str | None) -> str | None:
        return optional_text(value)

    @model_validator(mode="after")
    def has_change(self):
        if not (self.model_fields_set - {"expected_revision"}):
            raise ValueError("informe ao menos uma alteracao")
        return self


class OABChecklistItemResponse(OABResponse):
    id: str
    enrollment_id: str
    title: str
    notes: str | None
    is_completed: bool
    revision: int
    created_at: datetime
    updated_at: datetime


class OABEnrollmentResponse(OABResponse):
    id: str
    uf: str
    enrollment_type: EnrollmentType
    status: EnrollmentStatus
    protocol: str | None
    source_url: str
    source_version: str
    source_checked_at: datetime
    revision: int
    created_at: datetime
    updated_at: datetime
    checklist: list[OABChecklistItemResponse] = Field(default_factory=list)
    source_notice: str
    provision_url: str


class OABEnrollmentList(OABResponse):
    items: list[OABEnrollmentResponse]
    count: int
