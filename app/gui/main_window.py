"""Main application window: Add files -> Choose format -> Configure -> Convert."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.config import Settings, SettingsManager
from app.converters import registry
from app.gui.dialogs.dependency_dialog import DependencyDialog
from app.gui.dialogs.settings_dialog import SettingsDialog
from app.gui.dialogs.summary_dialog import ConversionSummaryDialog
from app.gui.styles.theme import stylesheet
from app.gui.widgets.drop_zone import DropZone
from app.gui.widgets.file_queue import FileQueueTable
from app.models import ConversionJob, ConversionResult, JobStatus
from app.utils.fs import safe_stem
from app.utils.logging_setup import get_logger
from app.workers.conversion_worker import ConversionQueueManager

logger = get_logger("gui.main_window")


class MainWindow(QMainWindow):
    def __init__(self, settings_manager: SettingsManager):
        super().__init__()
        self.settings_manager = settings_manager
        self.setWindowTitle("LocalConvert")
        self.resize(980, 680)

        self.queue_manager = ConversionQueueManager(
            max_concurrent=settings_manager.settings.max_simultaneous_conversions
        )
        self.queue_manager.job_started.connect(self._on_job_started)
        self.queue_manager.job_progress.connect(self._on_job_progress)
        self.queue_manager.job_finished.connect(self._on_job_finished)

        self._jobs: dict[str, ConversionJob] = {}
        self._results: dict[str, ConversionResult] = {}
        self._history: list[tuple[ConversionJob, ConversionResult]] = []

        self._build_ui()
        self.apply_theme(settings_manager.settings.theme)

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(12)

        # -- Title bar row --------------------------------------------------
        title_row = QHBoxLayout()
        title = QLabel("LocalConvert")
        title.setObjectName("AppTitle")
        title_row.addWidget(title)
        title_row.addStretch()

        deps_btn = QPushButton("Dependencies")
        deps_btn.clicked.connect(self._show_dependencies)
        title_row.addWidget(deps_btn)

        settings_btn = QPushButton("\u2699 Settings")
        settings_btn.clicked.connect(self._show_settings)
        title_row.addWidget(settings_btn)
        root.addLayout(title_row)

        tabs = QTabWidget()
        root.addWidget(tabs)

        tabs.addTab(self._build_convert_tab(), "Convert")
        tabs.addTab(self._build_history_tab(), "History")

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready.")

    def _build_convert_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Drop zone + add buttons
        self.drop_zone = DropZone()
        self.drop_zone.files_dropped.connect(self._add_paths)
        layout.addWidget(self.drop_zone)

        add_row = QHBoxLayout()
        add_files_btn = QPushButton("+ Add Files")
        add_files_btn.clicked.connect(self._browse_add_files)
        add_folder_btn = QPushButton("Add Folder")
        add_folder_btn.clicked.connect(self._browse_add_folder)
        clear_btn = QPushButton("Clear List")
        clear_btn.clicked.connect(self._clear_queue)
        add_row.addWidget(add_files_btn)
        add_row.addWidget(add_folder_btn)
        add_row.addStretch()
        add_row.addWidget(clear_btn)
        layout.addLayout(add_row)

        # Files table
        files_label = QLabel("Files")
        files_label.setObjectName("SectionTitle")
        layout.addWidget(files_label)

        self.file_table = FileQueueTable()
        layout.addWidget(self.file_table, stretch=1)

        # Output format + folder controls
        controls_row = QHBoxLayout()
        controls_row.addWidget(QLabel("Output format:"))
        self.format_combo = QComboBox()
        self.format_combo.currentTextChanged.connect(self._on_format_changed)
        controls_row.addWidget(self.format_combo)
        controls_row.addSpacing(20)

        controls_row.addWidget(QLabel("Output folder:"))
        self.output_folder_edit = QLineEdit(self.settings_manager.settings.output_folder)
        controls_row.addWidget(self.output_folder_edit, stretch=1)
        browse_out_btn = QPushButton("Browse")
        browse_out_btn.clicked.connect(self._browse_output_folder)
        controls_row.addWidget(browse_out_btn)
        open_out_btn = QPushButton("Open output folder")
        open_out_btn.clicked.connect(self._open_output_folder)
        controls_row.addWidget(open_out_btn)
        layout.addLayout(controls_row)

        self.capability_label = QLabel("")
        self.capability_label.setObjectName("Muted")
        self.capability_label.setWordWrap(True)
        layout.addWidget(self.capability_label)

        # Convert / Cancel buttons
        action_row = QHBoxLayout()
        action_row.addStretch()
        self.cancel_btn = QPushButton("Cancel All")
        self.cancel_btn.clicked.connect(self._cancel_all)
        self.cancel_btn.setEnabled(False)
        action_row.addWidget(self.cancel_btn)
        self.convert_btn = QPushButton("Convert All")
        self.convert_btn.setObjectName("PrimaryButton")
        self.convert_btn.clicked.connect(self._convert_all)
        action_row.addWidget(self.convert_btn)
        layout.addLayout(action_row)

        self._pending_paths: list[Path] = []
        return tab

    def _build_history_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.history_list = QListWidget()
        self.history_list.itemDoubleClicked.connect(self._show_history_summary)
        layout.addWidget(self.history_list)
        hint = QLabel("Double-click an entry to see its full conversion summary.")
        hint.setObjectName("Muted")
        layout.addWidget(hint)
        return tab

    # ------------------------------------------------------------- actions

    def apply_theme(self, theme: str) -> None:
        self.setStyleSheet(stylesheet(theme))

    def _browse_add_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Select files to convert")
        self._add_paths([Path(p) for p in paths])

    def _browse_add_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select a folder to convert")
        if folder:
            all_files = [p for p in Path(folder).rglob("*") if p.is_file()]
            self._add_paths(all_files)

    def _add_paths(self, paths: list[Path]) -> None:
        added = 0
        for path in paths:
            if path.is_dir():
                for f in path.rglob("*"):
                    if f.is_file():
                        self._pending_paths.append(f)
                        added += 1
            elif path.is_file():
                self._pending_paths.append(path)
                added += 1
        if added:
            self._refresh_format_choices()
            self._rebuild_queue_preview()
            self.statusBar().showMessage(f"Added {added} file(s).", 4000)

    def _refresh_format_choices(self) -> None:
        current = self.format_combo.currentText()
        input_formats = {p.suffix.lower().lstrip(".") for p in self._pending_paths}
        # Union of every output format reachable from any of the added
        # input formats; the per-format capability panel below clarifies
        # which specific input->output pairs are actually supported.
        possible: set[str] = set()
        for fmt in input_formats:
            possible |= registry.possible_output_formats(fmt)

        self.format_combo.blockSignals(True)
        self.format_combo.clear()
        self.format_combo.addItems(sorted(possible))
        if current in possible:
            self.format_combo.setCurrentText(current)
        self.format_combo.blockSignals(False)
        self._on_format_changed(self.format_combo.currentText())

    def _on_format_changed(self, fmt: str) -> None:
        if not fmt:
            self.capability_label.setText("")
            return
        notes = []
        input_formats = {p.suffix.lower().lstrip(".") for p in self._pending_paths}
        for in_fmt in input_formats:
            found = registry.find_capability(in_fmt, fmt)
            if not found:
                notes.append(f"\u2717 {in_fmt.upper()} \u2192 {fmt.upper()} is not supported.")
                continue
            converter, cap = found
            from app.utils.dependencies import missing_from
            missing = missing_from(cap.required_tools)
            if missing:
                names = ", ".join(m.name for m in missing)
                notes.append(f"\u26a0 {in_fmt.upper()} \u2192 {fmt.upper()} needs: {names} (not installed).")
            else:
                notes.append(f"\u2713 {in_fmt.upper()} \u2192 {fmt.upper()} via {cap.backend_name} ({cap.fidelity.value}).")
        self.capability_label.setText("\n".join(notes))

    def _rebuild_queue_preview(self) -> None:
        self.file_table.clear_all()
        fmt = self.format_combo.currentText() or "pdf"
        for path in self._pending_paths:
            self.file_table.add_job_row(job_id=str(id(path)), input_path=path, output_format=fmt)

    def _browse_output_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose output folder", self.output_folder_edit.text())
        if folder:
            self.output_folder_edit.setText(folder)

    def _open_output_folder(self) -> None:
        folder = Path(self.output_folder_edit.text())
        folder.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            subprocess.run(["explorer", str(folder)])
        elif sys.platform == "darwin":
            subprocess.run(["open", str(folder)])
        else:
            subprocess.run(["xdg-open", str(folder)])

    def _clear_queue(self) -> None:
        self._pending_paths.clear()
        self.file_table.clear_all()
        self.capability_label.setText("")

    def _convert_all(self) -> None:
        if not self._pending_paths:
            QMessageBox.information(self, "No files", "Add some files first.")
            return
        out_fmt = self.format_combo.currentText()
        if not out_fmt:
            QMessageBox.information(self, "No output format", "Choose an output format first.")
            return

        out_dir = Path(self.output_folder_edit.text())
        self.queue_manager.set_max_concurrent(self.settings_manager.settings.max_simultaneous_conversions)

        self.file_table.clear_all()
        self._jobs.clear()

        for path in self._pending_paths:
            found = registry.find_capability(path.suffix.lower().lstrip("."), out_fmt)
            job = ConversionJob(input_path=path, output_format=out_fmt, output_dir=out_dir)
            self._jobs[job.job_id] = job
            self.file_table.add_job_row(job.job_id, path, out_fmt)
            if not found:
                self.file_table.update_status(job.job_id, JobStatus.SKIPPED, "Unsupported conversion")
                continue
            self.queue_manager.submit(job)

        self.convert_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.statusBar().showMessage("Converting...")

    def _cancel_all(self) -> None:
        self.queue_manager.cancel_all()
        self.statusBar().showMessage("Cancelling...", 4000)

    # ------------------------------------------------------------- signals

    def _on_job_started(self, job_id: str) -> None:
        self.file_table.update_status(job_id, JobStatus.RUNNING)

    def _on_job_progress(self, job_id: str, fraction: float, message: str) -> None:
        self.file_table.update_progress(job_id, fraction)
        if message:
            self.statusBar().showMessage(message, 2000)

    def _on_job_finished(self, job_id: str, result: ConversionResult) -> None:
        job = self._jobs.get(job_id)
        status = JobStatus.SUCCESS if result.success else JobStatus.FAILED
        self.file_table.update_status(job_id, status, result.error_message)
        self.file_table.update_progress(job_id, 1.0 if result.success else 0.0)
        self._results[job_id] = result

        if job:
            self._history.append((job, result))
            mark = "\u2713" if result.success else "\u2717"
            entry = f"{mark} {job.input_path.name} \u2192 {job.output_format.upper()}"
            self.history_list.insertItem(0, entry)
            self.history_list.item(0).setData(Qt.ItemDataRole.UserRole, len(self._history) - 1)

        if self.queue_manager.active_count() == 0:
            self.convert_btn.setEnabled(True)
            self.cancel_btn.setEnabled(False)
            self.statusBar().showMessage("All conversions finished.", 5000)
            if self.settings_manager.settings.auto_open_output_folder and result.success:
                self._open_output_folder()

    def _show_history_summary(self, item) -> None:
        idx = item.data(Qt.ItemDataRole.UserRole)
        if idx is None or idx >= len(self._history):
            return
        job, result = self._history[idx]
        dlg = ConversionSummaryDialog(job.input_path.name, result, parent=self)
        dlg.exec()

    def _show_settings(self) -> None:
        dlg = SettingsDialog(self.settings_manager, parent=self)
        if dlg.exec():
            self.apply_theme(self.settings_manager.settings.theme)
            self.output_folder_edit.setText(self.settings_manager.settings.output_folder)

    def _show_dependencies(self) -> None:
        dlg = DependencyDialog(parent=self)
        dlg.exec()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override
        if self.queue_manager.active_count() > 0:
            reply = QMessageBox.question(
                self, "Conversions in progress",
                "Conversions are still running. Cancel them and quit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.queue_manager.cancel_all()
            self.queue_manager.wait_for_all(5000)
        event.accept()
