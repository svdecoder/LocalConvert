from pathlib import Path
from unittest.mock import patch

import pytest

from app.converters.documents import DocumentConverter
from app.engines import office as office_engine
from app.engines import pandoc_engine
from app.engines import pdf as pdf_engine
from app.models import ConversionJob


@pytest.fixture()
def sample_docx(tmp_path) -> Path:
    path = tmp_path / "report.docx"
    path.write_bytes(b"fake docx content")
    return path


@pytest.fixture()
def sample_md(tmp_path) -> Path:
    path = tmp_path / "notes.md"
    path.write_text("# Title\n\nSome text.")
    return path


def test_docx_to_pdf_requires_libreoffice(sample_docx, tmp_path):
    with patch.object(office_engine, "is_available", return_value=False):
        converter = DocumentConverter()
        job = ConversionJob(input_path=sample_docx, output_format="pdf", output_dir=tmp_path / "out")
        result = converter.convert(job)
    assert result.success is False
    assert "LibreOffice" in result.error_message


def test_docx_to_pdf_uses_libreoffice_and_validates(sample_docx, tmp_path):
    def fake_convert(input_path, out_fmt, out_dir, workspace, timeout=300):
        produced = out_dir / f"{input_path.stem}.pdf"
        produced.parent.mkdir(parents=True, exist_ok=True)
        produced.write_bytes(b"%PDF-1.4 fake")
        return produced

    with patch.object(office_engine, "is_available", return_value=True), \
         patch.object(office_engine, "convert_with_libreoffice", side_effect=fake_convert), \
         patch.object(pdf_engine, "validate_pdf_output", return_value=[]):
        converter = DocumentConverter()
        job = ConversionJob(input_path=sample_docx, output_format="pdf", output_dir=tmp_path / "out")
        result = converter.convert(job)

    assert result.success
    assert result.output_path.exists()
    assert result.preserved.formatting is True
    assert result.backend_used == "LibreOffice"


def test_markdown_to_pdf_falls_back_without_libreoffice(sample_md, tmp_path):
    def fake_html_to_pdf(html_path, output_path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"%PDF-1.4 fake")
        return output_path

    def fake_pandoc_convert(input_path, output_path, from_format=None, to_format=None, extra_args=None, timeout=180):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("<html><body>Title</body></html>")
        return output_path

    with patch.object(office_engine, "is_available", return_value=False), \
         patch.object(pdf_engine, "is_available", return_value=True), \
         patch.object(pandoc_engine, "is_available", return_value=True), \
         patch.object(pandoc_engine, "convert_with_pandoc", side_effect=fake_pandoc_convert), \
         patch.object(pdf_engine, "html_to_pdf", side_effect=fake_html_to_pdf), \
         patch.object(pdf_engine, "validate_pdf_output", return_value=[]):
        converter = DocumentConverter()
        job = ConversionJob(input_path=sample_md, output_format="pdf", output_dir=tmp_path / "out")
        result = converter.convert(job)

    assert result.success
    assert any("libreoffice not found" in w.message.lower() for w in result.warnings)
    assert result.backend_used == "PyMuPDF (fallback renderer)"


def test_markdown_to_pdf_fails_clearly_with_no_tools(sample_md, tmp_path):
    with patch.object(office_engine, "is_available", return_value=False), \
         patch.object(pdf_engine, "is_available", return_value=False):
        converter = DocumentConverter()
        job = ConversionJob(input_path=sample_md, output_format="pdf", output_dir=tmp_path / "out")
        result = converter.convert(job)

    assert result.success is False
    assert "LibreOffice or PyMuPDF" in result.error_message


def test_unsupported_document_pair_reports_clearly(tmp_path):
    input_path = tmp_path / "data.xyz123"
    input_path.write_text("data")
    converter = DocumentConverter()
    job = ConversionJob(input_path=input_path, output_format="zzz", output_dir=tmp_path / "out")
    result = converter.convert(job)
    assert result.success is False
    assert "No document conversion pipeline" in result.error_message
