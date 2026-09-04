# LocalConvert

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20macOS%20%7C%20Windows-lightgrey)]()
[![Tests](https://img.shields.io/badge/tests-41%20passed-brightgreen)]()

A fully local, offline, all-in-one file format converter with a modern
desktop GUI. No cloud uploads, no external APIs, no online conversion
services — every conversion runs using tools installed on your own
computer.

<p align="center">
  <i>Documents · Spreadsheets · Ebooks · Images · Video · Audio · PDF (with OCR)</i>
</p>

---

## Quick Start

```bash
# Clone and run the single setup script — creates a Python venv and installs
# all required system tools (LibreOffice, Pandoc, Calibre, FFmpeg, etc.)
git clone https://github.com/svdecoder/localconvert.git
cd localconvert
./setup.sh
```

<details>
<summary>Windows</summary>

```powershell
git clone https://github.com/svdecoder/localconvert.git
cd localconvert
powershell -ExecutionPolicy Bypass -File setup.ps1
```
</details>

<details>
<summary>Manual install</summary>

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
Then install the system tools you need (LibreOffice, Pandoc, Calibre,
FFmpeg, Tesseract) using your package manager.
</details>

### Run

```bash
source venv/bin/activate      # Windows: .\venv\Scripts\Activate.ps1
python -m app.main
```

---

## Architecture & Technology Choices

| Layer | Choice | Why |
|---|---|---|
| GUI | **PySide6 (Qt)** | Mature, native-feeling cross-platform desktop toolkit with first-class drag-and-drop, theming, and threading support. |
| Background work | **QThreadPool / QRunnable** | Keeps the GUI thread free so the app never freezes; Qt marshals progress signals back to the main thread safely. |
| Office documents | **LibreOffice headless** (`soffice --convert-to`) | The most complete, actively-maintained local engine for DOCX/DOC/ODT/RTF/PPTX/XLSX ⇄ PDF and between each other. |
| Lightweight text/markup | **Pandoc** | Best local tool for Markdown/HTML/plain-text ⇄ DOCX/ODT, preserving semantic structure (headings, lists, links) better than a full office suite round-trip. |
| Ebooks | **Calibre's `ebook-convert`** | The standard local, offline tool for EPUB/MOBI/AZW3, including chapter/TOC-aware conversion. |
| PDF reading/writing/reconstruction | **PyMuPDF (`fitz`)** | Fast, local, well-maintained PDF library used for inspection, page rendering, structured text extraction (for PDF→DOCX/Markdown reconstruction), and a lightweight HTML→PDF fallback. |
| OCR | **Tesseract** (via `pytesseract` or CLI) | Mature, fully local OCR engine for scanned PDFs/images. |
| Images | **Pillow**, with **ImageMagick** as an optional backend for SVG rasterization | Pillow covers all common raster formats and animation; ImageMagick fills the SVG gap. |
| Video/audio | **FFmpeg** (shelled out to directly) | The only realistic local, general-purpose codec/container engine; also used for probing (`ffprobe`) and progress reporting. |
| Plugin architecture | `BaseConverter` + `ConverterRegistry` | New format support = one new converter class + one registration line. The GUI and workers never import a specific converter directly. |

No conversion ever contacts the network. The app only uses local
subprocesses and local Python libraries.

### Project structure

```
app/
├── main.py                  # entry point
├── gui/
│   ├── main_window.py       # Add files → choose format → configure → convert
│   ├── widgets/              # DropZone, FileQueueTable
│   ├── dialogs/               # Settings, Dependency report, Conversion summary
│   └── styles/                # dark/light QSS
├── converters/                # plugin converters (documents, ebooks, images, video, audio)
├── engines/                    # thin wrappers around LibreOffice/Pandoc/Calibre/PyMuPDF/FFmpeg/Tesseract/Pillow
├── models/                     # plain dataclasses (ConversionJob, ConversionResult, CapabilityInfo, ...)
├── workers/                     # QThreadPool-based background conversion queue
├── utils/                        # dependency detection, filesystem helpers, logging
├── config/                        # persisted Settings
└── tests/                          # pytest unit tests (41 passing)
```

---

## Dependencies

### External executables

| Tool | Purpose | Required for | Fully local? |
|---|---|---|---|
| **LibreOffice** (`soffice`) | Office document conversion | DOCX/DOC/ODT/RTF/PPTX/XLSX ⇄ PDF, DOCX/ODT/RTF interchange | Yes |
| **Pandoc** | Markup/text conversion | Markdown/HTML/TXT ⇄ DOCX/ODT/RTF | Yes |
| **Calibre** (`ebook-convert`) | Ebook conversion | EPUB/MOBI/AZW3/FB2 ⇄ PDF/DOCX/TXT/HTML | Yes |
| **FFmpeg** (`ffmpeg`, `ffprobe`) | Video/audio transcoding & probing | All video and audio conversions | Yes |
| **Tesseract** | OCR | Scanned PDF/image → text | Yes |
| **ImageMagick** (`magick`/`convert`) | SVG rasterization | SVG → raster image formats | Yes (optional) |

### Python packages

| Package | Purpose |
|---|---|
| PySide6 | GUI framework |
| PyMuPDF (`fitz`) | PDF read/write/inspect/reconstruct |
| Pillow | Raster image conversion |
| python-docx | Writing DOCX from reconstructed PDF content |
| python-pptx | (reserved for future PPTX-specific editing features) |
| openpyxl | CSV ⇄ XLSX |
| EbookLib, beautifulsoup4 | (reserved for future direct EPUB parsing) |
| pytesseract | Python binding for Tesseract (optional — falls back to CLI) |

The app never assumes a tool is present: `app/utils/dependencies.py`
checks for each executable/package at runtime, caches the result, and
the **Dependencies** dialog (toolbar button) shows exactly what's
installed and what's missing, with install hints. Conversions requiring
a missing tool are refused with a clear message rather than silently
failing or producing corrupt output.

---

## Conversion capability matrix

Fidelity levels used throughout: **Lossless**, **High fidelity** (nearly
everything preserved, minor risk), **Best effort** (heuristic
reconstruction, e.g. PDF → DOCX), **Lossy** (known, structural
information loss).

| Conversion | Backend | Fidelity | Notes |
|---|---|---|---|
| DOCX/DOC/ODT/RTF/PPTX/XLSX → PDF | LibreOffice | High fidelity | Rare SmartArt/complex form fields may render slightly differently |
| CSV/XLSX → PDF | LibreOffice | High fidelity | Very wide sheets may split across pages |
| DOCX ⇄ ODT ⇄ RTF | LibreOffice | High fidelity | Rare proprietary formatting extensions may not round-trip |
| Markdown/HTML/TXT ⇄ DOCX/ODT/RTF | Pandoc | High fidelity | Plain text output cannot retain formatting/images/links |
| Markdown/HTML → PDF | LibreOffice or PyMuPDF fallback | High fidelity / reduced if LibreOffice absent | Fallback renderer has weaker CSS support |
| **PDF → DOCX/Markdown/TXT** | PyMuPDF heuristic reconstruction | **Best effort** | Headings inferred from font size; complex tables/multi-column layouts not reliably reconstructed |
| Scanned PDF → text/DOCX | Tesseract OCR | Best effort | Accuracy depends on scan quality; original formatting unrecoverable |
| CSV → XLSX | openpyxl | High fidelity | No formulas/formatting to begin with |
| XLSX → CSV | openpyxl | Lossy | Only first sheet; formulas exported as last value; formatting/charts lost |
| EPUB/MOBI/AZW3/FB2 ⇄ PDF/DOCX/TXT/HTML | Calibre | High fidelity | Interactive EPUB content (JS, embedded media) dropped; reflowable text becomes fixed layout in PDF |
| **PDF → EPUB/MOBI/AZW3** | Calibre | **Best effort** | Fixed-layout PDF heuristically reflowed into chapters; may misplace headings/footnotes |
| PNG/JPG/WEBP/GIF/BMP/TIFF/ICO ⇄ each other | Pillow | High fidelity | JPEG target flattens transparency; static-only target keeps only first frame of animation |
| SVG → raster | ImageMagick | High fidelity | Requires ImageMagick with librsvg support |
| Raster → SVG | Pillow (wrapper) | **Lossy** | Not true vector tracing — raster image is embedded inside an SVG container |
| MP4/MKV/WebM/AVI/MOV/WMV/MPEG/TS ⇄ each other | FFmpeg | High fidelity | Subtitles only embeddable in MP4/MOV/MKV; re-encoding is inherently lossy |
| MP3/AAC/WAV/FLAC/OGG/M4A ⇄ each other | FFmpeg | High fidelity | Converting lossy source to lossless target cannot recover already-lost quality |

The GUI queries this matrix live via `ConverterRegistry` and greys
out/warns about any conversion whose required tool isn't installed.

---

## Post-conversion validation

After every conversion the app performs automated checks appropriate to
the format (page/stream count, non-empty output, subtitle/audio-track
presence, duration drift for media, PDF page/content sanity) and shows
a summary like:

```
Conversion complete

Input: novel.epub
Output: novel.pdf

✓ Text preserved
✓ Images preserved
✓ Chapters preserved
✓ Table of contents preserved
✓ Metadata preserved

⚠ Interactive EPUB elements cannot be represented in PDF.
```

Failures never crash the GUI — jobs run in background workers and
report a `ConversionResult(success=False, error_message=...)`.

---

## Development

```bash
source venv/bin/activate
pip install -r requirements.txt   # includes pytest
python -m pytest app/tests/ -q
```

The test suite (41 tests) covers filesystem safety (no-overwrite,
Unicode filenames, temp cleanup), the converter registry/capability
declarations, dependency detection, and converter logic for images,
spreadsheets, documents, ebooks, video, and audio (external-tool calls
are mocked so the suite runs without LibreOffice/FFmpeg/Calibre
installed).

Code style: type hints throughout, docstrings on non-trivial modules,
no hardcoded absolute paths, no global mutable state outside the
explicit `converters.registry` singleton, and all "expected" failure
modes (missing tool, bad input, cancellation) are returned as
`ConversionResult(success=False, ...)` rather than raised — the GUI
never crashes because one file failed to convert.

---

## Building a standalone executable

```bash
pip install pyinstaller
pyinstaller packaging/localconvert.spec
```

Produces a standalone app under `dist/LocalConvert` (Windows/Linux) or
`dist/LocalConvert.app` (macOS). **Note:** this bundles only the
Python/Qt application — LibreOffice, Pandoc, Calibre, FFmpeg, and
Tesseract remain separate installs that the end user needs on their
system.

---

## Settings

Available under the **⚙ Settings** button: default output folder,
default conversion quality, theme (dark/light), hardware acceleration
toggle, temporary-file location, max simultaneous conversions, whether
to preserve metadata by default, whether to auto-open the output folder,
whether to overwrite existing files (default: off — auto-renames
instead), and logging level. Settings persist to a JSON file in the
platform-standard config directory.

---

## Safety & reliability

- Original input files are never modified or overwritten.
- Output filenames are auto-incremented (`file (1).pdf`, `file (2).pdf`, ...)
  unless the user explicitly enables "Overwrite existing files" in Settings.
- Each conversion runs in an isolated temporary workspace that is always
  cleaned up (even on failure/cancellation).
- Conversions run in background thread-pool workers, so the GUI never
  freezes and multiple files can convert concurrently (configurable cap).
- Cancellation is cooperative and safe: FFmpeg jobs are terminated
  cleanly; OCR/reconstruction loops check a cancel flag between pages.
- Filenames with spaces and Unicode characters are handled throughout.
- All errors are logged to a per-user log file in addition to being
  shown in the GUI.

---

## License

[MIT](LICENSE)