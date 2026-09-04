import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.workspace import normalize_phone


EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PHONE_RE = re.compile(r"^\+[1-9]\d{7,14}$")
RESOURCE_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class NotificationDispatchRequest(BaseModel):
    resource_ref: str = Field(min_length=1, max_length=128)
    recipient: str = Field(min_length=8, max_length=320)
    channel: Literal["email", "whatsapp"]

    @field_validator("resource_ref")
    @classmethod
    def validate_resource_ref(cls, value: str) -> str:
        value = value.strip()
        if not RESOURCE_REF_RE.fullmatch(value):
            raise ValueError("resource_ref must be an opaque identifier")
        return value

    @model_validator(mode="after")
    def normalize_recipient(self):
        value = self.recipient.strip()
        if self.channel == "email":
            value = value.casefold()
            if not EMAIL_RE.fullmatch(value):
                raise ValueError("invalid email recipient")
        else:
            try:
                value = normalize_phone(value)
            except ValueError as exc:
                raise ValueError("WhatsApp recipient must use a valid phone number") from exc
            if not value or not PHONE_RE.fullmatch(value):
                raise ValueError("WhatsApp recipient must use E.164 format")
        self.recipient = value
        return self


class NotificationDeliveryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    resource_ref: str
    channel: Literal["email", "whatsapp"]
    status: Literal["queued", "processing", "sent", "delivered", "unknown", "failed"]
    attempts: int
    error_code: str | None
    created_at: datetime
    updated_at: datetime
    existing: bool = False
