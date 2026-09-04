"""Settings page, per spec section 11."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.config import Settings, SettingsManager


class SettingsDialog(QDialog):
    def __init__(self, settings_manager: SettingsManager, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(480)
        self._mgr = settings_manager
        s: Settings = settings_manager.settings

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        # Default output folder
        self.output_folder_edit = QLineEdit(s.output_folder)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_output_folder)
        row = QHBoxLayout()
        row.addWidget(self.output_folder_edit)
        row.addWidget(browse_btn)
        row_widget = QWidget()
        row_widget.setLayout(row)
        form.addRow("Default output folder:", row_widget)

        # Default quality
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["low", "medium", "high", "maximum"])
        self.quality_combo.setCurrentText(s.default_quality)
        form.addRow("Default conversion quality:", self.quality_combo)

        # Theme
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["dark", "light"])
        self.theme_combo.setCurrentText(s.theme)
        form.addRow("Theme:", self.theme_combo)

        # Hardware acceleration
        self.hw_accel_check = QCheckBox("Enable hardware acceleration when available")
        self.hw_accel_check.setChecked(s.hardware_acceleration)
        form.addRow("", self.hw_accel_check)

        # Temp file location
        self.temp_dir_edit = QLineEdit(s.temp_file_location)
        temp_browse_btn = QPushButton("Browse...")
        temp_browse_btn.clicked.connect(self._browse_temp_folder)
        temp_row = QHBoxLayout()
        temp_row.addWidget(self.temp_dir_edit)
        temp_row.addWidget(temp_browse_btn)
        temp_row_widget = QWidget()
        temp_row_widget.setLayout(temp_row)
        form.addRow("Temporary file location:", temp_row_widget)

        # Max simultaneous conversions
        self.max_concurrent_spin = QSpinBox()
        self.max_concurrent_spin.setRange(1, 16)
        self.max_concurrent_spin.setValue(s.max_simultaneous_conversions)
        form.addRow("Max simultaneous conversions:", self.max_concurrent_spin)

        # Preserve metadata
        self.preserve_metadata_check = QCheckBox("Preserve metadata by default")
        self.preserve_metadata_check.setChecked(s.preserve_metadata)
        form.addRow("", self.preserve_metadata_check)

        # Auto open output folder
        self.auto_open_check = QCheckBox("Automatically open output folder when done")
        self.auto_open_check.setChecked(s.auto_open_output_folder)
        form.addRow("", self.auto_open_check)

        # Overwrite existing files
        self.overwrite_check = QCheckBox("Overwrite existing files (unchecked = auto-rename)")
        self.overwrite_check.setChecked(s.overwrite_existing_files)
        form.addRow("", self.overwrite_check)

        # Logging level
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self.log_level_combo.setCurrentText(s.logging_level)
        form.addRow("Logging level:", self.log_level_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse_output_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Choose default output folder", self.output_folder_edit.text())
        if path:
            self.output_folder_edit.setText(path)

    def _browse_temp_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Choose temporary file location", self.temp_dir_edit.text())
        if path:
            self.temp_dir_edit.setText(path)

    def _on_accept(self) -> None:
        self._mgr.update(
            output_folder=self.output_folder_edit.text(),
            default_quality=self.quality_combo.currentText(),
            theme=self.theme_combo.currentText(),
            hardware_acceleration=self.hw_accel_check.isChecked(),
            temp_file_location=self.temp_dir_edit.text(),
            max_simultaneous_conversions=self.max_concurrent_spin.value(),
            preserve_metadata=self.preserve_metadata_check.isChecked(),
            auto_open_output_folder=self.auto_open_check.isChecked(),
            overwrite_existing_files=self.overwrite_check.isChecked(),
            logging_level=self.log_level_combo.currentText(),
        )
        self.accept()
