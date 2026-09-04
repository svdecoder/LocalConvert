"""Small filesystem helpers used across converters and workers.

Centralizing these keeps "don't overwrite the original file", "handle
Unicode/space-laden filenames", and "clean up temp files" behavior
consistent instead of re-implemented ad hoc in each converter.
"""

from __future__ import annotations

import shutil
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


def unique_output_path(output_dir: Path, stem: str, suffix: str) -> Path:
    """Build an output path that never overwrites an existing file.

    Appends " (1)", " (2)", ... before the suffix if needed. ``suffix``
    should include the leading dot (e.g. ".pdf").
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    candidate = output_dir / f"{stem}{suffix}"
    if not candidate.exists():
        return candidate
    n = 1
    while True:
        candidate = output_dir / f"{stem} ({n}){suffix}"
        if not candidate.exists():
            return candidate
        n += 1


def safe_stem(path: Path) -> str:
    """Return a filename stem safe to reuse in output paths.

    Preserves Unicode; only strips characters that are illegal on at least
    one major OS (Windows is the strictest: <>:"/\\|?*).
    """
    stem = path.stem
    illegal = '<>:"/\\|?*'
    cleaned = "".join(c for c in stem if c not in illegal)
    cleaned = cleaned.strip().rstrip(".")
    return cleaned or "output"


@contextmanager
def temp_workspace(base_dir: Path | None = None) -> Iterator[Path]:
    """A per-conversion scratch directory that is always cleaned up, even
    if the conversion raises."""
    root = Path(tempfile.mkdtemp(prefix=f"localconvert_{uuid.uuid4().hex[:8]}_", dir=base_dir))
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} {unit}"
        size /= 1024
    return f"{size:.1f} TB"
