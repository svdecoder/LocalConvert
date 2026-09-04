"""Post-conversion summary dialog — the "Conversion complete" box from the
spec, showing preserved/lost features and warnings."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QTextEdit, QVBoxLayout, QWidget

from app.models import ConversionResult


class ConversionSummaryDialog(QDialog):
    def __init__(self, input_name: str, result: ConversionResult, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Conversion Summary")
        self.setMinimumSize(480, 360)

        layout = QVBoxLayout(self)

        title = QLabel("Conversion complete" if result.success else "Conversion failed")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        info = QLabel(
            f"Input: {input_name}\nOutput: {result.output_path.name if result.output_path else '(none)'}"
        )
        info.setObjectName("Muted")
        layout.addWidget(info)

        body = QTextEdit()
        body.setReadOnly(True)
        lines = result.summary_lines()
        if result.error_message and not result.success:
            lines.append(f"\u2717 {result.error_message}")
        if not lines:
            lines = ["No structural information to report for this conversion."]
        body.setPlainText("\n".join(lines))
        layout.addWidget(body)

        if result.backend_used:
            backend_label = QLabel(f"Backend used: {result.backend_used}")
            backend_label.setObjectName("Muted")
            layout.addWidget(backend_label)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
