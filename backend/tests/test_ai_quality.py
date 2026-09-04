import asyncio
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from pydantic import ValidationError

from app.api.v1.endpoints import research
from app.services.ai_quality import (
    DocumentIntelligenceOutput,
    EvaluationCaseContent,
    EvaluationOutput,
    canonical_hash,
    score_evaluation,
    validate_document_intelligence,
)
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
        "sources": [
            {"id": "G1", "title": "Recibo", "page": 1, "paragraph": 1, "locator": "p. 1, § 1", "excerpt": "Pagamento recebido."},
            {"id": "G2", "title": "Contrato", "page": 2, "paragraph": 3, "locator": "p. 2, § 3", "excerpt": "O contrato permanece vigente."},
        ],
        "questions": questions,
        "gold_answers": answers,
    })


class AIQualityTests(unittest.TestCase):
    def test_perfect_metrics_keep_separate_auditable_denominators(self):
        output = EvaluationOutput.model_validate({
            "answers": [
                {"question_id": "Q1", "status": "supported", "answer": "Sim.", "source_ids": ["G1"]},
                {"question_id": "Q2", "status": "contradicted", "answer": "Não há rescisão.", "source_ids": ["G2"]},
            ],
            "limitations": ["Resultado restrito ao corpus."], "human_review_required": True,
        })
        metrics = score_evaluation(gold_content(), output)
        self.assertEqual((metrics.citation_fidelity.numerator, metrics.citation_fidelity.denominator), (2, 2))
        self.assertEqual((metrics.omissions.numerator, metrics.omissions.denominator), (0, 2))
        self.assertEqual((metrics.contradictions.numerator, metrics.contradictions.denominator), (0, 2))
        self.assertEqual(metrics.hallucinations.numerator, 0)
        self.assertTrue(metrics.citation_fidelity.evidence)

    def test_omission_contradiction_and_invented_citation_are_not_blended(self):
        output = EvaluationOutput.model_validate({
            "answers": [{"question_id": "Q2", "status": "supported", "answer": "Foi rescindido.", "source_ids": ["G9"]}],
            "limitations": ["Resposta parcial."], "human_review_required": True,
        })
        metrics = score_evaluation(gold_content(), output)
        self.assertEqual(metrics.omissions.numerator, 1)
        self.assertEqual(metrics.contradictions.numerator, 1)
        self.assertEqual(metrics.hallucinations.numerator, 1)
        self.assertEqual(metrics.citation_fidelity.numerator, 0)

    def test_zero_denominator_is_unknown_not_an_invented_score(self):
        output = EvaluationOutput.model_validate({
            "answers": [{"question_id": "Q1", "status": "unknown", "answer": "Não é possível concluir.", "source_ids": []}],
            "limitations": ["Sem evidência suficiente."], "human_review_required": True,
        })
        metrics = score_evaluation(gold_content(unknown_only=True), output)
        self.assertEqual(metrics.citation_fidelity.status, "unknown")
        self.assertIsNone(metrics.citation_fidelity.rate)

    def test_gold_contract_rejects_unreviewable_or_unknown_sources(self):
        payload = gold_content().model_dump(mode="json")
        payload["gold_answers"][0]["source_ids"] = ["G99"]
        with self.assertRaises(ValidationError):
            EvaluationCaseContent.model_validate(payload)
        output = {"answers": [], "limitations": ["Revisar."], "human_review_required": False}
        with self.assertRaises(ValidationError):
            EvaluationOutput.model_validate(output)

    def test_document_intelligence_preserves_source_and_human_review(self):
        snapshots = [DocumentSnapshot(document_id="doc-a", version=1, sha256="a" * 64)]
        sources = [EvidenceSource(
            id="D1-P1-N1", kind="document", document_id="doc-a", title="Recibo", version=1,
            page=1, paragraph=1, locator="p. 1, § 1", excerpt="Pagamento em 2 de janeiro de 2026.",
        )]
        output = DocumentIntelligenceOutput.model_validate({
            "classifications": [{"document_id": "doc-a", "category": "financial", "confidence": 0.91, "source_ids": ["D1-P1-N1"], "review_required": True}],
            "events": [{"id": "E1", "event_date": "2026-01-02", "description": "Pagamento documentado.", "parties": [], "amount": None, "source_ids": ["D1-P1-N1"], "confidence": 0.9, "review_required": True}],
            "contradiction_groups": [], "limitations": ["Sem decisão jurídica."], "human_review_required": True,
        })
        self.assertIs(validate_document_intelligence(output, sources, snapshots), output)
        output.classifications[0].source_ids = ["D9-P1-N1"]
        with self.assertRaises(LegalAIValidationError):
            validate_document_intelligence(output, sources, snapshots)

    def test_low_quality_pdf_text_triggers_real_ocr(self):
        self.assertTrue(_needs_pdf_ocr(None))
        self.assertTrue(_needs_pdf_ocr("[[LEXFLOW_PAGE:1]]\n??"))
        self.assertFalse(_needs_pdf_ocr("[[LEXFLOW_PAGE:1]]\n" + "Texto juridico legivel. " * 10))
        self.assertTrue(_needs_pdf_ocr(
            "[[LEXFLOW_PAGE:1]]\n" + "Texto legivel. " * 10 + "\n[[LEXFLOW_PAGE:2]]\n"
        ))

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
                content_hash="0" * 64,
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
