"""Drag-and-drop area for adding files/folders."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class DropZone(QWidget):
    files_dropped = Signal(list)  # list[Path]

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("DropZone")
        self.setAcceptDrops(True)
        self.setMinimumHeight(140)

        layout = QVBoxLayout(self)
        layout.setAlignment(layout.alignment())
        label = QLabel("Drop files or folders here")
        label.setObjectName("DropZoneLabel")
        label.setAlignment(label.alignment())
        layout.addStretch()
        layout.addWidget(label, 0, alignment=label.alignment())
        layout.addStretch()
        self._label = label
        from PySide6.QtCore import Qt
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def dragEnterEvent(self, event):  # noqa: N802 - Qt override
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setProperty("dragging", True)
            self.style().unpolish(self)
            self.style().polish(self)

    def dragLeaveEvent(self, event):  # noqa: N802 - Qt override
        self.setProperty("dragging", False)
        self.style().unpolish(self)
        self.style().polish(self)

    def dropEvent(self, event):  # noqa: N802 - Qt override
        self.setProperty("dragging", False)
        self.style().unpolish(self)
        self.style().polish(self)
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        if paths:
            self.files_dropped.emit(paths)
        event.acceptProposedAction()
