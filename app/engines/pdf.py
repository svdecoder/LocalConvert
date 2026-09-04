"""PDF engine, built on PyMuPDF (``fitz``).

Handles:
  - Rendering PDF pages to images (for OCR and for image-based fallbacks)
  - Extracting text with structural hints (blocks, headings-by-font-size)
  - Building simple PDFs from HTML (for HTML/Markdown -> PDF fallback
    without LibreOffice, and for text/EPUB -> PDF reconstruction)
  - Basic post-conversion validation (page count, non-empty content)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.utils.dependencies import check_python_package
from app.utils.logging_setup import get_logger

logger = get_logger("engines.pdf")


def is_available() -> bool:
    return check_python_package("fitz").available


class PdfEngineError(RuntimeError):
    pass


def _fitz():
    if not is_available():
        raise PdfEngineError("PyMuPDF (fitz) is not installed. Run: pip install PyMuPDF")
    import fitz  # type: ignore

    return fitz


@dataclass
class PdfInspection:
    page_count: int
    has_text: bool
    has_images: bool
    is_probably_scanned: bool
    metadata: dict
    toc: list


def inspect_pdf(path: Path) -> PdfInspection:
    fitz = _fitz()
    doc = fitz.open(str(path))
    try:
        text_chars = 0
        image_count = 0
        sample_pages = min(len(doc), 5)
        for i in range(sample_pages):
            page = doc[i]
            text_chars += len(page.get_text("text"))
            image_count += len(page.get_images(full=True))
        has_text = text_chars > 20
        has_images = image_count > 0
        is_probably_scanned = (not has_text) and has_images
        return PdfInspection(
            page_count=len(doc),
            has_text=has_text,
            has_images=has_images,
            is_probably_scanned=is_probably_scanned,
            metadata=dict(doc.metadata or {}),
            toc=doc.get_toc() or [],
        )
    finally:
        doc.close()


def render_pages_to_images(path: Path, out_dir: Path, dpi: int = 200) -> list[Path]:
    """Render every page of a PDF to PNG images (used for OCR and for
    'flatten to images' style fallback conversions)."""
    fitz = _fitz()
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(str(path))
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    output_paths = []
    try:
        for i, page in enumerate(doc):
            pix = page.get_pixmap(matrix=matrix)
            out_path = out_dir / f"page_{i + 1:04d}.png"
            pix.save(str(out_path))
            output_paths.append(out_path)
    finally:
        doc.close()
    return output_paths


def extract_structured_text(path: Path) -> list[dict]:
    """Extract per-page text blocks with font-size info, used by the
    PDF -> DOCX/Markdown reconstruction path to guess headings vs. body
    text and approximate paragraph/heading structure rather than dumping
    one flat stream of text."""
    fitz = _fitz()
    doc = fitz.open(str(path))
    pages = []
    try:
        for page in doc:
            page_dict = page.get_text("dict")
            blocks = []
            for block in page_dict.get("blocks", []):
                if block.get("type") != 0:
                    continue  # skip image blocks here
                lines_out = []
                max_size = 0.0
                for line in block.get("lines", []):
                    spans = line.get("spans", [])
                    text = "".join(s.get("text", "") for s in spans)
                    if not text.strip():
                        continue
                    for s in spans:
                        max_size = max(max_size, s.get("size", 0.0))
                    lines_out.append(text)
                if lines_out:
                    blocks.append({"text": " ".join(lines_out), "max_font_size": max_size})
            pages.append({"blocks": blocks})
    finally:
        doc.close()
    return pages


def images_to_pdf(image_paths: list[Path], output_path: Path) -> Path:
    fitz = _fitz()
    doc = fitz.open()
    try:
        for img_path in image_paths:
            img_doc = fitz.open(str(img_path))
            rect = img_doc[0].rect
            pdf_bytes = img_doc.convert_to_pdf()
            img_doc.close()
            img_pdf = fitz.open("pdf", pdf_bytes)
            doc.insert_pdf(img_pdf)
            img_pdf.close()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(output_path))
    finally:
        doc.close()
    return output_path


def html_to_pdf(html_path: Path, output_path: Path) -> Path:
    """Lightweight HTML->PDF fallback using PyMuPDF's Story/HTML support.
    Used when LibreOffice is unavailable. Less faithful with complex CSS
    than the LibreOffice pipeline, which is preferred when present."""
    fitz = _fitz()
    html = html_path.read_text(encoding="utf-8", errors="replace")
    story = fitz.Story(html=html)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = fitz.DocumentWriter(str(output_path))
    mediabox = fitz.paper_rect("a4")
    where = mediabox + (36, 36, -36, -36)
    more = True
    while more:
        device = writer.begin_page(mediabox)
        more, _ = story.place(where)
        story.draw(device)
        writer.end_page()
    writer.close()
    return output_path


def validate_pdf_output(path: Path, min_pages: int = 1) -> list[str]:
    """Post-conversion sanity checks. Returns a list of human-readable
    issue strings (empty list == looks fine)."""
    issues = []
    if not path.exists() or path.stat().st_size == 0:
        issues.append("Output PDF is missing or empty.")
        return issues
    try:
        info = inspect_pdf(path)
        if info.page_count < min_pages:
            issues.append(f"Output PDF has only {info.page_count} page(s); expected at least {min_pages}.")
        if not info.has_text and not info.has_images:
            issues.append("Output PDF appears to contain neither text nor images.")
    except Exception as exc:
        issues.append(f"Could not validate output PDF: {exc}")
    return issues
