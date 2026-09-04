"""Backfill one tenant's existing binary versions to R2 without deleting PostgreSQL bytes."""
import argparse
import asyncio
import hashlib

from sqlalchemy import or_, select

from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
from app.core.dependencies import _set_tenant_context
from app.models.branding import BrandExport
from app.models.workspace import WorkspaceDocumentVersion
from app.services.document_storage import enabled, object_key, put, read


async def run(tenant_id: str, apply: bool, batch: int) -> dict:
    if not enabled():
        raise RuntimeError("R2_ENABLED must be true")
    result = {"document_versions": 0, "exports": 0, "verified": 0, "dry_run": not apply}
    async with AsyncSessionLocal() as db:
        await _set_tenant_context(db, tenant_id)
        versions = (await db.scalars(select(WorkspaceDocumentVersion).where(
            WorkspaceDocumentVersion.tenant_id == tenant_id,
            WorkspaceDocumentVersion.file_content.is_not(None),
            WorkspaceDocumentVersion.object_key.is_(None),
        ).order_by(WorkspaceDocumentVersion.created_at).limit(batch))).all()
        exports = (await db.scalars(select(BrandExport).where(
            BrandExport.tenant_id == tenant_id,
            or_(
                (BrandExport.docx.is_not(None) & BrandExport.docx_object_key.is_(None)),
                (BrandExport.pdf.is_not(None) & BrandExport.pdf_object_key.is_(None)),
            ),
        ).order_by(BrandExport.created_at).limit(batch))).all()
        result["document_versions"] = len(versions)
        result["exports"] = len(exports)
        if not apply:
            return result
        for version in versions:
            key = object_key(tenant_id, version.document_id, version.id)
            filename = version.filename or "documento.bin"
            content_type = version.content_type or "application/octet-stream"
            put(key, version.file_content, content_type, filename)
            expected = hashlib.sha256(version.file_content).hexdigest()
            if hashlib.sha256(read(key)).hexdigest() != expected:
                raise RuntimeError(f"R2 verification failed for version {version.id}")
            version.sha256_hash = expected
            version.object_key = key
            version.storage_status = "available"
            result["verified"] += 1
            await db.commit()
        for export in exports:
            for format, content, mime in (
                ("docx", export.docx, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
                ("pdf", export.pdf, "application/pdf"),
            ):
                key_field = f"{format}_object_key"
                if content is None or getattr(export, key_field):
                    continue
                key = f"exports/{tenant_id}/{export.id}/document.{format}"
                put(key, content, mime, f"documento.{format}")
                expected = export.sha256_docx if format == "docx" else export.sha256_pdf
                if hashlib.sha256(read(key)).hexdigest() != expected:
                    raise RuntimeError(f"R2 verification failed for export {export.id}/{format}")
                setattr(export, key_field, key)
                setattr(export, f"{format}_size", len(content))
                result["verified"] += 1
                await db.commit()
        return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--batch", type=int, default=100)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.batch <= 1000:
        parser.error("--batch must be between 1 and 1000")
    try:
        print(asyncio.run(run(args.tenant_id, args.apply, args.batch)))
    finally:
        asyncio.run(engine.dispose())


if __name__ == "__main__":
    main()
