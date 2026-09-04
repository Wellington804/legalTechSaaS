"""Strict HTTP contracts for calendar OAuth/sync and provider TCO."""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


CalendarProvider = Literal["google", "microsoft"]


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OrmResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime deve incluir fuso horario")
    return value.astimezone(timezone.utc)


class OAuthStart(StrictInput):
    redirect_path: str = Field(default="/dashboard/tasks", min_length=1, max_length=300, pattern=r"^/[A-Za-z0-9/_?=&.-]*$")


class OAuthAuthorization(StrictInput):
    authorization_url: str
    expires_at: datetime


class CalendarConnectionResponse(OrmResponse):
    id: str
    provider: CalendarProvider
    provider_account_label: str | None
    selected_calendar_label: str | None
    last_sync_at: datetime | None
    last_error: str | None
    status: Literal["active", "reauthorization_required", "revoked"]
    watch_expires_at: datetime | None
    revision: int


class ProviderCalendar(StrictInput):
    id: str
    name: str
    primary: bool = False
    can_write: bool = False


class CalendarSelection(StrictInput):
    calendar_id: str = Field(min_length=1, max_length=2048)
    expected_revision: int = Field(ge=1)


class CalendarTaskSelection(StrictInput):
    task_ids: list[str] = Field(min_length=1, max_length=100)

    @field_validator("task_ids")
    @classmethod
    def unique_tasks(cls, values: list[str]) -> list[str]:
        if any(not value or len(value) > 64 for value in values):
            raise ValueError("task_id invalido")
        if len(set(values)) != len(values):
            raise ValueError("task_ids duplicados")
        return values


class CalendarTaskLinkResponse(OrmResponse):
    id: str
    connection_id: str
    task_id: str
    provider_etag: str | None
    last_synced_at: datetime | None
    status: Literal["active", "tombstoned", "conflict", "delete_pending"]


class CalendarConflictSide(StrictInput):
    hash: str
    title: str | None
    starts_at: datetime | None
    location: str | None
    notes: str | None
    deleted: bool = False
    revision: int | None = None


class CalendarConflictResponse(OrmResponse):
    id: str
    connection_id: str
    task_id: str
    reason: Literal["both_changed", "remote_deleted"]
    status: Literal["pending", "accepted_remote", "kept_local"]
    local_revision: int
    remote_hash: str
    local: CalendarConflictSide
    remote: CalendarConflictSide
    created_at: datetime


class ConflictResolution(StrictInput):
    resolution: Literal["accept_remote", "keep_local"]
    expected_local_revision: int = Field(ge=1)
    expected_remote_hash: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")


class PriceItemInput(StrictInput):
    metric: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]{0,63}$")
    unit_price: Decimal = Field(ge=0, max_digits=18, decimal_places=6)
    included_units: int = Field(default=0, ge=0)


class PriceVersionCreate(StrictInput):
    provider: str = Field(min_length=2, max_length=32, pattern=r"^[a-z][a-z0-9_-]{1,31}$")
    currency: str = Field(default="BRL", min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    pricing_model: Literal["commitment_floor", "base_plus_usage"]
    monthly_base_amount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=6)
    effective_on: date
    observed_on: date
    provenance_url: str = Field(min_length=12, max_length=1000)
    quote_required: bool = False
    notes: str | None = Field(default=None, max_length=1000)
    items: list[PriceItemInput] = Field(min_length=1, max_length=50)

    @field_validator("provenance_url")
    @classmethod
    def https_provenance(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("provenance_url deve usar HTTPS sem credenciais")
        return value

    @model_validator(mode="after")
    def unique_metrics(self):
        metrics = [item.metric for item in self.items]
        if len(metrics) != len(set(metrics)):
            raise ValueError("metricas duplicadas")
        if self.observed_on < self.effective_on:
            raise ValueError("observed_on nao pode ser anterior a effective_on")
        return self


class CostScenario(StrictInput):
    provider: str = Field(min_length=2, max_length=32, pattern=r"^[a-z][a-z0-9_-]{1,31}$")
    price_version_id: str = Field(min_length=1, max_length=64)
    volumes: dict[str, int] = Field(min_length=1, max_length=50)

    @field_validator("volumes")
    @classmethod
    def valid_volumes(cls, values: dict[str, int]) -> dict[str, int]:
        for metric, units in values.items():
            if not metric or len(metric) > 64 or units < 0:
                raise ValueError("volume invalido")
        return values


class CostLine(StrictInput):
    metric: str
    units: int
    billable_units: int
    unit_price: Decimal
    amount: Decimal


class CostReport(StrictInput):
    provider: str
    currency: str
    pricing_model: Literal["commitment_floor", "base_plus_usage"]
    monthly_base_amount: Decimal
    usage_amount: Decimal
    total_amount: Decimal
    quote_required: bool
    observed_on: date
    provenance_url: str
    lines: list[CostLine]
