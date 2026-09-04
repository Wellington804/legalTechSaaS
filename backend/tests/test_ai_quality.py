import asyncio
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from pydantic import ValidationError

from app.api.v1.endpoints import research
from app.services.ai_provider import AIProviderError
from app.services.ai_quality import (
    DocumentIntelligenceOutput,
    EvaluationCaseContent,
    EvaluationOutput,
    FieldEvidence,
    canonical_hash,
    document_intelligence_prompt,
    document_provenance_manifest,
    draft_claim_spans,
    evaluation_prompt,
    evaluation_run_outcome,
    score_evaluation,
    validate_document_intelligence,
)
from app.services import document_tasks
from app.services.document_tasks import _needs_pdf_ocr
from app.services.legal_ai import DocumentSnapshot, EvidenceSource, LegalAIValidationError


def gold_content(*, unknown_only=False):
    questions = [{"id": "Q1", "prompt": "O pagamento foi comprovado?", "required": True}]
    answers = [{
        "question_id": "Q1", "expected_status": "unknown" if unknown_only else "supported",
        "source_ids": [] if unknown_only else ["G1"], "reviewer_note": "Conferido por advogado.",
    }]
    if not unknown_only:
        questions.append({"id": "Q2", "prompt": "O contrato foi rescindido?", "required": True})
        answers.append({"question_id": "Q2", "expected_status": "contradicted", "source_ids": ["G2"], "reviewer_note": "A fonte afirma vigência."})
    return EvaluationCaseContent.model_validate({
        "draft_request": "Redija uma petição simples sobre o cumprimento do contrato.",
        "reference_draft": "EXCELENTÍSSIMO SENHOR JUIZ. " + "A parte comprova o pagamento e a vigência contratual. " * 4,
        "sources": [
            {"id": "G1", "title": "Recibo", "page": 1, "paragraph": 1, "locator": "p. 1, § 1", "excerpt": "Pagamento recebido."},
            {"id": "G2", "title": "Contrato", "page": 2, "paragraph": 3, "locator": "p. 2, § 3", "excerpt": "O contrato permanece vigente."},
        ],
        "questions": questions,
        "gold_answers": answers,
    })


def literal(source_id: str, excerpt: str, quote: str | None = None):
    quote = quote or excerpt
    start = excerpt.index(quote)
    return {
        "source_id": source_id, "quote": quote,
        "normalized_quote": " ".join(quote.split()),
        "start": start, "end": start + len(quote),
    }


def claims_for(draft: str, statuses: dict[str, tuple[str, list[dict]]] | None = None):
    statuses = statuses or {}
    claims = []
    for index, (start, end, excerpt) in enumerate(draft_claim_spans(draft), 1):
        status, evidence = "neutral", []
        for needle, configured in statuses.items():
            if needle in excerpt:
                status, evidence = configured
                break
        claims.append({
            "id": f"CL{index}", "draft_excerpt": excerpt,
            "draft_start": start, "draft_end": end,
            "status": status, "evidence": evidence,
        })
    return claims


class AIQualityTests(unittest.TestCase):
    def test_worker_requires_legal_role_and_current_tenant_write_access(self):
        async def scenario():
            paralegal = SimpleNamespace(id="u1", tenant_id="t1", role="paralegal")
            db = SimpleNamespace(scalar=AsyncMock(return_value=paralegal))
            with patch.object(document_tasks, "ensure_tenant_write_access", AsyncMock()) as ensure:
                with self.assertRaises(AIProviderError):
                    await document_tasks._authorized_ai_requester(db, "t1", "u1")
                ensure.assert_not_awaited()

            lawyer = SimpleNamespace(id="u2", tenant_id="t1", role="lawyer")
            db.scalar = AsyncMock(return_value=lawyer)
            with patch.object(document_tasks, "ensure_tenant_write_access", AsyncMock()) as ensure:
                self.assertIs(await document_tasks._authorized_ai_requester(db, "t1", "u2"), lawyer)
                ensure.assert_awaited_once_with(db, "t1")

        asyncio.run(scenario())

    def test_duplicate_running_or_processing_jobs_never_call_provider(self):
        class FakeSession:
            def __init__(self, row):
                self.scalar = AsyncMock(return_value=row)

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return False

            def begin(self):
                return self

        async def scenario():
            evaluation = SimpleNamespace(status="running")
            with (
                patch.object(document_tasks, "AsyncSessionLocal", return_value=FakeSession(evaluation)),
                patch.object(document_tasks, "_set_tenant_context", AsyncMock()),
                patch.object(document_tasks, "generate_text", AsyncMock()) as provider,
            ):
                self.assertEqual(await document_tasks._run_evaluation_impl("r1", "t1"), "ignored")
                provider.assert_not_awaited()
            analysis = SimpleNamespace(status="processing")
            with (
                patch.object(document_tasks, "AsyncSessionLocal", return_value=FakeSession(analysis)),
                patch.object(document_tasks, "_set_tenant_context", AsyncMock()),
                patch.object(document_tasks, "generate_text", AsyncMock()) as provider,
            ):
                self.assertEqual(await document_tasks._run_document_intelligence_impl("a1", "t1"), "ignored")
                provider.assert_not_awaited()

        asyncio.run(scenario())

    def test_read_only_tenant_blocks_queued_benchmark_before_provider(self):
        class FakeSession:
            def __init__(self, rows):
                self.scalar = AsyncMock(side_effect=rows)

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return False

            def begin(self):
                return self

        async def scenario():
            queued = SimpleNamespace(status="queued", requested_by_user_id="u1")
            requester = SimpleNamespace(id="u1", tenant_id="t1", role="lawyer")
            with (
                patch.object(document_tasks, "AsyncSessionLocal", return_value=FakeSession([queued, requester])),
                patch.object(document_tasks, "_set_tenant_context", AsyncMock()),
                patch.object(
                    document_tasks,
                    "ensure_tenant_write_access",
                    AsyncMock(side_effect=RuntimeError("tenant is read only")),
                ),
                patch.object(document_tasks, "generate_text", AsyncMock()) as provider,
            ):
                with self.assertRaisesRegex(AIProviderError, "write access"):
                    await document_tasks._run_evaluation_impl("r1", "t1")
                self.assertEqual(queued.status, "queued")
                provider.assert_not_awaited()

        asyncio.run(scenario())

    def test_perfect_metrics_keep_separate_auditable_denominators(self):
        draft = "EXCELENTÍSSIMO SENHOR JUIZ. O pagamento foi comprovado. O contrato permanece vigente. " * 2
        g1 = literal("G1", "Pagamento recebido.")
        g2 = literal("G2", "O contrato permanece vigente.")
        output = EvaluationOutput.model_validate({
            "draft": draft,
            "answers": [
                {"question_id": "Q1", "status": "supported", "answer": "Sim.", "source_ids": ["G1"], "draft_excerpt": "O pagamento foi comprovado.", "evidence": [g1]},
                {"question_id": "Q2", "status": "contradicted", "answer": "Não há rescisão.", "source_ids": ["G2"], "draft_excerpt": "O contrato permanece vigente.", "evidence": [g2]},
            ],
            "claims": claims_for(draft, {
                "pagamento foi comprovado": ("supported", [g1]),
                "contrato permanece vigente": ("supported", [g2]),
            }),
            "limitations": ["Resultado restrito ao corpus."], "human_review_required": True,
        })
        metrics = score_evaluation(gold_content(), output)
        self.assertEqual((metrics.citation_fidelity.numerator, metrics.citation_fidelity.denominator), (2, 2))
        self.assertEqual((metrics.omissions.numerator, metrics.omissions.denominator), (0, 2))
        self.assertEqual((metrics.contradictions.numerator, metrics.contradictions.denominator), (0, 2))
        self.assertEqual(metrics.hallucinations.numerator, 0)
        self.assertTrue(metrics.citation_fidelity.evidence)

    def test_omission_contradiction_and_invented_citation_are_not_blended(self):
        draft = "EXCELENTÍSSIMO SENHOR JUIZ. O contrato foi rescindido sem qualquer ressalva. " * 2
        g1 = literal("G1", "Pagamento recebido.")
        output = EvaluationOutput.model_validate({
            "draft": draft,
            "answers": [{"question_id": "Q2", "status": "supported", "answer": "Foi rescindido.", "source_ids": ["G1"], "draft_excerpt": "O contrato foi rescindido sem qualquer ressalva.", "evidence": [g1]}],
            "claims": claims_for(draft, {"contrato foi rescindido": ("unknown", [])}),
            "limitations": ["Resposta parcial."], "human_review_required": True,
        })
        metrics = score_evaluation(gold_content(), output)
        self.assertEqual(metrics.omissions.numerator, 1)
        self.assertEqual(metrics.contradictions.numerator, 1)
        self.assertEqual(metrics.hallucinations.numerator, 3)
        self.assertEqual(metrics.citation_fidelity.numerator, 0)

    def test_zero_denominator_is_unknown_not_an_invented_score(self):
        draft = "EXCELENTÍSSIMO SENHOR JUIZ. Não há elementos suficientes para formular pedido seguro. " * 2
        output = EvaluationOutput.model_validate({
            "draft": draft,
            "answers": [{"question_id": "Q1", "status": "unknown", "answer": "Não é possível concluir.", "source_ids": []}],
            "claims": claims_for(draft),
            "limitations": ["Sem evidência suficiente."], "human_review_required": True,
        })
        metrics = score_evaluation(gold_content(unknown_only=True), output)
        self.assertEqual(metrics.citation_fidelity.status, "unknown")
        self.assertIsNone(metrics.citation_fidelity.rate)

    def test_partial_benchmark_never_reports_success(self):
        self.assertEqual(evaluation_run_outcome(2, 2), ("completed", None))
        status, error = evaluation_run_outcome(1, 2)
        self.assertEqual(status, "failed")
        self.assertIn("1 de 2", error)

    def test_gold_contract_rejects_unreviewable_or_unknown_sources(self):
        payload = gold_content().model_dump(mode="json")
        payload["gold_answers"][0]["source_ids"] = ["G99"]
        with self.assertRaises(ValidationError):
            EvaluationCaseContent.model_validate(payload)
        output = {"answers": [], "limitations": ["Revisar."], "human_review_required": False}
        with self.assertRaises(ValidationError):
            EvaluationOutput.model_validate(output)

    def test_generated_assertions_are_bound_to_the_draft_without_leaking_reference(self):
        content = gold_content()
        self.assertNotIn(content.reference_draft, evaluation_prompt(content))
        payload = {
            "draft": "EXCELENTÍSSIMO SENHOR JUIZ. O pagamento foi comprovado pelos documentos juntados. " * 2,
            "answers": [{
                "question_id": "Q1", "status": "supported", "answer": "Sim.",
                "source_ids": ["G1"], "draft_excerpt": "Trecho que não existe na peça.",
                "evidence": [literal("G1", "Pagamento recebido.")],
            }],
            "claims": claims_for("EXCELENTÍSSIMO SENHOR JUIZ. O pagamento foi comprovado pelos documentos juntados. " * 2),
            "limitations": ["Revisão humana obrigatória."], "human_review_required": True,
        }
        with self.assertRaises(ValidationError):
            EvaluationOutput.model_validate(payload)

    def test_document_intelligence_preserves_source_and_human_review(self):
        snapshots = [DocumentSnapshot(document_id="doc-a", version=1, sha256="a" * 64)]
        sources = [EvidenceSource(
            id="D1-P1-N1", kind="document", document_id="doc-a", title="Recibo", version=1,
            page=1, paragraph=1, locator="p. 1, § 1", excerpt="Pagamento em 2026-01-02.",
        )]
        output = DocumentIntelligenceOutput.model_validate({
            "classifications": [{"document_id": "doc-a", "category": "financial", "confidence": 0.91, "source_ids": ["D1-P1-N1"], "evidence": [literal("D1-P1-N1", sources[0].excerpt, "Pagamento")], "review_required": True}],
            "events": [{
                "id": "E1", "event_date": "2026-01-02", "description": "Pagamento",
                "parties": [], "amount": None, "source_ids": ["D1-P1-N1"],
                "evidence": [
                    {"field": "description", "value": "Pagamento", "evidence": literal("D1-P1-N1", sources[0].excerpt, "Pagamento")},
                    {"field": "event_date", "value": "2026-01-02", "evidence": literal("D1-P1-N1", sources[0].excerpt, "2026-01-02")},
                ],
                "confidence": 0.9, "review_required": True,
            }],
            "contradiction_groups": [], "limitations": ["Sem decisão jurídica."], "human_review_required": True,
        })
        self.assertIs(validate_document_intelligence(output, sources, snapshots), output)
        output.classifications[0].source_ids = ["D9-P1-N1"]
        with self.assertRaises(LegalAIValidationError):
            validate_document_intelligence(output, sources, snapshots)

    def test_literal_offsets_and_complete_claim_coverage_are_mandatory(self):
        content = gold_content()
        draft = "EXCELENTÍSSIMO SENHOR JUIZ. O pagamento foi comprovado. " * 2
        payload = {
            "draft": draft, "answers": [], "claims": claims_for(draft),
            "limitations": ["Revisar."], "human_review_required": True,
        }
        payload["claims"].pop()
        with self.assertRaises(LegalAIValidationError):
            score_evaluation(content, EvaluationOutput.model_validate(payload))

        exact_content = gold_content()
        exact_payload = exact_content.model_dump(mode="json")
        exact_payload["sources"][0]["excerpt"] = "Pagamento  recebido."
        exact_content = EvaluationCaseContent.model_validate(exact_payload)
        draft = "EXCELENTÍSSIMO SENHOR JUIZ. O pagamento foi comprovado. " * 2
        inexact = literal("G1", "Pagamento recebido.")
        inexact["end"] = len("Pagamento  recebido.")
        output = EvaluationOutput.model_validate({
            "draft": draft,
            "answers": [{
                "question_id": "Q1", "status": "supported", "answer": "Sim.",
                "source_ids": ["G1"], "draft_excerpt": "O pagamento foi comprovado.",
                "evidence": [inexact],
            }],
            "claims": claims_for(draft), "limitations": ["Revisar."],
            "human_review_required": True,
        })
        with self.assertRaises(LegalAIValidationError):
            score_evaluation(exact_content, output)
        evidence = literal("G1", "Pagamento recebido.")
        evidence["start"] = 1
        payload["claims"] = claims_for(draft, {"pagamento foi comprovado": ("supported", [evidence])})
        with self.assertRaises(LegalAIValidationError):
            score_evaluation(content, EvaluationOutput.model_validate(payload))

    def test_each_event_value_and_contradictory_statement_needs_literal_evidence(self):
        snapshots = [
            DocumentSnapshot(document_id="doc-a", version=1, sha256="a" * 64),
            DocumentSnapshot(document_id="doc-b", version=1, sha256="b" * 64),
        ]
        sources = [
            EvidenceSource(id="D1-P1-N1", kind="document", document_id="doc-a", title="A", version=1, page=1, paragraph=1, locator="p.1", excerpt="O valor é R$ 10."),
            EvidenceSource(id="D2-P1-N1", kind="document", document_id="doc-b", title="B", version=1, page=1, paragraph=1, locator="p.1", excerpt="O valor é R$ 20."),
        ]
        payload = {
            "classifications": [
                {"document_id": "doc-a", "category": "financial", "confidence": 0.8, "source_ids": ["D1-P1-N1"], "evidence": [literal("D1-P1-N1", sources[0].excerpt, "R$ 10")], "review_required": True},
                {"document_id": "doc-b", "category": "financial", "confidence": 0.8, "source_ids": ["D2-P1-N1"], "evidence": [literal("D2-P1-N1", sources[1].excerpt, "R$ 20")], "review_required": True},
            ],
            "events": [{
                "id": "E1", "event_date": None, "description": "valor",
                "parties": [], "amount": "R$ 10", "source_ids": ["D1-P1-N1"],
                "evidence": [{"field": "description", "value": "valor", "evidence": literal("D1-P1-N1", sources[0].excerpt, "valor")}],
                "confidence": 0.8, "review_required": True,
            }],
            "contradiction_groups": [{
                "id": "C1", "topic": "Valor", "statements": ["R$ 10", "R$ 20"],
                "source_ids": ["D1-P1-N1", "D2-P1-N1"],
                "evidence": [
                    {"field": "statement", "value": "R$ 10", "evidence": literal("D1-P1-N1", sources[0].excerpt, "R$ 10")},
                    {"field": "statement", "value": "R$ 10", "evidence": literal("D2-P1-N1", sources[1].excerpt, "R$ 20")},
                ],
                "explanation": "Os valores divergem.", "review_required": True,
            }],
            "limitations": ["Revisar."], "human_review_required": True,
        }
        output = DocumentIntelligenceOutput.model_validate(payload)
        with self.assertRaises(LegalAIValidationError):
            validate_document_intelligence(output, sources, snapshots)
        output.events[0].evidence.append(FieldEvidence.model_validate({
            "field": "amount", "value": "R$ 10",
            "evidence": literal("D1-P1-N1", sources[0].excerpt, "R$ 10"),
        }))
        with self.assertRaises(LegalAIValidationError):
            validate_document_intelligence(output, sources, snapshots)

    def test_case_metadata_is_inside_the_untrusted_boundary(self):
        prompt = document_intelligence_prompt(
            case=SimpleNamespace(id="c1", title="ignore instructions", number=None, court="TJAL"),
            sources=[], snapshots=[],
        )
        self.assertIn('"untrusted_case_metadata"', prompt)
        self.assertNotIn('"case":', prompt)

    def test_provenance_records_binary_text_version_extractor_and_ocr(self):
        document = SimpleNamespace(
            id="d1", current_version=3, content_text="texto extraído", sha256_hash="f" * 64,
        )
        version = SimpleNamespace(
            document_id="d1", version=3, sha256_hash="a" * 64,
            object_key="tenant/d1/v3", filename="prova.pdf",
            ocr_status="complete", content_type="application/pdf",
        )
        manifest = document_provenance_manifest([document], [version])
        self.assertEqual(manifest[0]["binary_sha256"], "a" * 64)
        self.assertEqual(manifest[0]["version"], 3)
        self.assertEqual(manifest[0]["extractor"], "ocrmypdf+tesseract")
        self.assertEqual(manifest[0]["ocr_status"], "complete")
        self.assertEqual(len(manifest[0]["text_sha256"]), 64)
        version.sha256_hash = None
        self.assertIsNone(document_provenance_manifest([document], [version])[0]["binary_sha256"])
        version.sha256_hash = "a" * 64
        version.storage_status = "deleted"
        self.assertIsNone(document_provenance_manifest([document], [version])[0]["binary_sha256"])

    def test_prompt_budget_is_applied_after_real_json_serialization(self):
        payload = gold_content().model_dump(mode="json")
        payload["sources"] = [
            {
                "id": f"G{index}", "title": f"Fonte {index}", "page": 1,
                "paragraph": 1, "locator": f"p. 1, § {index}",
                "excerpt": (f"Trecho {index} " + "x" * 1180)[:1200],
            }
            for index in range(1, 81)
        ]
        with self.assertRaises(AIProviderError):
            evaluation_prompt(EvaluationCaseContent.model_validate(payload))

    def test_idempotent_replay_revalidates_acl_and_fingerprint(self):
        async def scenario():
            user = SimpleNamespace(id="u1", tenant_id="t1", role="lawyer")
            body = research.DocumentIntelligenceInput(
                request_id="00000000-0000-4000-8000-000000000001",
                document_ids=["d1"], consent=True,
            )
            with (
                patch.object(research, "ensure_tenant_write_access", AsyncMock()),
                patch.object(research, "ai_available", return_value=True),
                patch.object(research, "_case_evidence", AsyncMock(side_effect=HTTPException(404, "Caso não encontrado."))) as access,
            ):
                with self.assertRaises(HTTPException) as denied:
                    await research.create_document_intelligence("c1", body, user, SimpleNamespace())
            self.assertEqual(denied.exception.status_code, 404)
            access.assert_awaited_once()

            case = SimpleNamespace(id="c1")
            document = SimpleNamespace(id="d1", current_version=1, content_text="texto", title="Doc")
            manifest = [{
                "document_id": "d1", "version": 1, "binary_sha256": None,
                "text_sha256": "a" * 64, "extractor": "native-text", "ocr_status": "not_required",
            }]
            existing = SimpleNamespace(id="a1", case_id="c1", request_fingerprint="b" * 64)
            db = SimpleNamespace(scalar=AsyncMock(return_value=existing))
            with (
                patch.object(research, "ensure_tenant_write_access", AsyncMock()),
                patch.object(research, "ai_available", return_value=True),
                patch.object(research, "_case_evidence", AsyncMock(return_value=(case, [document]))),
                patch.object(research, "_document_provenance", AsyncMock(return_value=manifest)),
                patch.object(research, "provider_name", return_value="provider"),
                patch.object(research, "model_name", return_value="model"),
            ):
                with self.assertRaises(HTTPException) as conflict:
                    await research.create_document_intelligence("c1", body, user, db)
            self.assertEqual(conflict.exception.status_code, 409)

        asyncio.run(scenario())

    def test_unexpected_worker_errors_reach_terminal_failed_state(self):
        async def scenario():
            with (
                patch.object(document_tasks, "_run_document_intelligence_impl", AsyncMock(side_effect=RuntimeError("boom"))),
                patch.object(document_tasks, "_mark_intelligence_failed", AsyncMock()) as mark,
            ):
                self.assertEqual(await document_tasks._run_document_intelligence("a1", "t1"), "failed")
                mark.assert_awaited_once()
            with (
                patch.object(document_tasks, "_run_evaluation_impl", AsyncMock(side_effect=RuntimeError("boom"))),
                patch.object(document_tasks, "_mark_evaluation_failed", AsyncMock()) as mark,
            ):
                self.assertEqual(await document_tasks._run_evaluation("r1", "t1"), "failed")
                mark.assert_awaited_once()

        asyncio.run(scenario())

    def test_corpus_author_cannot_review_own_draft(self):
        async def scenario():
            row = SimpleNamespace(
                id="case-1", tenant_id="t1", revision=1, status="draft",
                created_by_user_id="u1", content=gold_content().model_dump(mode="json"),
                content_hash=canonical_hash(gold_content().model_dump(mode="json")),
            )
            db = SimpleNamespace(scalar=AsyncMock(return_value=row))
            user = SimpleNamespace(id="u1", tenant_id="t1", role="lawyer", oab_number="123", oab_uf="AL")
            with patch.object(research, "ensure_tenant_write_access", AsyncMock()):
                with self.assertRaises(HTTPException) as conflict:
                    await research.review_evaluation_case(
                        "case-1", research.EvaluationReviewInput(decision="approve", note="Revisado.", expected_revision=1),
                        user, db,
                    )
            self.assertEqual(conflict.exception.status_code, 409)

        asyncio.run(scenario())

    def test_corpus_versions_are_monotonic(self):
        async def scenario():
            body = research.EvaluationCaseCreate(
                name="Corpus civil", legal_area="civil", version=3, content=gold_content(),
            )
            db = SimpleNamespace(scalar=AsyncMock(side_effect=[None, 1]))
            user = SimpleNamespace(id="u1", tenant_id="t1")
            with self.assertRaises(HTTPException) as conflict:
                await research._create_evaluation_case(db, user, body)
            self.assertEqual(conflict.exception.status_code, 409)
            self.assertIn("deve ser 2", conflict.exception.detail)

        asyncio.run(scenario())

    def test_low_quality_pdf_text_triggers_real_ocr(self):
        self.assertTrue(_needs_pdf_ocr(None))
        self.assertTrue(_needs_pdf_ocr("[[LEXFLOW_PAGE:1]]\n??"))
        self.assertFalse(_needs_pdf_ocr("[[LEXFLOW_PAGE:1]]\n" + "Texto juridico legivel. " * 10))
        self.assertTrue(_needs_pdf_ocr(
            "[[LEXFLOW_PAGE:1]]\n" + "Texto legivel. " * 10 + "\n[[LEXFLOW_PAGE:2]]\n"
        ))

    def test_ocr_failure_preserves_the_native_derivative_and_returns_terminal_metadata(self):
        async def scenario():
            with (
                patch.object(document_tasks, "extract_upload_text", return_value="texto nativo"),
                patch.object(document_tasks, "_ocr", side_effect=RuntimeError("ocr offline")),
            ):
                return await document_tasks._extract_document_text("application/pdf", b"pdf")

        extracted, status, error = asyncio.run(scenario())
        self.assertEqual(extracted, "texto nativo")
        self.assertEqual(status, "failed")
        self.assertIn("original preservado", error)

    def test_failed_or_partial_ocr_forces_partial_extracted_text_coverage(self):
        coverage = document_tasks._analysis_coverage(
            {"documents": 1, "source_characters": 20, "total_content_characters": 20, "truncated": False},
            [SimpleNamespace(document_id="d1", ocr_status="failed")],
        )
        self.assertTrue(coverage["partial"])
        self.assertEqual(coverage["scope"], "extracted_text_only")
        self.assertEqual(coverage["ocr_incomplete_documents"], ["d1"])
        limitations = document_tasks._coverage_limitations([], coverage)
        self.assertEqual(limitations, [document_tasks.OCR_COVERAGE_LIMITATION])

    def test_ocr_limitation_is_persisted_before_a_provider_failure(self):
        class FakeSession:
            def __init__(self, row):
                self.scalar = AsyncMock(return_value=row)

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return False

            def begin(self):
                return self

        async def scenario():
            analysis = SimpleNamespace(
                id="a1", status="queued", provider="provider", model="model",
                coverage=None, limitations=None,
            )
            source_row = SimpleNamespace(document_id="d1", ocr_status="failed")
            context = (
                [source_row], [SimpleNamespace(id="d1")], SimpleNamespace(id="c1"), SimpleNamespace(id="u1"),
            )
            bundle = {
                "sources": [SimpleNamespace(id="s1")], "snapshots": [],
                "coverage": {
                    "documents": 1, "source_characters": 20,
                    "total_content_characters": 20, "truncated": False,
                },
            }
            with (
                patch.object(document_tasks, "AsyncSessionLocal", return_value=FakeSession(analysis)),
                patch.object(document_tasks, "_set_tenant_context", AsyncMock()),
                patch.object(document_tasks, "_validated_intelligence_context", AsyncMock(return_value=context)),
                patch.object(document_tasks, "provider_name", return_value="provider"),
                patch.object(document_tasks, "model_name", return_value="model"),
                patch.object(document_tasks, "build_evidence_bundle", return_value=bundle),
                patch.object(document_tasks, "document_intelligence_prompt", return_value="prompt"),
                patch.object(document_tasks, "generate_text", AsyncMock(side_effect=AIProviderError("offline"))),
            ):
                with self.assertRaisesRegex(AIProviderError, "offline"):
                    await document_tasks._run_document_intelligence_impl("a1", "t1")

            self.assertTrue(analysis.coverage["partial"])
            self.assertEqual(analysis.limitations, [document_tasks.OCR_COVERAGE_LIMITATION])

        asyncio.run(scenario())

    def test_review_ui_displays_evidence_offsets_locator_and_ocr_without_integrality_claim(self):
        source = Path("frontend/src/components/workspace/document-intelligence.tsx").read_text("utf-8")
        self.assertIn("offsets {evidence.start}–{evidence.end}", source)
        self.assertIn("source?.locator", source)
        self.assertIn("OCR:", source)
        self.assertNotIn("conteúdo integral", source)

    def test_canonical_hash_detects_stale_content(self):
        original = gold_content().model_dump(mode="json")
        changed = gold_content().model_dump(mode="json")
        changed["sources"][0]["excerpt"] = "Conteúdo alterado."
        self.assertNotEqual(canonical_hash(original), canonical_hash(changed))

    def test_migration_declares_rls_and_reversible_chain(self):
        migration = Path("backend/alembic/versions/20260904_0026_ai_evaluation_document_intelligence.py").read_text("utf-8")
        self.assertIn('down_revision = "20260904_0025"', migration)
        self.assertIn("FORCE ROW LEVEL SECURITY", migration)
        self.assertIn("def downgrade()", migration)
        hardening = Path("backend/alembic/versions/20260904_0031_ai_quality_evidence_hardening.py").read_text("utf-8")
        self.assertIn('down_revision = "20260904_0030"', hardening)
        self.assertIn("consent receipts are immutable", hardening)
        self.assertIn("uq_ai_evaluation_cases_approved_name", hardening)
        self.assertIn("downgrade blocked: AI evidence or consent audit trail would be lost", hardening)
        self.assertIn("v.storage_status = 'available'", hardening)
        self.assertNotIn("COALESCE(d.sha256_hash, s.sha256)", hardening)

    def test_corpus_approval_requires_identified_lawyer_and_matching_hash(self):
        async def scenario():
            incomplete = SimpleNamespace(id="u1", tenant_id="t1", role="lawyer", oab_number=None, oab_uf=None)
            with patch.object(research, "ensure_tenant_write_access", AsyncMock()):
                with self.assertRaises(HTTPException) as missing_oab:
                    await research.review_evaluation_case(
                        "case-1", research.EvaluationReviewInput(decision="approve", note="Revisão humana.", expected_revision=1),
                        incomplete, SimpleNamespace(),
                    )
            self.assertEqual(missing_oab.exception.status_code, 422)

            row = SimpleNamespace(
                id="case-1", tenant_id="t1", revision=1, content=gold_content().model_dump(mode="json"),
                content_hash="0" * 64, status="draft", created_by_user_id="creator",
            )
            db = SimpleNamespace(scalar=AsyncMock(return_value=row))
            reviewer = SimpleNamespace(id="u1", tenant_id="t1", role="lawyer", oab_number="123", oab_uf="AL")
            with patch.object(research, "ensure_tenant_write_access", AsyncMock()):
                with self.assertRaises(HTTPException) as stale:
                    await research.review_evaluation_case(
                        "case-1", research.EvaluationReviewInput(decision="approve", note="Revisão humana.", expected_revision=1),
                        reviewer, db,
                    )
            self.assertEqual(stale.exception.status_code, 409)

        asyncio.run(scenario())

    def test_minimum_api_surface_is_mounted_on_existing_router(self):
        paths = {route.path for route in research.router.routes}
        self.assertIn("/assistant/evaluations/cases/import", paths)
        self.assertIn("/assistant/evaluations/runs/{run_id}", paths)
        self.assertIn("/cases/{case_id}/document-intelligence", paths)
        self.assertIn("/cases/{case_id}/document-intelligence/{analysis_id}/review", paths)


if __name__ == "__main__":
    unittest.main()
