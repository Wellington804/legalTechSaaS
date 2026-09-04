"""Tenant-scoped identity drafts and immutable publication/export snapshots."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, ForeignKeyConstraint, Integer, JSON, LargeBinary, String, UniqueConstraint

from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class BrandProfile(Base):
    __tablename__ = "brand_profiles"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_brand_profile_tenant"),
        CheckConstraint("(scope = 'office' AND owner_user_id IS NULL) OR (scope = 'personal' AND owner_user_id IS NOT NULL)", name="ck_brand_profile_scope"),
        ForeignKeyConstraint(["tenant_id", "owner_user_id"], ["users.tenant_id", "users.id"]),
        ForeignKeyConstraint(["tenant_id", "id", "published_version"], ["brand_versions.tenant_id", "brand_versions.profile_id", "brand_versions.version"], name="fk_brand_published_version", use_alter=True, deferrable=True, initially="DEFERRED"),
    )
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    scope = Column(String(16), nullable=False)
    owner_user_id = Column(String)
    settings = Column(JSON, nullable=False)
    variants = Column(JSON, nullable=False, default=dict)
    revision = Column(Integer, nullable=False, default=1)
    published_version = Column(Integer)
    archived_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class BrandVersion(Base):
    __tablename__ = "brand_versions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "profile_id", "version", name="uq_brand_version_number"),
        ForeignKeyConstraint(["tenant_id", "profile_id"], ["brand_profiles.tenant_id", "brand_profiles.id"]),
        ForeignKeyConstraint(["tenant_id", "created_by_user_id"], ["users.tenant_id", "users.id"]),
    )
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    profile_id = Column(String, nullable=False, index=True)
    version = Column(Integer, nullable=False)
    settings = Column(JSON, nullable=False)
    variants = Column(JSON, nullable=False, default=dict)
    professional_snapshot = Column(JSON, nullable=False, default=dict)
    created_by_user_id = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class BrandAsset(Base):
    __tablename__ = "brand_assets"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "profile_id"], ["brand_profiles.tenant_id", "brand_profiles.id"]),
        ForeignKeyConstraint(["tenant_id", "created_by_user_id"], ["users.tenant_id", "users.id"]),
        CheckConstraint("kind IN ('reference','logo','logo_dark','logo_mono','watermark','background')", name="ck_brand_asset_kind"),
    )
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    profile_id = Column(String, nullable=False, index=True)
    kind = Column(String(16), nullable=False)
    filename = Column(String(255), nullable=False)
    content_type = Column(String(100), nullable=False)
    content = Column(LargeBinary, nullable=True)
    object_key = Column(String(512), nullable=True, unique=True)
    size = Column(Integer, nullable=False)
    sha256 = Column(String(64), nullable=False)
    analysis = Column(JSON, nullable=False)
    created_by_user_id = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class BrandExport(Base):
    __tablename__ = "brand_exports"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "document_id", "document_version"], ["workspace_document_versions.tenant_id", "workspace_document_versions.document_id", "workspace_document_versions.version"]),
        ForeignKeyConstraint(["tenant_id", "profile_id", "brand_version"], ["brand_versions.tenant_id", "brand_versions.profile_id", "brand_versions.version"]),
        ForeignKeyConstraint(["tenant_id", "created_by_user_id"], ["users.tenant_id", "users.id"]),
        CheckConstraint("document_type IN ('general','petition','contract','power_of_attorney','notice','correspondence')", name="ck_brand_exports_document_type"),
    )
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    document_id = Column(String, nullable=False, index=True)
    document_version = Column(Integer, nullable=False)
    profile_id = Column(String, nullable=False)
    brand_version = Column(Integer, nullable=False)
    document_type = Column(String(32), nullable=False, default="general")
    brand_snapshot = Column(JSON, nullable=False)
    docx = Column(LargeBinary, nullable=True)
    pdf = Column(LargeBinary, nullable=True)
    docx_object_key = Column(String(512), nullable=True, unique=True)
    pdf_object_key = Column(String(512), nullable=True, unique=True)
    docx_size = Column(Integer, nullable=False, default=0)
    pdf_size = Column(Integer, nullable=False, default=0)
    sha256_docx = Column(String(64), nullable=False)
    sha256_pdf = Column(String(64), nullable=False)
    created_by_user_id = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
