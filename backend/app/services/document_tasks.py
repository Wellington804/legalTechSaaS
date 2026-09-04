"""Quarantined document processing and lifecycle tasks."""
import asyncio
import hashlib
import re
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select, text

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
from app.core.dependencies import _set_tenant_context
from app.models.assistant import (
    AIEvaluationCase,
    AIEvaluationResult,
    AIEvaluationRun,
    DocumentIntelligenceAnalysis,
    DocumentIntelligenceSource,
)
from app.models.workspace import WorkspaceCase, WorkspaceDocument, WorkspaceDocumentUpload, WorkspaceDocumentVersion
from app.services.ai_provider import AIProviderError, generate_text, model_name, provider_name
from app.services.ai_quality import (
    DOCUMENT_INTELLIGENCE_SYSTEM_PROMPT,
    EVALUATION_SYSTEM_PROMPT,
    DocumentIntelligenceOutput,
    EvaluationCaseContent,
    EvaluationMetrics,
    EvaluationOutput,
    aggregate_evaluation_metrics,
    canonical_hash,
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
    if content_type.startswith("image/") or (content_type == "application/pdf" and _needs_pdf_ocr(extracted)):
        ocr_status = "processing"
        extracted = await asyncio.to_thread(_ocr, content_type, content)
        ocr_status = "complete" if extracted else "failed"

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
            processing_error="OCR não encontrou texto utilizável." if ocr_status == "failed" else None,
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


async def _run_evaluation(run_id: str, tenant_id: str) -> str:
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db, db.begin():
        await _set_tenant_context(db, tenant_id)
        run = await db.scalar(select(AIEvaluationRun).where(
            AIEvaluationRun.id == run_id, AIEvaluationRun.tenant_id == tenant_id,
        ).with_for_update())
        if not run or run.status not in {"queued", "running"}:
            return "ignored"
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
        run.status = "running"
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
        provider, model, requested_by = run.provider, run.model, run.requested_by_user_id

    for case_id, case_version, case_hash, raw_content in payloads:
        try:
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
        if not run:
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


async def _run_document_intelligence(analysis_id: str, tenant_id: str) -> str:
    async with AsyncSessionLocal() as db, db.begin():
        await _set_tenant_context(db, tenant_id)
        analysis = await db.scalar(select(DocumentIntelligenceAnalysis).where(
            DocumentIntelligenceAnalysis.id == analysis_id,
            DocumentIntelligenceAnalysis.tenant_id == tenant_id,
        ).with_for_update())
        if not analysis or analysis.status not in {"queued", "processing"}:
            return "ignored"
        source_rows = (await db.execute(select(DocumentIntelligenceSource).where(
            DocumentIntelligenceSource.analysis_id == analysis_id,
            DocumentIntelligenceSource.tenant_id == tenant_id,
        ).order_by(DocumentIntelligenceSource.document_id))).scalars().all()
        documents = (await db.execute(select(WorkspaceDocument).where(
            WorkspaceDocument.tenant_id == tenant_id,
            WorkspaceDocument.id.in_([row.document_id for row in source_rows]),
            WorkspaceDocument.deleted_at.is_(None),
        ))).scalars().all()
        documents = sorted(documents, key=lambda item: item.id)
        current_snapshot = sorted(({
            "document_id": document.id,
            "version": document.current_version,
            "sha256": hashlib.sha256((document.content_text or "").encode()).hexdigest(),
        } for document in documents), key=lambda item: item["document_id"])
        persisted_snapshot = sorted(({
            "document_id": row.document_id, "version": row.document_version, "sha256": row.sha256,
        } for row in source_rows), key=lambda item: item["document_id"])
        if current_snapshot != persisted_snapshot or canonical_hash(current_snapshot) != analysis.snapshot_hash:
            analysis.status = "stale"
            analysis.error = "Documentos alterados antes da análise."
            return "stale"
        if provider_name(settings) != analysis.provider or model_name(settings, "legal") != analysis.model:
            analysis.status = "stale"
            analysis.error = "A rota de IA mudou depois do agendamento."
            return "stale"
        case = await db.scalar(select(WorkspaceCase).where(
            WorkspaceCase.id == analysis.case_id, WorkspaceCase.tenant_id == tenant_id,
        ))
        if not case:
            analysis.status = "failed"
            analysis.error = "Processo não encontrado."
            return "failed"
        analysis.status = "processing"
        requested_by = analysis.requested_by_user_id

    try:
        bundle = build_evidence_bundle(documents, "classificação anexo fatos datas valores partes eventos divergências", max_source_chars=60_000)
        if not bundle["sources"]:
            raise AIProviderError("documents have no citable text")
        raw = await generate_text(
            system_prompt=DOCUMENT_INTELLIGENCE_SYSTEM_PROMPT,
            user_prompt=document_intelligence_prompt(case=case, sources=bundle["sources"], snapshots=bundle["snapshots"]),
            purpose="legal", max_output_tokens=7000, temperature=0,
            response_schema=DocumentIntelligenceOutput.model_json_schema(),
        )
        output = validate_document_intelligence(parse_document_intelligence(raw), bundle["sources"], bundle["snapshots"])
        status, error = "review_required", None
    except (AIProviderError, ValueError, TypeError) as exc:
        output, status, error = None, "failed", (str(exc) or "Falha de análise documental.")[:500]

    async with AsyncSessionLocal() as db, db.begin():
        await _set_tenant_context(db, tenant_id)
        analysis = await db.scalar(select(DocumentIntelligenceAnalysis).where(
            DocumentIntelligenceAnalysis.id == analysis_id,
            DocumentIntelligenceAnalysis.tenant_id == tenant_id,
        ).with_for_update())
        if not analysis or analysis.status not in {"processing", "queued"}:
            return "ignored"
        analysis.status = status
        analysis.error = error
        if output:
            analysis.evidence_sources = [item.model_dump(mode="json") for item in bundle["sources"]]
            analysis.classifications = [item.model_dump(mode="json") for item in sorted(output.classifications, key=lambda item: item.document_id)]
            analysis.timeline = [item.model_dump(mode="json") for item in sorted(
                output.events, key=lambda item: (item.event_date is None, item.event_date.isoformat() if item.event_date else "", item.id),
            )]
            analysis.contradiction_groups = [item.model_dump(mode="json") for item in sorted(output.contradiction_groups, key=lambda item: item.id)]
            analysis.limitations = output.limitations
            analysis.result_hash = canonical_hash({
                "evidence_sources": analysis.evidence_sources,
                "classifications": analysis.classifications,
                "timeline": analysis.timeline,
                "contradiction_groups": analysis.contradiction_groups,
                "limitations": analysis.limitations,
            })
        await AuditService.log_action(db, tenant_id, requested_by, "DOCUMENT_INTELLIGENCE_COMPLETED", "document_intelligence_analyses", analysis_id, {
            "status": status, "review_required": status == "review_required",
        })
    return status


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
