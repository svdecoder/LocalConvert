"""Calibre's ``ebook-convert`` CLI — the standard local, offline tool for
EPUB/MOBI/AZW3/FB2 <-> PDF/DOCX/TXT/HTML ebook conversions. Calibre ships
this as a stand-alone command-line tool even without the full GUI app
running.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

from app.utils.dependencies import check_executable
from app.utils.logging_setup import get_logger

logger = get_logger("engines.ebook")


def is_available() -> bool:
    return check_executable("ebook-convert").available


class EbookConversionError(RuntimeError):
    pass


def convert_with_calibre(
    input_path: Path,
    output_path: Path,
    metadata_options: Optional[dict[str, str]] = None,
    extra_args: Optional[list[str]] = None,
    timeout: int = 300,
) -> Path:
    status = check_executable("ebook-convert")
    if not status.available:
        raise EbookConversionError(
            "Calibre's 'ebook-convert' tool was not found on PATH. Install Calibre "
            "to enable ebook conversions."
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [status.path, str(input_path), str(output_path)]

    if metadata_options:
        for key, value in metadata_options.items():
            cmd += [f"--{key}", value]
    if extra_args:
        cmd += extra_args

    logger.info("Running ebook-convert: %s", " ".join(cmd))
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise EbookConversionError(f"ebook-convert timed out after {timeout}s.") from exc

    if proc.returncode != 0:
        raise EbookConversionError(f"ebook-convert failed: {proc.stderr.strip() or proc.stdout.strip()}")
    if not output_path.exists():
        raise EbookConversionError("ebook-convert reported success but produced no output file.")
    return output_path
