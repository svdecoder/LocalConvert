"""Central dependency-detection registry.

The whole application treats "is this tool installed?" as a first-class,
cached, queryable fact rather than something discovered by catching an
exception deep inside a conversion. Converters declare which external
executables and Python packages they need; the GUI and pre-flight checks
call into this module to explain to the user, in advance, why a given
conversion is greyed out.
"""

from __future__ import annotations

import functools
import importlib
import shutil
import subprocess
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ToolStatus:
    name: str
    kind: str  # "executable" | "python_package"
    available: bool
    version: str = ""
    path: str = ""
    hint: str = ""


# Human-facing installation hints, kept in one place so messaging stays
# consistent across the GUI (settings page, disabled-conversion tooltips,
# and the startup dependency report).
_INSTALL_HINTS: dict[str, str] = {
    "libreoffice": (
        "Install LibreOffice from https://www.libreoffice.org/download/ "
        "(Linux: 'sudo apt install libreoffice', macOS: 'brew install --cask libreoffice')."
    ),
    "pandoc": (
        "Install Pandoc from https://pandoc.org/installing.html "
        "(Linux: 'sudo apt install pandoc', macOS: 'brew install pandoc')."
    ),
    "ffmpeg": (
        "Install FFmpeg from https://ffmpeg.org/download.html "
        "(Linux: 'sudo apt install ffmpeg', macOS: 'brew install ffmpeg')."
    ),
    "ffprobe": "Bundled with FFmpeg — install FFmpeg to get ffprobe as well.",
    "tesseract": (
        "Install Tesseract OCR from https://github.com/tesseract-ocr/tesseract "
        "(Linux: 'sudo apt install tesseract-ocr', macOS: 'brew install tesseract')."
    ),
    "ebook-convert": (
        "Install Calibre from https://calibre-ebook.com/download "
        "(provides the 'ebook-convert' command-line tool)."
    ),
    "magick": (
        "Install ImageMagick from https://imagemagick.org/script/download.php "
        "(optional — only used for a few advanced image operations)."
    ),
}

_PACKAGE_INSTALL_HINTS: dict[str, str] = {
    "fitz": "pip install PyMuPDF",
    "PIL": "pip install Pillow",
    "docx": "pip install python-docx",
    "pptx": "pip install python-pptx",
    "openpyxl": "pip install openpyxl",
    "ebooklib": "pip install EbookLib",
    "bs4": "pip install beautifulsoup4",
    "pytesseract": "pip install pytesseract",
}


@functools.lru_cache(maxsize=None)
def check_executable(name: str) -> ToolStatus:
    """Check whether an external executable is on PATH, caching the result
    for the lifetime of the process (call ``check_executable.cache_clear()``
    after a user installs something and asks to re-check)."""
    path = shutil.which(name)
    if not path:
        return ToolStatus(
            name=name,
            kind="executable",
            available=False,
            hint=_INSTALL_HINTS.get(name, f"Install '{name}' and ensure it is on your PATH."),
        )
    version = ""
    try:
        proc = subprocess.run(
            [path, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        first_line = (proc.stdout or proc.stderr or "").strip().splitlines()
        version = first_line[0] if first_line else ""
    except Exception:
        version = ""
    return ToolStatus(name=name, kind="executable", available=True, version=version, path=path)


@functools.lru_cache(maxsize=None)
def check_python_package(module_name: str) -> ToolStatus:
    try:
        mod = importlib.import_module(module_name)
        version = getattr(mod, "__version__", "")
        return ToolStatus(
            name=module_name, kind="python_package", available=True, version=version
        )
    except Exception:
        return ToolStatus(
            name=module_name,
            kind="python_package",
            available=False,
            hint=_PACKAGE_INSTALL_HINTS.get(module_name, f"pip install {module_name}"),
        )


def clear_cache() -> None:
    check_executable.cache_clear()
    check_python_package.cache_clear()


def missing_from(required_tools: list[str]) -> list[ToolStatus]:
    """Given a list of tool identifiers (mixed executables/python packages,
    matched by convention below), return the ones that are NOT available."""
    missing = []
    for tool in required_tools:
        status = _resolve(tool)
        if not status.available:
            missing.append(status)
    return missing


def _resolve(tool: str) -> ToolStatus:
    # Python packages are declared with a "py:" prefix; everything else is
    # treated as an external executable. This keeps CapabilityInfo lists
    # human-readable while remaining unambiguous.
    if tool.startswith("py:"):
        return check_python_package(tool[3:])
    return check_executable(tool)


def full_report(all_tools: list[str]) -> list[ToolStatus]:
    return [_resolve(t) for t in sorted(set(all_tools))]
