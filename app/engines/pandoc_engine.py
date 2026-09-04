"""Pandoc engine — used for lightweight text/markup conversions
(Markdown, HTML, RTF, plain text, and as a DOCX<->Markdown/HTML bridge)
where LibreOffice would be overkill or less faithful.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

from app.utils.dependencies import check_executable
from app.utils.logging_setup import get_logger

logger = get_logger("engines.pandoc")


def is_available() -> bool:
    return check_executable("pandoc").available


class PandocConversionError(RuntimeError):
    pass


# Pandoc format identifiers differ slightly from file extensions.
_FORMAT_MAP = {
    "md": "markdown",
    "markdown": "markdown",
    "htm": "html",
    "html": "html",
    "txt": "plain",
    "rtf": "rtf",
    "docx": "docx",
    "odt": "odt",
    "epub": "epub",
}


def pandoc_format(fmt: str) -> str:
    return _FORMAT_MAP.get(fmt.lower(), fmt.lower())


def convert_with_pandoc(
    input_path: Path,
    output_path: Path,
    from_format: Optional[str] = None,
    to_format: Optional[str] = None,
    extra_args: Optional[list[str]] = None,
    timeout: int = 180,
) -> Path:
    pandoc_status = check_executable("pandoc")
    if not pandoc_status.available:
        raise PandocConversionError(
            "Pandoc was not found on PATH. Install Pandoc to enable this conversion."
        )

    cmd = ["pandoc", str(input_path)]
    if from_format:
        cmd += ["-f", pandoc_format(from_format)]
    if to_format:
        cmd += ["-t", pandoc_format(to_format)]
    cmd += ["-o", str(output_path)]
    if extra_args:
        cmd += extra_args

    output_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Running Pandoc: %s", " ".join(cmd))
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise PandocConversionError(f"Pandoc conversion timed out after {timeout}s.") from exc

    if proc.returncode != 0:
        raise PandocConversionError(f"Pandoc failed: {proc.stderr.strip()}")
    if not output_path.exists():
        raise PandocConversionError("Pandoc reported success but produced no output file.")
    return output_path
