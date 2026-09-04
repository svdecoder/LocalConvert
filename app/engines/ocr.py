"""Local OCR engine using Tesseract (via pytesseract, or the CLI directly
as a fallback if pytesseract is not installed but the tesseract binary
is). Entirely offline — no cloud OCR APIs.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from app.utils.dependencies import check_executable, check_python_package
from app.utils.logging_setup import get_logger

logger = get_logger("engines.ocr")


def is_available() -> bool:
    return check_executable("tesseract").available


class OcrError(RuntimeError):
    pass


def ocr_image_to_text(image_path: Path, language: str = "eng") -> str:
    if not is_available():
        raise OcrError("Tesseract OCR is not installed. Install 'tesseract-ocr' to enable OCR.")

    if check_python_package("pytesseract").available:
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore

        with Image.open(image_path) as img:
            return pytesseract.image_to_string(img, lang=language)

    # Fallback: call the tesseract CLI directly.
    status = check_executable("tesseract")
    out_base = image_path.with_suffix("")
    cmd = [status.path, str(image_path), str(out_base), "-l", language]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise OcrError(f"Tesseract failed: {proc.stderr.strip()}")
    txt_path = out_base.with_suffix(".txt")
    if not txt_path.exists():
        raise OcrError("Tesseract reported success but produced no text output.")
    return txt_path.read_text(encoding="utf-8", errors="replace")


def ocr_pdf_pages(page_image_paths: list[Path], language: str = "eng") -> list[str]:
    return [ocr_image_to_text(p, language=language) for p in page_image_paths]
