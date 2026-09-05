"""Validated contracts for descriptive, non-predictive jurimetry."""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator

from app.schemas.controladoria import SUPPORTED_DATAJUD_TRIBUNALS


MAX_PERIOD_DAYS = 366
SampleLimit = Literal[50, 100, 200]


class JurimetrySchema(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class JurimetryFilters(JurimetrySchema):
    date_from: date
    date_to: date
    degree: str | None = Field(default=None, min_length=1, max_length=16, pattern=r"^[A-Za-z0-9_-]+$")
    class_code: int | None = Field(default=None, ge=1, le=2_147_483_647)
    subject_code: int | None = Field(default=None, ge=1, le=2_147_483_647)
    court_unit_code: int | None = Field(default=None, ge=1, le=2_147_483_647)

    @field_validator("degree")
    @classmethod
    def normalize_degree(cls, value: str | None) -> str | None:
        return value.upper() if value else None

    @model_validator(mode="after")
    def bounded_period(self) -> "JurimetryFilters":
        days = (self.date_to - self.date_from).days
        if days < 0:
            raise ValueError("A data final deve ser igual ou posterior à data inicial.")
        if days >= MAX_PERIOD_DAYS:
            raise ValueError(f"O período máximo de consulta é de {MAX_PERIOD_DAYS} dias.")
        return self


class JurimetryAnalysisRequest(JurimetrySchema):
    request_id: uuid.UUID
    tribunal: str = Field(min_length=2, max_length=20)
    filters: JurimetryFilters
    sample_limit: SampleLimit = 100
    persist_snapshot: StrictBool = False

    @field_validator("tribunal")
    @classmethod
    def supported_tribunal(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in SUPPORTED_DATAJUD_TRIBUNALS:
            raise ValueError("Tribunal não suportado pela integração DataJud.")
        return normalized


class MetricBucket(JurimetrySchema):
    label: str
    code: str | None = None
    count: int = Field(ge=0)
    sample_share_percent: float = Field(ge=0, le=100)


class MetricCoverage(JurimetrySchema):
    filing_date: int = Field(ge=0)
    degree: int = Field(ge=0)
    case_class: int = Field(ge=0)
    subjects: int = Field(ge=0)
    court_unit: int = Field(ge=0)
    source_update: int = Field(ge=0)


class DescriptiveMetrics(JurimetrySchema):
    filings_by_month: list[MetricBucket]
    cases_by_degree: list[MetricBucket]
    cases_by_class: list[MetricBucket]
    subject_occurrences: list[MetricBucket]
    cases_by_court_unit: list[MetricBucket]
    coverage: MetricCoverage


class JurimetryAnalysisResponse(JurimetrySchema):
    request_id: uuid.UUID
    snapshot_id: str | None = None
    persisted: bool
    tribunal: str
    filters: JurimetryFilters
    sample_limit: SampleLimit
    sample_size: int = Field(ge=0)
    total_matches: int | None = Field(default=None, ge=0)
    total_relation: Literal["eq", "gte", "unknown"]
    source_name: str
    source_url: str
    queried_at: datetime
    source_updated_at: datetime | None = None
    universe: str
    metrics: DescriptiveMetrics
    limitations: list[str]


class JurimetrySnapshotList(JurimetrySchema):
    items: list[JurimetryAnalysisResponse]


class JurimetryOptions(JurimetrySchema):
    provider_available: bool
    source_name: str
    source_documentation_url: str
    tribunals: list[str]
    sample_limits: list[SampleLimit]
    max_period_days: int
    supported_filters: list[str]
