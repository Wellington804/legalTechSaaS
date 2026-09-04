"""Quarantined document processing and lifecycle tasks."""
import asyncio
import hashlib
import re
import subprocess
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import and_, or_, select, text
from sqlalchemy.orm import load_only

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
from app.core.dependencies import _set_tenant_context, ensure_tenant_write_access
from app.models.assistant import (
    AIEvaluationCase,
    AIEvaluationResult,
    AIEvaluationRun,
    DocumentIntelligenceAnalysis,
    DocumentIntelligenceConsentReceipt,
    DocumentIntelligenceSource,
)
from app.models.user import User
from app.models.workspace import WorkspaceCase, WorkspaceDocument, WorkspaceDocumentUpload, WorkspaceDocumentVersion
from app.services.ai_provider import AIProviderError, generate_text, model_name, provider_name
from app.services.ai_quality import (
    DOCUMENT_INTELLIGENCE_SYSTEM_PROMPT,
    DOCUMENT_INTELLIGENCE_CONSENT_POLICY,
    EVALUATION_SYSTEM_PROMPT,
    DocumentIntelligenceOutput,
    EvaluationCaseContent,
    EvaluationMetrics,
    EvaluationOutput,
    aggregate_evaluation_metrics,
    canonical_hash,
    consent_receipt_hash,
    document_provenance_manifest,
    document_intelligence_prompt,
    evaluation_prompt,
    evaluation_run_outcome,
    parse_document_intelligence,
    parse_evaluation_output,
    score_evaluation,
    validate_document_intelligence,
)
from app.services.audit_service import AuditService
from app.services.document_storage import DocumentStorageError, delete, object_key, promote, read, scan
from app.services.document_text import TextExtractionError, extract_upload_text, mark_pdf_pages
from app.services.legal_ai import build_evidence_bundle
from app.services.workspace_service import case_access_clause, reset_document_review, validate_upload_bytes
from app.services.push_service import enqueue_user_push


AI_WORKER_ROLES = {"admin", "partner", "lawyer"}
AI_WORKER_LEASE_TIMEOUT = timedelta(minutes=15)
OCR_COVERAGE_LIMITATION = (
    "OCR falho, parcial ou não comprovado; a análise cobre somente o texto efetivamente extraído."
)


async def _authorized_ai_requester(db, tenant_id: str, user_id: str) -> User:
    user = await db.scalar(select(User).where(
        User.id == user_id,
        User.tenant_id == tenant_id,
        User.is_active.is_(True),
    ))
    if not user or user.role not in AI_WORKER_ROLES:
        raise AIProviderError("requesting user is not authorized for legal AI")
    try:
        await ensure_tenant_write_access(db, tenant_id)
    except Exception as exc:
        raise AIProviderError("tenant write access is no longer available") from exc
    return user


def _claim_queued_job(row, next_status: str) -> bool:
    if row.status != "queued":
        return False
    row.status = next_status
    return True


def _worker_lease_expired(claimed_at: datetime | None, now: datetime) -> bool:
    if claimed_at is None:
        return True
    if claimed_at.tzinfo is None:
        claimed_at = claimed_at.replace(tzinfo=timezone.utc)
    return claimed_at <= now - AI_WORKER_LEASE_TIMEOUT


def _analysis_coverage(base: dict, source_rows: list[DocumentIntelligenceSource]) -> dict:
    ocr_incomplete = [
        row.document_id for row in source_rows
        if row.ocr_status in {"failed", "partial", "processing", "unknown"}
    ]
    return {
        **base,
        "ocr_incomplete_documents": ocr_incomplete,
        "partial": bool(base.get("truncated") or ocr_incomplete),
        "scope": "extracted_text_only",
    }


def _coverage_limitations(limitations: list[str], coverage: dict) -> list[str]:
    values = [item for item in limitations if item != OCR_COVERAGE_LIMITATION]
    if coverage.get("ocr_incomplete_documents"):
        return values[:19] + [OCR_COVERAGE_LIMITATION]
    return values[:20]


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
            # force-ocr produces one complete sidecar for mixed native/scanned PDFs;
            # skip-text would omit native pages and break page-level provenance.
            command = [
                "ocrmypdf", "--force-ocr", "--deskew", "--rotate-pages", "--jobs", "2",
                "--tesseract-timeout", "30", "--language", "por+eng", "--sidecar", str(sidecar),
                str(source), str(output),
            ]
            subprocess.run(command, check=True, timeout=240, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            text = sidecar.read_text("utf-8", errors="replace")[:250_000].strip()
            return mark_pdf_pages(text) or None
        result = subprocess.run(
            ["tesseract", str(source), "stdout", "-l", "por+eng"], check=True, timeout=180,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        return result.stdout[:250_000].strip() or None


def _needs_pdf_ocr(extracted: str | None) -> bool:
    """Detect empty and low-quality/partially scanned PDFs without guessing content."""
    if not extracted:
        return True
    pages = re.split(r"\[\[LEXFLOW_PAGE:\d+\]\]", extracted)[1:]
    printable = sum(character.isalnum() for character in extracted)
    replacement_ratio = extracted.count("\ufffd") / max(1, len(extracted))
    sparse_page = bool(pages) and any(sum(character.isalnum() for character in page) < 40 for page in pages)
    return sparse_page or printable < max(80, 40 * len(pages)) or replacement_ratio > 0.02


async def _extract_document_text(content_type: str, content: bytes) -> tuple[str | None, str, str | None]:
    try:
        extracted = await asyncio.to_thread(extract_upload_text, content_type, content)
    except TextExtractionError:
        extracted = None
    ocr_status = "not_required"
    ocr_error = None
    if content_type.startswith("image/") or (content_type == "application/pdf" and _needs_pdf_ocr(extracted)):
        ocr_status = "processing"
        try:
            ocr_text = await asyncio.to_thread(_ocr, content_type, content)
            if ocr_text:
                extracted = ocr_text
                ocr_status = "complete"
            else:
                ocr_status = "failed"
                ocr_error = "OCR não encontrou texto utilizável."
        except Exception:
            # Integrity and malware checks are performed by the caller first.
            # OCR is a derivative; its failure must not destroy the original.
            ocr_status = "failed"
            ocr_error = "OCR indisponível; original preservado para nova tentativa."
    return extracted, ocr_status, ocr_error


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
    extracted, ocr_status, ocr_error = await _extract_document_text(content_type, content)

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
        # A new binary version must never inherit text from the previous file.
        # If extraction/OCR yields no text, downstream AI remains closed instead of
        # attributing stale content to the new hash/version.
        document.content_text = extracted
        document.current_version = version_number
        document.revision += int(bool(upload["document_id"]))
        reset_document_review(document)
        db.add(WorkspaceDocumentVersion(
            id=version_id, tenant_id=tenant_id, document_id=document.id, version=version_number,
            content_text=document.content_text, content_format=document.content_format,
            filename=filename, content_type=content_type, file_size=len(content), sha256_hash=digest,
            object_key=destination, storage_status="available", ocr_status=ocr_status,
            processing_error=ocr_error,
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


async def _run_evaluation_impl(run_id: str, tenant_id: str) -> str:
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db, db.begin():
        await _set_tenant_context(db, tenant_id)
        run = await db.scalar(select(AIEvaluationRun).where(
            AIEvaluationRun.id == run_id, AIEvaluationRun.tenant_id == tenant_id,
        ).with_for_update())
        if not run:
            return "ignored"
        if run.status == "running":
            if not _worker_lease_expired(run.started_at, now):
                return "ignored"
            run.status = "failed"
            run.error = "Lease do worker expirou; reexecução automática bloqueada para evitar custo duplicado."
            run.completed_at = now
            await AuditService.log_action(
                db, tenant_id, run.requested_by_user_id,
                "AI_EVALUATION_LEASE_EXPIRED", "ai_evaluation_runs", run.id,
                {
                    "previous_status": "running",
                    "claimed_at": run.started_at.isoformat() if run.started_at else None,
                    "lease_seconds": int(AI_WORKER_LEASE_TIMEOUT.total_seconds()),
                    "automatic_retry": False,
                },
            )
            return "failed"
        if run.status != "queued":
            return "ignored"
        requester = await _authorized_ai_requester(db, tenant_id, run.requested_by_user_id)
        if (
            not isinstance(run.case_ids, list) or not run.case_ids or len(run.case_ids) > 5
            or any(not isinstance(item, str) or not item for item in run.case_ids)
            or len(run.case_ids) != len(set(run.case_ids))
        ):
            run.status = "failed"
            run.error = "Snapshot de corpus inválido."
            run.completed_at = now
            return "stale"
        cases = (await db.execute(select(AIEvaluationCase).where(
            AIEvaluationCase.tenant_id == tenant_id,
            AIEvaluationCase.id.in_(run.case_ids),
            AIEvaluationCase.status == "approved",
        ))).scalars().all()
        snapshot = sorted(
            ({"id": case.id, "version": case.version, "content_hash": case.content_hash} for case in cases),
            key=lambda item: item["id"],
        )
        if len(cases) != run.case_count or canonical_hash(snapshot) != run.corpus_hash:
            run.status = "failed"
            run.error = "O corpus aprovado mudou antes da execução."
            run.completed_at = now
            return "stale"
        if provider_name(settings) != run.provider or model_name(settings, "legal") != run.model:
            run.status = "failed"
            run.error = "A rota de IA mudou depois do agendamento. Execute um novo benchmark."
            run.completed_at = now
            return "stale"
        if not _claim_queued_job(run, "running"):
            return "ignored"
        run.started_at = run.started_at or now
        completed_case_ids = set((await db.scalars(select(AIEvaluationResult.case_id).where(
            AIEvaluationResult.tenant_id == tenant_id,
            AIEvaluationResult.run_id == run_id,
        ))).all())
        payloads = [
            (case.id, case.version, case.content_hash, case.content)
            for case in sorted(cases, key=lambda item: item.id)
            if case.id not in completed_case_ids
        ]
        provider, model, requested_by = run.provider, run.model, requester.id

    for case_id, case_version, case_hash, raw_content in payloads:
        try:
            async with AsyncSessionLocal() as db, db.begin():
                await _set_tenant_context(db, tenant_id)
                current_run = await db.scalar(select(AIEvaluationRun).where(
                    AIEvaluationRun.id == run_id,
                    AIEvaluationRun.tenant_id == tenant_id,
                    AIEvaluationRun.status == "running",
                ))
                if not current_run:
                    raise AIProviderError("evaluation run is no longer active")
                await _authorized_ai_requester(db, tenant_id, current_run.requested_by_user_id)
            content = EvaluationCaseContent.model_validate(raw_content)
            if canonical_hash(content.model_dump(mode="json")) != case_hash:
                raise AIProviderError("stale evaluation case hash")
            raw = await generate_text(
                system_prompt=EVALUATION_SYSTEM_PROMPT,
                user_prompt=evaluation_prompt(content),
                purpose="legal",
                max_output_tokens=5000,
                temperature=0,
                response_schema=EvaluationOutput.model_json_schema(),
            )
            output = parse_evaluation_output(raw)
            metrics = score_evaluation(content, output)
            result = AIEvaluationResult(
                tenant_id=tenant_id, run_id=run_id, case_id=case_id, case_version=case_version,
                case_hash=case_hash, status="completed", output=output.model_dump(mode="json"),
                output_hash=canonical_hash(output.model_dump(mode="json")), metrics=metrics.model_dump(mode="json"),
            )
        except (AIProviderError, ValueError, TypeError) as exc:
            result = AIEvaluationResult(
                tenant_id=tenant_id, run_id=run_id, case_id=case_id, case_version=case_version,
                case_hash=case_hash, status="failed", error=(str(exc) or "Falha de avaliação.")[:500],
            )
        async with AsyncSessionLocal() as db, db.begin():
            await _set_tenant_context(db, tenant_id)
            existing = await db.scalar(select(AIEvaluationResult).where(
                AIEvaluationResult.tenant_id == tenant_id,
                AIEvaluationResult.run_id == run_id,
                AIEvaluationResult.case_id == case_id,
            ))
            if not existing:
                db.add(result)

    async with AsyncSessionLocal() as db, db.begin():
        await _set_tenant_context(db, tenant_id)
        run = await db.scalar(select(AIEvaluationRun).where(
            AIEvaluationRun.id == run_id, AIEvaluationRun.tenant_id == tenant_id,
        ).with_for_update())
        if not run or run.status != "running":
            return "ignored"
        completed_rows = (await db.execute(select(AIEvaluationResult).where(
            AIEvaluationResult.tenant_id == tenant_id,
            AIEvaluationResult.run_id == run_id,
            AIEvaluationResult.status == "completed",
        ))).scalars().all()
        all_metrics = [EvaluationMetrics.model_validate(row.metrics) for row in completed_rows if row.metrics]
        run.status, run.error = evaluation_run_outcome(len(all_metrics), run.case_count)
        run.aggregate_metrics = aggregate_evaluation_metrics(all_metrics).model_dump(mode="json") if all_metrics else None
        run.completed_at = datetime.now(timezone.utc)
        await AuditService.log_action(db, tenant_id, requested_by, "AI_EVALUATION_COMPLETED", "ai_evaluation_runs", run_id, {
            "provider": provider, "model": model, "completed_cases": len(all_metrics), "total_cases": run.case_count,
        })
    return run.status


async def _validated_intelligence_context(db, analysis: DocumentIntelligenceAnalysis, tenant_id: str):
    source_rows = (await db.execute(select(DocumentIntelligenceSource).where(
        DocumentIntelligenceSource.analysis_id == analysis.id,
        DocumentIntelligenceSource.tenant_id == tenant_id,
    ).order_by(DocumentIntelligenceSource.document_id))).scalars().all()
    documents = (await db.execute(select(WorkspaceDocument).where(
        WorkspaceDocument.tenant_id == tenant_id,
        WorkspaceDocument.id.in_([row.document_id for row in source_rows]),
        WorkspaceDocument.deleted_at.is_(None),
    ))).scalars().all()
    versions = (await db.execute(select(WorkspaceDocumentVersion).options(load_only(
        WorkspaceDocumentVersion.document_id, WorkspaceDocumentVersion.version,
        WorkspaceDocumentVersion.sha256_hash, WorkspaceDocumentVersion.object_key,
        WorkspaceDocumentVersion.filename, WorkspaceDocumentVersion.file_size,
        WorkspaceDocumentVersion.storage_status, WorkspaceDocumentVersion.ocr_status,
        WorkspaceDocumentVersion.content_type,
    )).where(
        WorkspaceDocumentVersion.tenant_id == tenant_id,
        or_(*[
            and_(WorkspaceDocumentVersion.document_id == row.document_id, WorkspaceDocumentVersion.version == row.document_version)
            for row in source_rows
        ]),
    ))).scalars().all() if source_rows else []
    manifest = document_provenance_manifest(documents, versions)
    persisted = [{
        "document_id": row.document_id, "version": row.document_version,
        "binary_sha256": row.binary_sha256, "text_sha256": row.text_sha256,
        "extractor": row.extractor, "ocr_status": row.ocr_status,
    } for row in source_rows]
    if len(documents) != len(source_rows) or manifest != persisted or canonical_hash(manifest) != analysis.snapshot_hash:
        raise AIProviderError("stale document provenance")
    user = await _authorized_ai_requester(db, tenant_id, analysis.requested_by_user_id)
    case = await db.scalar(select(WorkspaceCase).where(
        WorkspaceCase.id == analysis.case_id,
        WorkspaceCase.tenant_id == tenant_id,
        case_access_clause(user),
    ))
    if not case:
        raise AIProviderError("requesting user no longer has access to the case")
    receipt = await db.scalar(select(DocumentIntelligenceConsentReceipt).where(
        DocumentIntelligenceConsentReceipt.analysis_id == analysis.id,
        DocumentIntelligenceConsentReceipt.tenant_id == tenant_id,
    ))
    if (
        not receipt or receipt.case_id != case.id or receipt.user_id != user.id
        or receipt.provider != analysis.provider or receipt.purpose != "document_intelligence"
        or receipt.policy_version != DOCUMENT_INTELLIGENCE_CONSENT_POLICY
        or receipt.document_manifest != manifest
    ):
        raise AIProviderError("missing or stale consent receipt")
    expected_receipt_hash = consent_receipt_hash(
        analysis_id=analysis.id, case_id=case.id, user_id=user.id,
        provider=receipt.provider, purpose=receipt.purpose,
        policy_version=receipt.policy_version, document_manifest=manifest,
    )
    if receipt.receipt_hash != expected_receipt_hash:
        raise AIProviderError("consent receipt integrity check failed")
    expected_fingerprint = canonical_hash({
        "case_id": case.id, "requested_by_user_id": user.id,
        "documents": manifest, "provider": analysis.provider, "model": analysis.model,
        "purpose": "document_intelligence", "consent_policy": receipt.policy_version,
    })
    if analysis.request_fingerprint != expected_fingerprint:
        raise AIProviderError("request fingerprint does not match its authorization snapshot")
    return source_rows, sorted(documents, key=lambda item: item.id), case, user


async def _run_document_intelligence_impl(analysis_id: str, tenant_id: str) -> str:
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db, db.begin():
        await _set_tenant_context(db, tenant_id)
        analysis = await db.scalar(select(DocumentIntelligenceAnalysis).where(
            DocumentIntelligenceAnalysis.id == analysis_id,
            DocumentIntelligenceAnalysis.tenant_id == tenant_id,
        ).with_for_update())
        if not analysis:
            return "ignored"
        if analysis.status == "processing":
            if not _worker_lease_expired(analysis.updated_at, now):
                return "ignored"
            analysis.status = "stale"
            analysis.error = "Lease do worker expirou; reexecução automática bloqueada para evitar custo duplicado."
            analysis.revision += 1
            await AuditService.log_action(
                db, tenant_id, analysis.requested_by_user_id,
                "DOCUMENT_INTELLIGENCE_LEASE_EXPIRED", "document_intelligence_analyses", analysis.id,
                {
                    "previous_status": "processing",
                    "claimed_at": analysis.updated_at.isoformat() if analysis.updated_at else None,
                    "lease_seconds": int(AI_WORKER_LEASE_TIMEOUT.total_seconds()),
                    "automatic_retry": False,
                },
            )
            return "stale"
        if analysis.status != "queued":
            return "ignored"
        source_rows, documents, case, user = await _validated_intelligence_context(db, analysis, tenant_id)
        if provider_name(settings) != analysis.provider or model_name(settings, "legal") != analysis.model:
            analysis.status, analysis.error = "stale", "A rota de IA mudou depois do agendamento."
            return "stale"
        if not _claim_queued_job(analysis, "processing"):
            return "ignored"
        analysis.updated_at = now
        requested_by = user.id

    bundle = build_evidence_bundle(
        documents, "classificação anexo fatos datas valores partes eventos divergências",
        max_source_chars=40_000,
    )
    if not bundle["sources"]:
        raise AIProviderError("documents have no citable text")
    coverage = _analysis_coverage(bundle["coverage"], source_rows)
    prompt = document_intelligence_prompt(case=case, sources=bundle["sources"], snapshots=bundle["snapshots"])

    # Persist extraction coverage before the external call. If the provider fails,
    # the failed record still explains exactly which OCR/text surface was analysed.
    async with AsyncSessionLocal() as db, db.begin():
        await _set_tenant_context(db, tenant_id)
        analysis = await db.scalar(select(DocumentIntelligenceAnalysis).where(
            DocumentIntelligenceAnalysis.id == analysis_id,
            DocumentIntelligenceAnalysis.tenant_id == tenant_id,
        ).with_for_update())
        if not analysis or analysis.status != "processing":
            return "ignored"
        await _validated_intelligence_context(db, analysis, tenant_id)
        analysis.coverage = coverage
        analysis.limitations = _coverage_limitations([], coverage)

    raw = await generate_text(
        system_prompt=DOCUMENT_INTELLIGENCE_SYSTEM_PROMPT,
        user_prompt=prompt,
        purpose="legal", max_output_tokens=7000, temperature=0,
        response_schema=DocumentIntelligenceOutput.model_json_schema(),
    )
    output = validate_document_intelligence(parse_document_intelligence(raw), bundle["sources"], bundle["snapshots"])

    async with AsyncSessionLocal() as db, db.begin():
        await _set_tenant_context(db, tenant_id)
        analysis = await db.scalar(select(DocumentIntelligenceAnalysis).where(
            DocumentIntelligenceAnalysis.id == analysis_id,
            DocumentIntelligenceAnalysis.tenant_id == tenant_id,
        ).with_for_update())
        if not analysis or analysis.status != "processing":
            return "ignored"
        await _validated_intelligence_context(db, analysis, tenant_id)
        analysis.status, analysis.error = "review_required", None
        analysis.evidence_sources = [item.model_dump(mode="json") for item in bundle["sources"]]
        analysis.classifications = [item.model_dump(mode="json") for item in sorted(output.classifications, key=lambda item: item.document_id)]
        analysis.timeline = [item.model_dump(mode="json") for item in sorted(
            output.events, key=lambda item: (item.event_date is None, item.event_date.isoformat() if item.event_date else "", item.id),
        )]
        analysis.contradiction_groups = [item.model_dump(mode="json") for item in sorted(output.contradiction_groups, key=lambda item: item.id)]
        analysis.limitations = _coverage_limitations(list(output.limitations), coverage)
        analysis.coverage = coverage
        analysis.result_hash = canonical_hash({
            "evidence_sources": analysis.evidence_sources,
            "classifications": analysis.classifications,
            "timeline": analysis.timeline,
            "contradiction_groups": analysis.contradiction_groups,
            "limitations": analysis.limitations,
            "coverage": analysis.coverage,
        })
        await AuditService.log_action(db, tenant_id, requested_by, "DOCUMENT_INTELLIGENCE_COMPLETED", "document_intelligence_analyses", analysis_id, {
            "status": "review_required", "review_required": True,
            "coverage": analysis.coverage,
        })
    return "review_required"


async def _mark_evaluation_failed(run_id: str, tenant_id: str, error: Exception) -> None:
    async with AsyncSessionLocal() as db, db.begin():
        await _set_tenant_context(db, tenant_id)
        run = await db.scalar(select(AIEvaluationRun).where(
            AIEvaluationRun.id == run_id, AIEvaluationRun.tenant_id == tenant_id,
        ).with_for_update())
        if run and run.status in {"queued", "running"}:
            run.status = "failed"
            run.error = (str(error) or "Falha inesperada na avaliação.")[:500]
            run.completed_at = datetime.now(timezone.utc)


async def _mark_intelligence_failed(analysis_id: str, tenant_id: str, error: Exception) -> None:
    async with AsyncSessionLocal() as db, db.begin():
        await _set_tenant_context(db, tenant_id)
        analysis = await db.scalar(select(DocumentIntelligenceAnalysis).where(
            DocumentIntelligenceAnalysis.id == analysis_id,
            DocumentIntelligenceAnalysis.tenant_id == tenant_id,
        ).with_for_update())
        if analysis and analysis.status in {"queued", "processing"}:
            analysis.status = "failed"
            analysis.error = (str(error) or "Falha inesperada na análise documental.")[:500]


async def _run_evaluation(run_id: str, tenant_id: str) -> str:
    try:
        return await _run_evaluation_impl(run_id, tenant_id)
    except Exception as exc:
        await _mark_evaluation_failed(run_id, tenant_id, exc)
        return "failed"


async def _run_document_intelligence(analysis_id: str, tenant_id: str) -> str:
    try:
        return await _run_document_intelligence_impl(analysis_id, tenant_id)
    except Exception as exc:
        await _mark_intelligence_failed(analysis_id, tenant_id, exc)
        return "failed"


@celery_app.task(name="documents.run_ai_evaluation", queue="documents", acks_late=True, reject_on_worker_lost=True, soft_time_limit=270, time_limit=300)
def run_ai_evaluation(run_id: str, tenant_id: str):
    try:
        return asyncio.run(_run_evaluation(run_id, tenant_id))
    finally:
        asyncio.run(engine.dispose())


@celery_app.task(name="documents.run_intelligence", queue="documents", acks_late=True, reject_on_worker_lost=True, soft_time_limit=270, time_limit=300)
def run_document_intelligence(analysis_id: str, tenant_id: str):
    try:
        return asyncio.run(_run_document_intelligence(analysis_id, tenant_id))
    finally:
        asyncio.run(engine.dispose())
