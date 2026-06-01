"""Unit tests for parser service and parser factory behavior."""

from pathlib import Path

import fitz
import pytest
from docx import Document

from app.services.parser_service import DocumentParserFactory, ParserService
from app.utils.exceptions import EmptyDocumentError, UnsupportedFileTypeError


def create_pdf(path: Path, text: str) -> None:
    """Create a simple PDF with provided text for testing."""

    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), text)
    pdf.save(path)
    pdf.close()


def create_docx(path: Path, paragraphs: list[str]) -> None:
    """Create a DOCX file with paragraph content for testing."""

    doc = Document()
    for paragraph in paragraphs:
        doc.add_paragraph(paragraph)
    doc.save(path)


def test_pdf_parsing(tmp_path: Path) -> None:
    """ParserService should extract PDF text content successfully."""

    file_path = tmp_path / "sample.pdf"
    create_pdf(file_path, "Hello PDF parser world")

    service = ParserService()
    result = service.parse_file(str(file_path))

    assert result.extraction_success is True
    assert "Hello PDF parser world" in result.content
    assert result.word_count >= 4


def test_docx_parsing(tmp_path: Path) -> None:
    """ParserService should extract DOCX paragraph content in order."""

    file_path = tmp_path / "sample.docx"
    create_docx(file_path, ["First paragraph", "Second paragraph"])

    service = ParserService()
    result = service.parse_file(str(file_path))

    assert result.extraction_success is True
    assert "First paragraph" in result.content
    assert "Second paragraph" in result.content


def test_txt_parsing(tmp_path: Path) -> None:
    """ParserService should extract UTF-8 TXT content."""

    file_path = tmp_path / "sample.txt"
    file_path.write_text("plain text document with enough words", encoding="utf-8")

    service = ParserService()
    result = service.parse_file(str(file_path))

    assert result.extraction_success is True
    assert result.word_count >= 5


def test_unsupported_type(tmp_path: Path) -> None:
    """Factory should reject unsupported file types."""

    file_path = tmp_path / "sample.csv"
    file_path.write_text("a,b,c", encoding="utf-8")

    with pytest.raises(UnsupportedFileTypeError):
        DocumentParserFactory.get_parser(file_path)


def test_empty_content_validation() -> None:
    """validate_content should fail when content is empty."""

    service = ParserService()

    with pytest.raises(EmptyDocumentError):
        service.validate_content("   ")


def test_validation_rules_short_content() -> None:
    """validate_content should fail when content is too short."""

    service = ParserService()

    with pytest.raises(EmptyDocumentError):
        service.validate_content("short")


def test_factory_selection(tmp_path: Path) -> None:
    """Factory should choose parser by extension."""

    pdf_path = tmp_path / "a.pdf"
    docx_path = tmp_path / "b.docx"
    txt_path = tmp_path / "c.txt"

    pdf_path.write_text("x", encoding="utf-8")
    docx_path.write_text("x", encoding="utf-8")
    txt_path.write_text("x", encoding="utf-8")

    assert DocumentParserFactory.get_parser(pdf_path).__class__.__name__ == "PDFParser"
    assert (
        DocumentParserFactory.get_parser(docx_path).__class__.__name__ == "DOCXParser"
    )
    assert DocumentParserFactory.get_parser(txt_path).__class__.__name__ == "TXTParser"
