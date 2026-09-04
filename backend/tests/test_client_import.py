import io
import unittest

from fastapi import HTTPException
from openpyxl import Workbook

from app.services.client_import import parse_client_file


class ClientImportFileTests(unittest.TestCase):
    def test_csv_and_xlsx_share_bounded_mapping_contract(self):
        csv_result = parse_client_file("clientes.csv", "Nome;E-mail;CPF\nAna;ana@example.test;12345678901\n".encode())
        self.assertEqual(csv_result["suggested_mapping"], {"name": "Nome", "email": "E-mail", "tax_id": "CPF"})
        workbook = Workbook(); sheet = workbook.active
        sheet.append(["Nome", "Telefone", "Etapa"]); sheet.append(["Bruno", "+5511999999999", "Cliente"])
        content = io.BytesIO(); workbook.save(content)
        xlsx_result = parse_client_file("clientes.xlsx", content.getvalue())
        self.assertEqual(xlsx_result["row_count"], 1)
        self.assertEqual(xlsx_result["suggested_mapping"]["phone"], "Telefone")

    def test_rejects_technical_or_oversized_input(self):
        with self.assertRaises(HTTPException):
            parse_client_file("clientes.json", b"[]")
        with self.assertRaises(HTTPException):
            parse_client_file("clientes.csv", b"x" * (2 * 1024 * 1024 + 1))


if __name__ == "__main__":
    unittest.main()
