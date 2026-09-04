"""Office document, PDF, HTML, Markdown, and plain-text conversion.

Pipeline selection strategy (see spec section 14 — no single generic
pipeline for every pair):

  * DOCX/DOC/ODT/RTF/PPTX/XLSX/CSV  <-> PDF     : LibreOffice headless
  * DOCX/ODT/RTF <-> HTML/Markdown/TXT           : Pandoc
  * Markdown/HTML -> PDF                         : LibreOffice if present,
                                                    else a PyMuPDF Story
                                                    fallback (fewer CSS
                                                    features supported)
  * PDF -> DOCX                                  : best-effort structural
                                                    reconstruction (heading
                                                    detection via font size)
                                                    using PyMuPDF + python-docx
  * PDF -> TXT/Markdown                          : PyMuPDF text extraction
  * Scanned PDF -> text/DOCX                     : optional local OCR pass
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Callable, Optional

from app.converters.base import BaseConverter, ConversionCancelled
from app.engines import ocr as ocr_engine
from app.engines import office as office_engine
from app.engines import pandoc_engine
from app.engines import pdf as pdf_engine
from app.models import (
    CapabilityInfo,
    ConversionJob,
    ConversionOption,
    ConversionResult,
    ConversionWarning,
    Fidelity,
    PreservationFlags,
)
from app.utils.fs import temp_workspace, unique_output_path
from app.utils.logging_setup import get_logger

logger = get_logger("converters.documents")

_OFFICE_FORMATS = {"docx", "doc", "odt", "rtf", "pptx", "xlsx", "csv"}
_PANDOC_TEXTUAL = {"md", "markdown", "html", "htm", "txt", "rtf", "docx", "odt"}


class DocumentConverter(BaseConverter):
    name = "documents"

    def capabilities(self) -> list[CapabilityInfo]:
        caps = []

        # Office suite <-> PDF via LibreOffice: the highest-fidelity local
        # path for these formats.
        caps.append(
            CapabilityInfo(
                input_formats={"docx", "doc", "odt", "rtf", "pptx", "xlsx"},
                output_formats={"pdf"},
                fidelity=Fidelity.HIGH_FIDELITY,
                preserves=PreservationFlags(
                    text=True, formatting=True, fonts=True, images=True, tables=True,
                    hyperlinks=True, headings=True, page_structure=True,
                    headers_footers=True, lists=True, metadata=True,
                ),
                required_tools=["libreoffice"],
                limitations=[
                    "Some advanced DOCX/PPTX layout features (SmartArt, complex "
                    "form fields) may render slightly differently.",
                ],
                backend_name="LibreOffice",
            )
        )

        # CSV/XLSX -> PDF
        caps.append(
            CapabilityInfo(
                input_formats={"csv", "xlsx"},
                output_formats={"pdf"},
                fidelity=Fidelity.HIGH_FIDELITY,
                preserves=PreservationFlags(text=True, tables=True, formatting=True, metadata=True),
                required_tools=["libreoffice"],
                limitations=["Very wide spreadsheets may be split across multiple PDF pages."],
                backend_name="LibreOffice",
            )
        )

        # Office document interchange (DOCX<->ODT<->RTF, etc.)
        caps.append(
            CapabilityInfo(
                input_formats={"docx", "doc", "odt", "rtf"},
                output_formats={"docx", "odt", "rtf"},
                fidelity=Fidelity.HIGH_FIDELITY,
                preserves=PreservationFlags(
                    text=True, formatting=True, fonts=True, images=True, tables=True,
                    hyperlinks=True, headings=True, lists=True, metadata=True,
                ),
                required_tools=["libreoffice"],
                limitations=["Rare proprietary formatting extensions may not round-trip perfectly."],
                backend_name="LibreOffice",
            )
        )

        # Markdown/HTML/TXT <-> DOCX/ODT via Pandoc (better semantic
        # fidelity for structured text than round-tripping through LO).
        caps.append(
            CapabilityInfo(
                input_formats={"md", "markdown", "html", "htm", "txt"},
                output_formats={"docx", "odt", "html", "md", "txt", "rtf"},
                fidelity=Fidelity.HIGH_FIDELITY,
                preserves=PreservationFlags(
                    text=True, formatting=True, headings=True, hyperlinks=True, lists=True,
                ),
                required_tools=["pandoc"],
                limitations=["Plain text output cannot retain formatting, images, or links."],
                backend_name="Pandoc",
            )
        )
        caps.append(
            CapabilityInfo(
                input_formats={"docx", "odt"},
                output_formats={"md", "markdown", "html", "htm", "txt"},
                fidelity=Fidelity.HIGH_FIDELITY if True else Fidelity.LOSSY,
                preserves=PreservationFlags(
                    text=True, formatting=True, headings=True, hyperlinks=True, lists=True, images=True,
                ),
                required_tools=["pandoc"],
                limitations=[
                    "Complex layout (columns, precise positioning) has no Markdown/HTML "
                    "equivalent and is flattened to reading order.",
                ],
                backend_name="Pandoc",
            )
        )

        # Markdown/HTML -> PDF
        caps.append(
            CapabilityInfo(
                input_formats={"md", "markdown", "html", "htm"},
                output_formats={"pdf"},
                fidelity=Fidelity.HIGH_FIDELITY,
                preserves=PreservationFlags(text=True, formatting=True, images=True, headings=True, hyperlinks=True),
                required_tools=["pandoc", "libreoffice"],
                optional_tools=["py:fitz"],
                limitations=["Falls back to a simplified renderer if LibreOffice is unavailable; advanced CSS may not be honored."],
                backend_name="Pandoc + LibreOffice",
            )
        )

        # PDF -> DOCX/Markdown/TXT (best-effort reconstruction)
        caps.append(
            CapabilityInfo(
                input_formats={"pdf"},
                output_formats={"docx", "md", "markdown", "txt"},
                fidelity=Fidelity.BEST_EFFORT,
                preserves=PreservationFlags(
                    text=True, headings=True, page_structure=False, tables=False,
                    formatting=False, images=True,
                ),
                required_tools=["py:fitz"],
                optional_tools=["py:docx", "tesseract"],
                limitations=[
                    "Reconstructed heading/paragraph structure is inferred from font "
                    "sizes and may not exactly match the original document structure.",
                    "Complex tables and multi-column layouts are not reliably reconstructed.",
                    "Original fonts are not preserved (PDF fonts are not portable to DOCX).",
                ],
                backend_name="PyMuPDF (heuristic reconstruction)",
            )
        )

        # Scanned PDF -> text/DOCX via OCR
        caps.append(
            CapabilityInfo(
                input_formats={"pdf"},
                output_formats={"txt", "docx"},
                fidelity=Fidelity.BEST_EFFORT,
                preserves=PreservationFlags(text=True, images=True),
                required_tools=["py:fitz", "tesseract"],
                limitations=[
                    "OCR accuracy depends on scan quality; recognition errors are possible.",
                    "Original formatting is not recoverable from a scanned image.",
                ],
                options=[
                    ConversionOption(
                        key="use_ocr",
                        label="Use OCR for scanned pages",
                        kind="bool",
                        default=True,
                        help_text="Recognize text in scanned/image-only PDF pages using local Tesseract OCR.",
                    ),
                    ConversionOption(
                        key="ocr_language",
                        label="OCR language",
                        kind="text",
                        default="eng",
                        help_text="Tesseract language code, e.g. 'eng', 'fra', 'deu'.",
                    ),
                ],
                backend_name="Tesseract OCR",
            )
        )

        return caps

    # ------------------------------------------------------------------

    def convert(
        self,
        job: ConversionJob,
        progress_cb: Optional[Callable[[float, str], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> ConversionResult:
        in_fmt = job.input_format
        out_fmt = job.output_format.lower().lstrip(".")
        warnings: list[ConversionWarning] = []

        def report(frac: float, msg: str) -> None:
            if progress_cb:
                progress_cb(frac, msg)

        try:
            with temp_workspace() as workspace:
                if in_fmt == "pdf" and out_fmt in {"docx", "md", "markdown", "txt"}:
                    return self._convert_pdf_to_editable(job, workspace, report, cancel_check, warnings)

                if in_fmt in _OFFICE_FORMATS and out_fmt == "pdf":
                    return self._convert_via_libreoffice(job, workspace, report, warnings, "pdf")

                if in_fmt in {"docx", "doc", "odt", "rtf"} and out_fmt in {"docx", "odt", "rtf"}:
                    return self._convert_via_libreoffice(job, workspace, report, warnings, out_fmt)

                if in_fmt in {"md", "markdown", "html", "htm", "txt"} and out_fmt == "pdf":
                    return self._convert_markup_to_pdf(job, workspace, report, warnings)

                if out_fmt in {"docx", "odt", "html", "md", "markdown", "txt", "rtf"}:
                    return self._convert_via_pandoc(job, workspace, report, warnings)

                return ConversionResult(
                    job_id=job.job_id,
                    success=False,
                    output_path=None,
                    error_message=f"No document conversion pipeline available for {in_fmt} -> {out_fmt}.",
                )
        except ConversionCancelled:
            return ConversionResult(
                job_id=job.job_id, success=False, output_path=None, error_message="Cancelled by user."
            )
        except Exception as exc:  # noqa: BLE001 - convert to a result, never crash the GUI
            logger.exception("Document conversion failed for %s", job.input_path)
            return ConversionResult(job_id=job.job_id, success=False, output_path=None, error_message=str(exc))

    # -- individual pipelines -------------------------------------------------

    def _convert_via_libreoffice(self, job, workspace, report, warnings, out_fmt) -> ConversionResult:
        report(0.05, "Starting LibreOffice...")
        if not office_engine.is_available():
            return ConversionResult(
                job_id=job.job_id, success=False, output_path=None,
                error_message="LibreOffice is required for this conversion but was not found.",
            )
        produced = office_engine.convert_with_libreoffice(
            job.input_path, out_fmt, workspace / "out", workspace
        )
        report(0.85, "Finalizing...")
        final_path = unique_output_path(job.output_dir, job.input_path.stem, f".{out_fmt}")
        final_path.write_bytes(produced.read_bytes())

        validation_issues: list[str] = []
        if out_fmt == "pdf":
            validation_issues = pdf_engine.validate_pdf_output(final_path)

        report(1.0, "Done")
        return ConversionResult(
            job_id=job.job_id,
            success=not validation_issues,
            output_path=final_path,
            preserved=PreservationFlags(
                text=True, formatting=True, fonts=True, images=True, tables=True,
                hyperlinks=True, headings=True, metadata=True, page_structure=(out_fmt == "pdf"),
            ),
            warnings=warnings,
            validation_issues=validation_issues,
            backend_used="LibreOffice",
            error_message="; ".join(validation_issues) if validation_issues else "",
        )

    def _convert_markup_to_pdf(self, job, workspace, report, warnings) -> ConversionResult:
        report(0.05, "Converting to PDF...")
        final_path = unique_output_path(job.output_dir, job.input_path.stem, ".pdf")

        if office_engine.is_available():
            # Route through LibreOffice for best CSS/formatting fidelity.
            produced = office_engine.convert_with_libreoffice(job.input_path, "pdf", workspace / "out", workspace)
            final_path.write_bytes(produced.read_bytes())
            backend = "LibreOffice"
        elif pdf_engine.is_available():
            warnings.append(ConversionWarning(
                "LibreOffice not found; used a simplified built-in renderer. "
                "Complex CSS/layout may not be fully honored.",
                severity="warning",
            ))
            src = job.input_path
            if job.input_format in ("md", "markdown"):
                if not pandoc_engine.is_available():
                    return ConversionResult(
                        job_id=job.job_id, success=False, output_path=None,
                        error_message="Converting Markdown to PDF without LibreOffice requires Pandoc "
                                      "to first render HTML, but Pandoc was not found.",
                    )
                html_path = workspace / "converted.html"
                pandoc_engine.convert_with_pandoc(src, html_path, from_format="markdown", to_format="html")
                src = html_path
            pdf_engine.html_to_pdf(src, final_path)
            backend = "PyMuPDF (fallback renderer)"
        else:
            return ConversionResult(
                job_id=job.job_id, success=False, output_path=None,
                error_message="This conversion requires LibreOffice or PyMuPDF, neither of which was found.",
            )

        report(0.9, "Validating output...")
        issues = pdf_engine.validate_pdf_output(final_path)
        report(1.0, "Done")
        return ConversionResult(
            job_id=job.job_id,
            success=not issues,
            output_path=final_path,
            preserved=PreservationFlags(text=True, formatting=True, images=True, headings=True),
            warnings=warnings,
            validation_issues=issues,
            backend_used=backend,
            error_message="; ".join(issues) if issues else "",
        )

    def _convert_via_pandoc(self, job, workspace, report, warnings) -> ConversionResult:
        report(0.1, "Converting with Pandoc...")
        if not pandoc_engine.is_available():
            return ConversionResult(
                job_id=job.job_id, success=False, output_path=None,
                error_message="Pandoc is required for this conversion but was not found.",
            )
        out_fmt = job.output_format.lower().lstrip(".")
        ext = "md" if out_fmt == "markdown" else out_fmt
        final_path = unique_output_path(job.output_dir, job.input_path.stem, f".{ext}")
        tmp_out = workspace / final_path.name
        pandoc_engine.convert_with_pandoc(job.input_path, tmp_out, to_format=out_fmt)
        tmp_out.replace(final_path) if tmp_out.exists() else None
        if not final_path.exists() and tmp_out.exists():
            final_path.write_bytes(tmp_out.read_bytes())

        preserves_formatting = out_fmt not in {"txt"}
        if out_fmt == "txt":
            warnings.append(ConversionWarning("Plain text output cannot retain formatting, images, or links.", "warning"))

        report(1.0, "Done")
        return ConversionResult(
            job_id=job.job_id,
            success=True,
            output_path=final_path,
            preserved=PreservationFlags(
                text=True,
                formatting=preserves_formatting,
                headings=preserves_formatting,
                hyperlinks=preserves_formatting,
                lists=preserves_formatting,
            ),
            warnings=warnings,
            backend_used="Pandoc",
        )

    def _convert_pdf_to_editable(self, job, workspace, report, cancel_check, warnings) -> ConversionResult:
        report(0.05, "Inspecting PDF...")
        if not pdf_engine.is_available():
            return ConversionResult(
                job_id=job.job_id, success=False, output_path=None,
                error_message="PyMuPDF is required to read PDFs but was not found.",
            )

        info = pdf_engine.inspect_pdf(job.input_path)
        out_fmt = job.output_format.lower().lstrip(".")
        use_ocr = job.options.get("use_ocr", True)
        ocr_language = job.options.get("ocr_language", "eng")

        pages_text: list[str]
        used_ocr = False

        if info.is_probably_scanned and use_ocr:
            if not ocr_engine.is_available():
                warnings.append(ConversionWarning(
                    "This PDF looks like a scanned document, but Tesseract OCR is not "
                    "installed, so no text could be recognized.", severity="error",
                ))
                pages_text = ["" for _ in range(info.page_count)]
            else:
                report(0.15, "Rendering pages for OCR...")
                images = pdf_engine.render_pages_to_images(job.input_path, workspace / "pages", dpi=250)
                pages_text = []
                for i, img in enumerate(images):
                    if cancel_check and cancel_check():
                        raise ConversionCancelled()
                    pages_text.append(ocr_engine.ocr_image_to_text(img, language=ocr_language))
                    report(0.15 + 0.6 * (i + 1) / max(len(images), 1), f"OCR page {i + 1}/{len(images)}...")
                used_ocr = True
                warnings.append(ConversionWarning(
                    "Text was recognized via OCR from a scanned document; recognition "
                    "errors are possible and original formatting could not be recovered.",
                    severity="warning",
                ))
        else:
            report(0.3, "Extracting structured text...")
            structured = pdf_engine.extract_structured_text(job.input_path)
            pages_text = ["\n\n".join(b["text"] for b in p["blocks"]) for p in structured]

        report(0.8, "Writing output...")
        ext = "md" if out_fmt == "markdown" else out_fmt
        final_path = unique_output_path(job.output_dir, job.input_path.stem, f".{ext}")

        if out_fmt in ("txt",):
            final_path.write_text("\n\n".join(pages_text), encoding="utf-8")
        elif out_fmt in ("md", "markdown"):
            final_path.write_text(self._structured_to_markdown(job.input_path, used_ocr, pages_text), encoding="utf-8")
        elif out_fmt == "docx":
            from app.utils.dependencies import check_python_package
            if not check_python_package("docx").available:
                return ConversionResult(
                    job_id=job.job_id, success=False, output_path=None,
                    error_message="python-docx is required for PDF -> DOCX but was not found.",
                )
            self._write_docx_from_structured(job.input_path, final_path, used_ocr, pages_text)
        else:
            return ConversionResult(
                job_id=job.job_id, success=False, output_path=None,
                error_message=f"Unsupported PDF reconstruction target: {out_fmt}",
            )

        warnings.append(ConversionWarning(
            "Reconstructed from PDF: exact original formatting, fonts, and complex "
            "table layouts could not be recovered.", severity="warning",
        ))
        report(1.0, "Done")
        return ConversionResult(
            job_id=job.job_id,
            success=True,
            output_path=final_path,
            preserved=PreservationFlags(text=True, headings=not used_ocr, images=False, formatting=False),
            warnings=warnings,
            backend_used="Tesseract OCR" if used_ocr else "PyMuPDF (heuristic reconstruction)",
        )

    @staticmethod
    def _structured_to_markdown(pdf_path: Path, used_ocr: bool, pages_text: list[str]) -> str:
        if used_ocr:
            return "\n\n".join(pages_text)
        structured = pdf_engine.extract_structured_text(pdf_path)
        # Guess a heading threshold from the distribution of font sizes.
        sizes = [b["max_font_size"] for p in structured for b in p["blocks"] if b["max_font_size"]]
        body_size = sorted(sizes)[len(sizes) // 2] if sizes else 12.0
        heading_threshold = body_size * 1.2

        out_lines = []
        for page in structured:
            for block in page["blocks"]:
                text = block["text"].strip()
                if not text:
                    continue
                if block["max_font_size"] >= heading_threshold * 1.5:
                    out_lines.append(f"# {text}")
                elif block["max_font_size"] >= heading_threshold:
                    out_lines.append(f"## {text}")
                else:
                    out_lines.append(text)
                out_lines.append("")
        return "\n".join(out_lines)

    @staticmethod
    def _write_docx_from_structured(pdf_path: Path, out_path: Path, used_ocr: bool, pages_text: list[str]) -> None:
        import docx  # type: ignore

        document = docx.Document()
        if used_ocr:
            for text in pages_text:
                for para in text.split("\n"):
                    if para.strip():
                        document.add_paragraph(para)
                document.add_page_break()
        else:
            structured = pdf_engine.extract_structured_text(pdf_path)
            sizes = [b["max_font_size"] for p in structured for b in p["blocks"] if b["max_font_size"]]
            body_size = sorted(sizes)[len(sizes) // 2] if sizes else 12.0
            heading_threshold = body_size * 1.2
            for page in structured:
                for block in page["blocks"]:
                    text = block["text"].strip()
                    if not text:
                        continue
                    if block["max_font_size"] >= heading_threshold * 1.5:
                        document.add_heading(text, level=1)
                    elif block["max_font_size"] >= heading_threshold:
                        document.add_heading(text, level=2)
                    else:
                        document.add_paragraph(text)
                document.add_page_break()
        document.save(str(out_path))


class SpreadsheetConverter(BaseConverter):
    """Handles CSV <-> XLSX directly (no LibreOffice needed for this
    lightweight, extremely common pair) plus delegates other spreadsheet
    targets to LibreOffice via DocumentConverter's capability (kept
    separate here for a fast, dependency-light CSV<->XLSX path).
    """

    name = "spreadsheets"

    def capabilities(self) -> list[CapabilityInfo]:
        return [
            CapabilityInfo(
                input_formats={"csv"},
                output_formats={"xlsx"},
                fidelity=Fidelity.HIGH_FIDELITY,
                preserves=PreservationFlags(text=True, tables=True),
                required_tools=["py:openpyxl"],
                limitations=["CSV has no formatting/formulas to preserve, so the XLSX is plain data only."],
                backend_name="openpyxl",
            ),
            CapabilityInfo(
                input_formats={"xlsx"},
                output_formats={"csv"},
                fidelity=Fidelity.LOSSY,
                preserves=PreservationFlags(text=True, tables=True, formatting=False),
                required_tools=["py:openpyxl"],
                limitations=["Only the first sheet is exported; formulas are exported as their last calculated value; formatting/charts are lost."],
                backend_name="openpyxl",
            ),
        ]

    def convert(self, job, progress_cb=None, cancel_check=None) -> ConversionResult:
        from app.utils.dependencies import check_python_package

        if not check_python_package("openpyxl").available:
            return ConversionResult(
                job_id=job.job_id, success=False, output_path=None,
                error_message="openpyxl is required for CSV/XLSX conversion but was not found.",
            )
        import openpyxl  # type: ignore

        in_fmt, out_fmt = job.input_format, job.output_format.lower().lstrip(".")
        final_path = unique_output_path(job.output_dir, job.input_path.stem, f".{out_fmt}")

        try:
            if in_fmt == "csv" and out_fmt == "xlsx":
                wb = openpyxl.Workbook()
                ws = wb.active
                with open(job.input_path, newline="", encoding="utf-8-sig") as f:
                    for row in csv.reader(f):
                        ws.append(row)
                wb.save(final_path)
            elif in_fmt == "xlsx" and out_fmt == "csv":
                wb = openpyxl.load_workbook(job.input_path, data_only=True)
                ws = wb.active
                with open(final_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    for row in ws.iter_rows(values_only=True):
                        writer.writerow(["" if v is None else v for v in row])
            else:
                return ConversionResult(
                    job_id=job.job_id, success=False, output_path=None,
                    error_message=f"Unsupported spreadsheet conversion: {in_fmt} -> {out_fmt}",
                )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Spreadsheet conversion failed")
            return ConversionResult(job_id=job.job_id, success=False, output_path=None, error_message=str(exc))

        if progress_cb:
            progress_cb(1.0, "Done")
        return ConversionResult(
            job_id=job.job_id,
            success=True,
            output_path=final_path,
            preserved=PreservationFlags(text=True, tables=True, formatting=(out_fmt == "xlsx")),
            backend_used="openpyxl",
        )
