"""Quarantined document processing and lifecycle tasks."""
import asyncio
import hashlib
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select, text

from app.core.celery_app import celery_app
from app.core.database import AsyncSessionLocal, engine
from app.core.dependencies import _set_tenant_context
from app.models.workspace import WorkspaceCase, WorkspaceDocument, WorkspaceDocumentUpload, WorkspaceDocumentVersion
from app.services.audit_service import AuditService
from app.services.document_storage import DocumentStorageError, delete, object_key, promote, read, scan
from app.services.document_text import TextExtractionError, extract_upload_text
from app.services.workspace_service import reset_document_review, validate_upload_bytes
from app.services.push_service import enqueue_user_push


def _ocr(content_type: str, content: bytes) -> str | None:
    if content_type not in {"application/pdf", "image/jpeg", "image/png"}:
        return None
    with tempfile.TemporaryDirectory(prefix="lexflow-ocr-") as directory:
        root = Path(directory)
        suffix = ".pdf" if content_type == "application/pdf" else ".png"
        source = root / f"source{suffix}"
        source.write_bytes(content)
        if content_type == "application/pdf":
            sidecar = root / "text.txt"
            output = root / "ignored.pdf"
            command = ["ocrmypdf", "--skip-text", "--deskew", "--rotate-pages", "--language", "por+eng", "--sidecar", str(sidecar), str(source), str(output)]
            subprocess.run(command, check=True, timeout=240, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return sidecar.read_text("utf-8", errors="replace")[:250_000].strip() or None
        result = subprocess.run(
            ["tesseract", str(source), "stdout", "-l", "por+eng"], check=True, timeout=180,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        return result.stdout[:250_000].strip() or None


async def _upload_row(upload_id: str, tenant_id: str, *, lock: bool = False):
    async with AsyncSessionLocal() as db, db.begin():
        await _set_tenant_context(db, tenant_id)
        statement = select(WorkspaceDocumentUpload).where(
            WorkspaceDocumentUpload.id == upload_id,
            WorkspaceDocumentUpload.tenant_id == tenant_id,
        )
        upload = await db.scalar(statement.with_for_update() if lock else statement)
        if not upload or upload.status != "uploaded":
            return None
        return {
            "id": upload.id, "tenant_id": upload.tenant_id, "document_id": upload.document_id,
            "expected_version": upload.expected_version, "folder_id": upload.folder_id,
            "client_id": upload.client_id, "case_id": upload.case_id, "filename": upload.filename,
            "content_type": upload.content_type, "expected_size": upload.expected_size,
            "expected_sha256": upload.expected_sha256, "object_key": upload.object_key,
            "created_by_user_id": upload.created_by_user_id,
            "created_by_portal_grant_id": upload.created_by_portal_grant_id,
        }


async def _process_upload(upload_id: str, tenant_id: str) -> str:
    upload = await _upload_row(upload_id, tenant_id, lock=True)
    if not upload:
        return "ignored"
    content = await asyncio.to_thread(read, upload["object_key"])
    if len(content) != upload["expected_size"]:
        raise DocumentStorageError("Tamanho recebido difere do upload autorizado.")
    filename, content_type, _, digest = validate_upload_bytes(upload["filename"], content)
    if content_type != upload["content_type"] or (upload["expected_sha256"] and digest != upload["expected_sha256"]):
        raise DocumentStorageError("Integridade ou formato do arquivo nao confere.")
    await asyncio.to_thread(scan, content)
    try:
        extracted = await asyncio.to_thread(extract_upload_text, content_type, content)
    except TextExtractionError:
        extracted = None
    ocr_status = "not_required"
    if content_type.startswith("image/") or (content_type == "application/pdf" and not extracted):
        ocr_status = "processing"
        extracted = await asyncio.to_thread(_ocr, content_type, content)
        ocr_status = "complete"

    async with AsyncSessionLocal() as db, db.begin():
        await _set_tenant_context(db, tenant_id)
        row = await db.scalar(select(WorkspaceDocumentUpload).where(
            WorkspaceDocumentUpload.id == upload_id,
            WorkspaceDocumentUpload.tenant_id == tenant_id,
        ).with_for_update())
        if not row or row.status == "completed":
            return "ignored"
        document = None
        if upload["document_id"]:
            document = await db.scalar(select(WorkspaceDocument).where(
                WorkspaceDocument.id == upload["document_id"], WorkspaceDocument.tenant_id == tenant_id,
            ).with_for_update())
            if not document or document.deleted_at or document.current_version != upload["expected_version"]:
                raise DocumentStorageError("Documento mudou antes da conclusao do upload.")
        else:
            document = WorkspaceDocument(
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"lexflow:{tenant_id}:{upload_id}:document")), tenant_id=tenant_id, client_id=upload["client_id"],
                case_id=upload["case_id"], folder_id=upload["folder_id"], kind="evidence",
                title=Path(filename).stem[:300], content_format="plain",
            )
            db.add(document)
            await db.flush()
        version_number = document.current_version + 1 if upload["document_id"] else 1
        version_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"lexflow:{tenant_id}:{upload_id}:version"))
        destination = object_key(tenant_id, document.id, version_id)
        await asyncio.to_thread(promote, upload["object_key"], destination, content_type, filename)
        document.filename = filename
        document.content_type = content_type
        document.file_content = None
        document.file_size = len(content)
        document.sha256_hash = digest
        document.content_text = document.content_text or extracted
        document.current_version = version_number
        document.revision += int(bool(upload["document_id"]))
        reset_document_review(document)
        db.add(WorkspaceDocumentVersion(
            id=version_id, tenant_id=tenant_id, document_id=document.id, version=version_number,
            content_text=document.content_text, content_format=document.content_format,
            filename=filename, content_type=content_type, file_size=len(content), sha256_hash=digest,
            object_key=destination, storage_status="available", ocr_status=ocr_status,
            created_by_user_id=upload["created_by_user_id"],
            created_by_portal_grant_id=upload["created_by_portal_grant_id"],
        ))
        row.document_id = document.id
        row.status = "completed"
        row.completed_at = datetime.now(timezone.utc)
        await AuditService.log_action(
            db, tenant_id, upload["created_by_user_id"], "DOCUMENT_UPLOAD_COMPLETED", "workspace_documents", document.id,
            {"version": version_number, "sha256": digest, "portal_grant_id": upload["created_by_portal_grant_id"]},
        )
        if upload["created_by_portal_grant_id"] and upload["case_id"]:
            case = await db.scalar(select(WorkspaceCase).where(
                WorkspaceCase.tenant_id == tenant_id, WorkspaceCase.id == upload["case_id"],
            ))
            if case and case.responsible_user_id:
                await enqueue_user_push(
                    db, tenant_id=tenant_id, user_id=case.responsible_user_id,
                    event_key=f"portal-document:{document.id}", kind="portal_document", case_id=case.id,
                )
        document_id = document.id
    try:
        await asyncio.to_thread(delete, upload["object_key"])
    except Exception:
        pass  # The quarantine lifecycle rule is the bounded fallback cleanup.
    return document_id


async def _fail_upload(upload_id: str, tenant_id: str, message: str) -> None:
    quarantine = None
    async with AsyncSessionLocal() as db, db.begin():
        await _set_tenant_context(db, tenant_id)
        row = await db.scalar(select(WorkspaceDocumentUpload).where(
            WorkspaceDocumentUpload.id == upload_id,
            WorkspaceDocumentUpload.tenant_id == tenant_id,
        ).with_for_update())
        if row and row.status != "completed":
            quarantine = row.object_key
            row.status = "failed"
            row.error = message[:500]
            await AuditService.log_action(db, tenant_id, row.created_by_user_id, "DOCUMENT_UPLOAD_REJECTED", "workspace_document_uploads", row.id, {"reason": message[:120]})
    if quarantine:
        try:
            await asyncio.to_thread(delete, quarantine)
        except Exception:
            pass  # The bucket lifecycle rule removes failed quarantine objects.


@celery_app.task(bind=True, name="documents.process_upload", queue="documents", acks_late=True, reject_on_worker_lost=True, max_retries=3, soft_time_limit=270, time_limit=300)
def process_upload(self, upload_id: str, tenant_id: str):
    try:
        return asyncio.run(_process_upload(upload_id, tenant_id))
    except Exception as exc:
        if self.request.retries < self.max_retries and not "bloqueado pelo antivirus" in str(exc).lower():
            raise self.retry(exc=exc, countdown=30 * (self.request.retries + 1))
        asyncio.run(_fail_upload(upload_id, tenant_id, str(exc) or "Falha no processamento seguro."))
        return "failed"
    finally:
        asyncio.run(engine.dispose())


async def _lifecycle_candidates() -> list[tuple[str, str, str]]:
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(text("SELECT tenant_id, document_id, object_key FROM document_lifecycle_candidates(200)"))).all()
        return [(row.tenant_id, row.document_id, row.object_key) for row in rows]


async def _purge_candidate(tenant_id: str, document_id: str, key: str) -> bool:
    await asyncio.to_thread(delete, key)
    async with AsyncSessionLocal() as db, db.begin():
        return bool(await db.scalar(text("SELECT mark_document_object_deleted(:tenant, :document, :key)"), {"tenant": tenant_id, "document": document_id, "key": key}))


@celery_app.task(name="documents.purge_trash", queue="documents", soft_time_limit=240, time_limit=270)
def purge_trash():
    candidates = asyncio.run(_lifecycle_candidates())
    purged = 0
    try:
        for candidate in candidates:
            purged += int(asyncio.run(_purge_candidate(*candidate)))
        return {"candidates": len(candidates), "purged": purged}
    finally:
        asyncio.run(engine.dispose())
