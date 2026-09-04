"""Shows which external tools/Python packages are installed, so the user
understands why some conversions are greyed out (spec section 7/13)."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from app.utils.dependencies import clear_cache, full_report

_ALL_TOOLS = [
    "libreoffice", "pandoc", "ebook-convert", "ffmpeg", "ffprobe", "tesseract", "magick",
    "py:fitz", "py:PIL", "py:docx", "py:pptx", "py:openpyxl", "py:pytesseract",
]


class DependencyDialog(QDialog):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Local Dependencies")
        self.setMinimumSize(560, 420)

        layout = QVBoxLayout(self)
        note = QLabel(
            "LocalConvert never uploads files anywhere - all conversions run using the "
            "tools below, installed on this computer. Conversions requiring a missing "
            "tool are disabled until it is installed."
        )
        note.setWordWrap(True)
        note.setObjectName("Muted")
        layout.addWidget(note)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Tool", "Type", "Status"])
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        self._populate()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        refresh = buttons.addButton("Re-check", QDialogButtonBox.ButtonRole.ActionRole)
        refresh.clicked.connect(self._refresh)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    def _populate(self) -> None:
        statuses = full_report(_ALL_TOOLS)
        self.table.setRowCount(len(statuses))
        for row, status in enumerate(statuses):
            display_name = status.name if not status.name.startswith("py:") else status.name
            self.table.setItem(row, 0, QTableWidgetItem(status.name))
            self.table.setItem(row, 1, QTableWidgetItem(status.kind.replace("_", " ")))
            if status.available:
                item = QTableWidgetItem(f"\u2713 Installed {('(' + status.version + ')') if status.version else ''}")
            else:
                item = QTableWidgetItem(f"\u2717 Missing - {status.hint}")
            self.table.setItem(row, 2, item)
        self.table.resizeColumnsToContents()

    def _refresh(self) -> None:
        clear_cache()
        self._populate()
