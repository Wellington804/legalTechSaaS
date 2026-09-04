"""Bounded text extraction for already validated office uploads."""
import io
import re
import unicodedata
import zipfile

from docx import Document
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from openpyxl import load_workbook


MAX_PAGES = 300
MAX_TEXT_CHARS = 250_000
MAX_DOCX_ENTRIES = 2_000
MAX_DOCX_UNCOMPRESSED = 40 * 1024 * 1024


class TextExtractionError(ValueError):
    pass


def _bounded(texts) -> str | None:
    result: list[str] = []
    size = 0
    for value in texts:
        text = str(value or "").replace("\x00", "").strip()
        if not text:
            continue
        remaining = MAX_TEXT_CHARS - size
        if remaining <= 0:
            break
        result.append(text[:remaining])
        size += len(result[-1]) + 1
    joined = "\n".join(result).strip()
    return joined or None


def extract_upload_text(content_type: str, content: bytes) -> str | None:
    try:
        if content_type == "text/plain":
            return _bounded([content.decode("utf-8")])
        if content_type == "application/pdf":
            reader = PdfReader(io.BytesIO(content), strict=True)
            if reader.is_encrypted or len(reader.pages) > MAX_PAGES:
                raise TextExtractionError("PDF protegido ou extenso demais para indexação.")
            return _bounded(page.extract_text() for page in reader.pages)
        if content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                entries = archive.infolist()
                if len(entries) > MAX_DOCX_ENTRIES or sum(item.file_size for item in entries) > MAX_DOCX_UNCOMPRESSED:
                    raise TextExtractionError("DOCX extenso demais para indexação.")
                if any(item.compress_size and item.file_size / item.compress_size > 200 for item in entries):
                    raise TextExtractionError("Compactação do DOCX não é segura para indexação.")
            document = Document(io.BytesIO(content))
            return _bounded([*(paragraph.text for paragraph in document.paragraphs),
                             *(cell.text for table in document.tables for row in table.rows for cell in row.cells)])
        if content_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
            workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            try:
                if len(workbook.sheetnames) > 100:
                    raise TextExtractionError("Planilha extensa demais para indexacao.")
                return _bounded(
                    cell.value
                    for sheet in workbook.worksheets
                    for row_number, row in enumerate(sheet.iter_rows(), 1)
                    if row_number <= 20_000
                    for cell in row
                )
            finally:
                workbook.close()
    except TextExtractionError:
        raise
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile, PdfReadError) as exc:
        raise TextExtractionError("Não foi possível extrair texto seguro do arquivo.") from exc
    return None


def citation_chunks(text: str, question: str, limit: int = 6) -> list[dict]:
    """Return exact, bounded excerpts ranked by query terms; never invent a source."""
    normalized = unicodedata.normalize("NFKD", question).encode("ascii", "ignore").decode().lower()
    terms = {term for term in re.findall(r"[a-z0-9]{4,}", normalized)}
    paragraphs = [part.strip() for part in re.split(r"\n{2,}", text) if part.strip()]
    chunks: list[tuple[int, str]] = []
    for paragraph_index, paragraph in enumerate(paragraphs):
        for start in range(0, len(paragraph), 1_200):
            chunks.append((paragraph_index, paragraph[start:start + 1_200]))
    ranked = sorted(enumerate(chunks), key=lambda item: (
        -sum(term in unicodedata.normalize("NFKD", item[1][1]).encode("ascii", "ignore").decode().lower() for term in terms),
        item[0],
    ))[:max(1, min(limit, 10))]
    return [{"label": f"D{position}", "paragraph": chunk[0] + 1, "excerpt": chunk[1]}
            for position, (_index, chunk) in enumerate(ranked, 1)]
