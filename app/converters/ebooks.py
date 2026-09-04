"""Ebook format conversion: EPUB, MOBI, AZW3, PDF, DOCX, TXT, HTML.

Primary backend is Calibre's ``ebook-convert``, which is the mature local
tool of choice for anything touching MOBI/AZW3 (Pillow/Pandoc do not
speak Kindle formats). EPUB<->PDF also goes through Calibre for
consistent chapter/TOC handling.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from app.converters.base import BaseConverter
from app.engines import ebook as ebook_engine
from app.engines import pdf as pdf_engine
from app.models import (
    CapabilityInfo,
    ConversionJob,
    ConversionResult,
    ConversionWarning,
    Fidelity,
    PreservationFlags,
)
from app.utils.fs import unique_output_path
from app.utils.logging_setup import get_logger

logger = get_logger("converters.ebooks")

_EBOOK_FORMATS = {"epub", "mobi", "azw3", "fb2"}
_TARGET_FORMATS = {"epub", "mobi", "azw3", "pdf", "docx", "txt", "html"}


class EbookConverter(BaseConverter):
    name = "ebooks"

    def capabilities(self) -> list[CapabilityInfo]:
        return [
            CapabilityInfo(
                input_formats=_EBOOK_FORMATS,
                output_formats=_EBOOK_FORMATS - {"fb2"} | {"pdf", "docx", "txt", "html"},
                fidelity=Fidelity.HIGH_FIDELITY,
                preserves=PreservationFlags(
                    text=True, formatting=True, images=True, chapters=True,
                    table_of_contents=True, metadata=True, hyperlinks=True,
                ),
                required_tools=["ebook-convert"],
                limitations=[
                    "Interactive/scripted EPUB content (JavaScript, embedded audio/video) "
                    "has no equivalent in static formats like PDF or MOBI and is dropped.",
                    "Reflowable EPUB text becomes fixed-layout when converted to PDF.",
                ],
                backend_name="Calibre (ebook-convert)",
            ),
            CapabilityInfo(
                input_formats={"pdf"},
                output_formats={"epub", "mobi", "azw3"},
                fidelity=Fidelity.BEST_EFFORT,
                preserves=PreservationFlags(
                    text=True, images=True, chapters=False, table_of_contents=False, formatting=False,
                ),
                required_tools=["ebook-convert"],
                limitations=[
                    "PDF has a fixed page layout with no chapter markup; Calibre must "
                    "heuristically reflow text, which can misplace headings, footnotes, "
                    "or multi-column content.",
                ],
                backend_name="Calibre (ebook-convert)",
            ),
        ]

    def convert(
        self,
        job: ConversionJob,
        progress_cb: Optional[Callable[[float, str], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> ConversionResult:
        if progress_cb:
            progress_cb(0.05, "Starting Calibre ebook-convert...")

        if not ebook_engine.is_available():
            return ConversionResult(
                job_id=job.job_id, success=False, output_path=None,
                error_message="Calibre's 'ebook-convert' tool is required for ebook conversion but was not found.",
            )

        out_fmt = job.output_format.lower().lstrip(".")
        final_path = unique_output_path(job.output_dir, job.input_path.stem, f".{out_fmt}")

        try:
            ebook_engine.convert_with_calibre(job.input_path, final_path)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Ebook conversion failed")
            return ConversionResult(job_id=job.job_id, success=False, output_path=None, error_message=str(exc))

        warnings = []
        validation_issues = []
        preserved = PreservationFlags(
            text=True, images=True, metadata=True,
            chapters=job.input_format != "pdf",
            table_of_contents=job.input_format != "pdf",
            formatting=job.input_format != "pdf",
        )

        if job.input_format == "pdf":
            warnings.append(ConversionWarning(
                "Source was a fixed-layout PDF; chapter structure and formatting "
                "were heuristically reconstructed and may not exactly match the original.",
                severity="warning",
            ))

        if out_fmt == "pdf":
            validation_issues = pdf_engine.validate_pdf_output(final_path)

        if progress_cb:
            progress_cb(1.0, "Done")

        return ConversionResult(
            job_id=job.job_id,
            success=not validation_issues,
            output_path=final_path,
            preserved=preserved,
            warnings=warnings,
            validation_issues=validation_issues,
            backend_used="Calibre (ebook-convert)",
            error_message="; ".join(validation_issues) if validation_issues else "",
        )
