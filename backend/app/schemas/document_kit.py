from typing import Literal
from uuid import UUID

from pydantic import Field, StrictBool, field_validator

from app.schemas.workspace import WorkspaceInput, safe_document_text


class DocumentKitPreview(WorkspaceInput):
    template_key: Literal[
        "intake", "power_of_attorney", "fee_agreement", "initial_petition", "defense",
        "intermediate_petition", "extrajudicial_notice", "collection_notice",
    ]
    case_id: str = Field(min_length=1, max_length=64)
    values: dict[str, str] = Field(default_factory=dict, max_length=16)

    @field_validator("values")
    @classmethod
    def safe_values(cls, values: dict[str, str]) -> dict[str, str]:
        result = {}
        for key, value in values.items():
            if len(key) > 64 or len(value) > 4000 or any(ord(char) < 32 and char not in "\n\r\t" for char in value):
                raise ValueError("Campo inválido ou muito longo; limite de 4000 caracteres por campo.")
            result[key] = safe_document_text(value.strip())
        if sum(len(value) for value in result.values()) > 24000:
            raise ValueError("O preenchimento excede 24000 caracteres.")
        return result


class DocumentKitSource(WorkspaceInput):
    case_revision: int = Field(ge=1)
    client_revision: int = Field(ge=1)
    template_version: str = Field(min_length=1, max_length=40)
    profile_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


class DocumentKitCreate(DocumentKitPreview):
    request_id: UUID
    source: DocumentKitSource
    reviewed: StrictBool

    @field_validator("reviewed")
    @classmethod
    def require_review(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Revise o rascunho e confirme a conferência antes de salvar.")
        return value
