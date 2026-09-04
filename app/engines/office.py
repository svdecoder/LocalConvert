"""LibreOffice headless engine.

LibreOffice's ``soffice --headless --convert-to`` is the workhorse for
Office-document conversions (DOCX/DOC/ODT/RTF/PPTX/XLSX/CSV <-> PDF and
between each other). It runs entirely locally.

Two important real-world details this module handles:
  1. LibreOffice can be slow to start and occasionally leaves a stale lock
     file / user profile lock when run concurrently, so we give each
     invocation its own ``-env:UserInstallation`` profile directory.
  2. The executable is named differently across platforms/installs
     ("soffice", "soffice.exe", "libreoffice").
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

from app.utils.dependencies import check_executable
from app.utils.logging_setup import get_logger

logger = get_logger("engines.office")

_CANDIDATE_NAMES = ["soffice", "libreoffice", "soffice.exe"]


def find_soffice() -> Optional[str]:
    for name in _CANDIDATE_NAMES:
        status = check_executable(name)
        if status.available:
            return status.path
    return None


def is_available() -> bool:
    return find_soffice() is not None


class OfficeConversionError(RuntimeError):
    pass


def convert_with_libreoffice(
    input_path: Path,
    output_format: str,
    output_dir: Path,
    workspace: Path,
    timeout: int = 300,
) -> Path:
    """Convert ``input_path`` to ``output_format`` using LibreOffice
    headless mode. Returns the path to the produced file.

    ``workspace`` is used as an isolated LibreOffice user profile
    directory so concurrent conversions do not collide.
    """
    soffice = find_soffice()
    if not soffice:
        raise OfficeConversionError(
            "LibreOffice ('soffice') was not found on PATH. Install LibreOffice to "
            "enable Office-document conversions."
        )

    profile_dir = workspace / "lo_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)
    profile_uri = profile_dir.resolve().as_uri()

    output_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        soffice,
        "--headless",
        "--norestore",
        "--nolockcheck",
        f"-env:UserInstallation={profile_uri}",
        "--convert-to",
        output_format,
        "--outdir",
        str(output_dir),
        str(input_path),
    ]
    logger.info("Running LibreOffice: %s", " ".join(cmd))
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired as exc:
        raise OfficeConversionError(
            f"LibreOffice conversion timed out after {timeout}s."
        ) from exc

    if proc.returncode != 0:
        raise OfficeConversionError(
            f"LibreOffice exited with code {proc.returncode}: {proc.stderr.strip() or proc.stdout.strip()}"
        )

    expected = output_dir / f"{input_path.stem}.{output_format.split(':')[0]}"
    if expected.exists():
        return expected

    # Some format tokens (e.g. "pdf:writer_pdf_Export") produce the base
    # extension only; fall back to scanning outdir for a freshly created
    # file matching the stem.
    base_ext = output_format.split(":")[0]
    candidates = sorted(
        output_dir.glob(f"{input_path.stem}*.{base_ext}"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if candidates:
        return candidates[0]

    raise OfficeConversionError(
        f"LibreOffice reported success but no output file was found for '{input_path.name}'."
    )
