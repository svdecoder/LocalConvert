from pathlib import Path
from unittest.mock import patch

import pytest

from app.converters.ebooks import EbookConverter
from app.engines import ebook as ebook_engine
from app.engines import pdf as pdf_engine
from app.models import ConversionJob


@pytest.fixture()
def sample_epub(tmp_path) -> Path:
    path = tmp_path / "novel.epub"
    path.write_bytes(b"fake epub content")
    return path


@pytest.fixture()
def sample_pdf(tmp_path) -> Path:
    path = tmp_path / "scanbook.pdf"
    path.write_bytes(b"%PDF-1.4 fake")
    return path


def test_ebook_converter_requires_calibre(sample_epub, tmp_path):
    with patch.object(ebook_engine, "is_available", return_value=False):
        converter = EbookConverter()
        job = ConversionJob(input_path=sample_epub, output_format="pdf", output_dir=tmp_path / "out")
        result = converter.convert(job)
    assert result.success is False
    assert "Calibre" in result.error_message


def test_epub_to_pdf_preserves_chapters(sample_epub, tmp_path):
    def fake_convert(input_path, output_path, metadata_options=None, extra_args=None, timeout=300):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"%PDF-1.4 fake")
        return output_path

    with patch.object(ebook_engine, "is_available", return_value=True), \
         patch.object(ebook_engine, "convert_with_calibre", side_effect=fake_convert), \
         patch.object(pdf_engine, "validate_pdf_output", return_value=[]):
        converter = EbookConverter()
        job = ConversionJob(input_path=sample_epub, output_format="pdf", output_dir=tmp_path / "out")
        result = converter.convert(job)

    assert result.success
    assert result.preserved.chapters is True
    assert result.preserved.table_of_contents is True
    assert not result.warnings  # no special warning needed for non-PDF source


def test_pdf_to_epub_warns_about_reconstruction(sample_pdf, tmp_path):
    def fake_convert(input_path, output_path, metadata_options=None, extra_args=None, timeout=300):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake epub bytes")
        return output_path

    with patch.object(ebook_engine, "is_available", return_value=True), \
         patch.object(ebook_engine, "convert_with_calibre", side_effect=fake_convert):
        converter = EbookConverter()
        job = ConversionJob(input_path=sample_pdf, output_format="epub", output_dir=tmp_path / "out")
        result = converter.convert(job)

    assert result.success
    assert result.preserved.chapters is False
    assert any("heuristically reconstructed" in w.message.lower() for w in result.warnings)
