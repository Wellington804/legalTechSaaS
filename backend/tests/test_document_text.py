import io
import unittest

from docx import Document

from app.services.document_text import citation_chunks, extract_upload_text


class DocumentTextTests(unittest.TestCase):
    def test_extracts_utf8_and_docx_with_a_hard_bound(self):
        self.assertEqual(extract_upload_text("text/plain", "Texto jurídico".encode()), "Texto jurídico")
        document = Document()
        document.add_paragraph("Fato informado")
        table = document.add_table(rows=1, cols=1)
        table.cell(0, 0).text = "Documento citado"
        output = io.BytesIO()
        document.save(output)
        self.assertEqual(extract_upload_text(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document", output.getvalue()
        ), "Fato informado\nDocumento citado")

    def test_citations_are_exact_and_rank_relevant_passages(self):
        text = "Primeiro trecho sem relação.\n\nA obrigação venceu em 10 de agosto e não foi paga."
        chunks = citation_chunks(text, "Quando venceu a obrigação?")
        self.assertEqual(chunks[0]["label"], "D1")
        self.assertIn("obrigação venceu", chunks[0]["excerpt"])
        self.assertIn(chunks[0]["excerpt"], text)


if __name__ == "__main__":
    unittest.main()
