from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, ForeignKeyConstraint, String

from app.core.database import Base


class DocumentKitReceipt(Base):
    """Immutable request receipt; document content stays in the existing version store."""

    __tablename__ = "document_kit_receipts"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "user_id"], ["users.tenant_id", "users.id"], name="fk_document_kit_receipt_user"),
        ForeignKeyConstraint(["tenant_id", "document_id"], ["workspace_documents.tenant_id", "workspace_documents.id"], name="fk_document_kit_receipt_document", ondelete="RESTRICT"),
    )

    tenant_id = Column(String, ForeignKey("tenants.id"), primary_key=True)
    user_id = Column(String, primary_key=True)
    request_id = Column(String(36), primary_key=True)
    payload_hash = Column(String(64), nullable=False)
    document_id = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
