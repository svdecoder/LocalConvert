"""Core data models shared across the application.

These are plain dataclasses (no Qt / GUI imports) so they can be used by
the conversion engine, the worker threads, and the GUI layer alike, and so
they can be unit-tested without a display server.
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


class Fidelity(str, enum.Enum):
    """How faithfully a conversion pipeline can be expected to preserve
    the source document."""

    LOSSLESS = "lossless"
    HIGH_FIDELITY = "high_fidelity"   # nearly everything preserved, minor risk
    LOSSY = "lossy"                   # known, structural information loss
    BEST_EFFORT = "best_effort"       # heuristic reconstruction (e.g. PDF->DOCX)


class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


@dataclass
class PreservationFlags:
    """Which structural features a given conversion pipeline preserves.

    ``None`` means "not applicable to this format pair" (e.g. asking about
    subtitles for a PNG->JPG conversion) so it can be omitted from the
    summary UI rather than shown as a false negative.
    """

    text: Optional[bool] = None
    formatting: Optional[bool] = None
    fonts: Optional[bool] = None
    images: Optional[bool] = None
    tables: Optional[bool] = None
    hyperlinks: Optional[bool] = None
    headings: Optional[bool] = None
    chapters: Optional[bool] = None
    table_of_contents: Optional[bool] = None
    bookmarks: Optional[bool] = None
    metadata: Optional[bool] = None
    page_structure: Optional[bool] = None
    footnotes: Optional[bool] = None
    headers_footers: Optional[bool] = None
    lists: Optional[bool] = None
    subtitles: Optional[bool] = None
    audio_tracks: Optional[bool] = None
    chapters_video: Optional[bool] = None
    transparency: Optional[bool] = None
    animation: Optional[bool] = None
    color_profile: Optional[bool] = None

    def as_dict(self) -> dict[str, Optional[bool]]:
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class ConversionOption:
    """Describes a single user-configurable option exposed by a converter."""

    key: str
    label: str
    kind: str  # "choice" | "int" | "float" | "bool" | "text"
    default: Any
    choices: Optional[list[Any]] = None
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    help_text: str = ""


@dataclass
class CapabilityInfo:
    """Static, declarative description of what a converter can do.

    Each Converter subclass exposes one or more of these (one per
    input/output format pair, or a shared one when behavior does not
    depend on the pair) so the GUI and the pre-flight checks can reason
    about a conversion before running it.
    """

    input_formats: set[str]
    output_formats: set[str]
    fidelity: Fidelity
    preserves: PreservationFlags = field(default_factory=PreservationFlags)
    required_tools: list[str] = field(default_factory=list)
    optional_tools: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    options: list[ConversionOption] = field(default_factory=list)
    backend_name: str = ""


@dataclass
class ConversionJob:
    """A single file conversion request, as tracked by the queue/workers."""

    input_path: Path
    output_format: str
    output_dir: Path
    options: dict[str, Any] = field(default_factory=dict)
    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: JobStatus = JobStatus.QUEUED
    output_path: Optional[Path] = None
    error_message: str = ""
    progress: float = 0.0  # 0..1

    @property
    def input_format(self) -> str:
        return self.input_path.suffix.lower().lstrip(".")


@dataclass
class ConversionWarning:
    message: str
    severity: str = "warning"  # "info" | "warning" | "error"


@dataclass
class ConversionResult:
    """Outcome of running a single ConversionJob."""

    job_id: str
    success: bool
    output_path: Optional[Path]
    preserved: PreservationFlags = field(default_factory=PreservationFlags)
    warnings: list[ConversionWarning] = field(default_factory=list)
    validation_issues: list[str] = field(default_factory=list)
    error_message: str = ""
    backend_used: str = ""

    def summary_lines(self) -> list[str]:
        """Human-readable summary lines, in the style of the spec's
        "Conversion complete" example block."""
        lines: list[str] = []
        labels = {
            "text": "Text",
            "formatting": "Formatting",
            "fonts": "Fonts",
            "images": "Images",
            "tables": "Tables",
            "hyperlinks": "Hyperlinks",
            "headings": "Headings",
            "chapters": "Chapters",
            "table_of_contents": "Table of contents",
            "bookmarks": "Bookmarks",
            "metadata": "Metadata",
            "page_structure": "Page structure",
            "footnotes": "Footnotes/endnotes",
            "headers_footers": "Headers and footers",
            "lists": "Lists",
            "subtitles": "Subtitles",
            "audio_tracks": "Audio tracks",
            "chapters_video": "Chapters",
            "transparency": "Transparency",
            "animation": "Animation",
            "color_profile": "Color profile",
        }
        for key, val in self.preserved.as_dict().items():
            mark = "\u2713" if val else "\u2717"
            lines.append(f"{mark} {labels.get(key, key)} {'preserved' if val else 'lost'}")
        for w in self.warnings:
            sym = {"info": "i", "warning": "\u26a0", "error": "\u2717"}.get(w.severity, "\u26a0")
            lines.append(f"{sym} {w.message}")
        return lines
