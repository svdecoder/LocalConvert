"""Table widget listing queued files, their target format, and status."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QProgressBar, QTableWidget, QTableWidgetItem, QWidget

from app.models import JobStatus

_ICONS = {
    "pdf": "\U0001F4C4", "docx": "\U0001F4C4", "doc": "\U0001F4C4", "odt": "\U0001F4C4",
    "rtf": "\U0001F4C4", "txt": "\U0001F4C4", "md": "\U0001F4C4", "html": "\U0001F4C4",
    "epub": "\U0001F4D5", "mobi": "\U0001F4D5", "azw3": "\U0001F4D5",
    "pptx": "\U0001F4CA", "xlsx": "\U0001F4CA", "csv": "\U0001F4CA",
    "mp4": "\U0001F3AC", "mkv": "\U0001F3AC", "webm": "\U0001F3AC", "avi": "\U0001F3AC",
    "mov": "\U0001F3AC", "wmv": "\U0001F3AC",
    "mp3": "\U0001F3B5", "wav": "\U0001F3B5", "flac": "\U0001F3B5", "aac": "\U0001F3B5",
    "png": "\U0001F5BC", "jpg": "\U0001F5BC", "jpeg": "\U0001F5BC", "webp": "\U0001F5BC",
    "gif": "\U0001F5BC", "svg": "\U0001F5BC",
}

_STATUS_TEXT = {
    JobStatus.QUEUED: "Ready",
    JobStatus.RUNNING: "Converting...",
    JobStatus.SUCCESS: "Done",
    JobStatus.FAILED: "Failed",
    JobStatus.CANCELLED: "Cancelled",
    JobStatus.SKIPPED: "Skipped",
}

COL_FILE, COL_CONVERSION, COL_STATUS, COL_PROGRESS = range(4)


class FileQueueTable(QTableWidget):
    remove_requested = Signal(str)  # job_id

    def __init__(self, parent: QWidget | None = None):
        super().__init__(0, 4, parent)
        self.setHorizontalHeaderLabels(["File", "Conversion", "Status", "Progress"])
        self.horizontalHeader().setSectionResizeMode(COL_FILE, QHeaderView.ResizeMode.Stretch)
        self.horizontalHeader().setSectionResizeMode(COL_CONVERSION, QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(COL_STATUS, QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(COL_PROGRESS, QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(COL_PROGRESS, 140)
        self.verticalHeader().setVisible(False)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setShowGrid(False)

        self._row_by_job_id: dict[str, int] = {}
        self._progress_bars: dict[str, QProgressBar] = {}

    def add_job_row(self, job_id: str, input_path: Path, output_format: str) -> None:
        row = self.rowCount()
        self.insertRow(row)
        icon = _ICONS.get(input_path.suffix.lower().lstrip("."), "\U0001F4C1")
        self.setItem(row, COL_FILE, QTableWidgetItem(f"{icon}  {input_path.name}"))
        self.setItem(
            row, COL_CONVERSION,
            QTableWidgetItem(f"{input_path.suffix.upper().lstrip('.')} \u2192 {output_format.upper()}"),
        )
        self.setItem(row, COL_STATUS, QTableWidgetItem(_STATUS_TEXT[JobStatus.QUEUED]))

        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(0)
        bar.setTextVisible(False)
        self.setCellWidget(row, COL_PROGRESS, bar)

        self._row_by_job_id[job_id] = row
        self._progress_bars[job_id] = bar

    def update_status(self, job_id: str, status: JobStatus, detail: str = "") -> None:
        row = self._row_by_job_id.get(job_id)
        if row is None:
            return
        text = _STATUS_TEXT.get(status, status.value)
        if detail:
            text = f"{text} - {detail}" if status == JobStatus.FAILED else detail
        item = self.item(row, COL_STATUS)
        if item:
            item.setText(text)

    def update_progress(self, job_id: str, fraction: float) -> None:
        bar = self._progress_bars.get(job_id)
        if bar:
            bar.setValue(int(max(0.0, min(1.0, fraction)) * 100))

    def clear_all(self) -> None:
        self.setRowCount(0)
        self._row_by_job_id.clear()
        self._progress_bars.clear()

    def job_id_for_row(self, row: int) -> str | None:
        for job_id, r in self._row_by_job_id.items():
            if r == row:
                return job_id
        return None
