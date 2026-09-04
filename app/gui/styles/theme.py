"""Qt stylesheets (QSS) for LocalConvert's dark and light themes.

Kept as plain strings (not external .qss resource files) to avoid any
packaging complications when building a standalone executable.
"""

from __future__ import annotations

_DARK = """
QWidget {
    background-color: #1e1f22;
    color: #e6e6e6;
    font-family: "Segoe UI", "Inter", "Helvetica Neue", sans-serif;
    font-size: 13px;
}
QMainWindow, QDialog { background-color: #1e1f22; }
#TitleBar { background-color: #17181a; }
#AppTitle { font-size: 16px; font-weight: 600; color: #f2f2f2; }
QPushButton {
    background-color: #2b2d31;
    border: 1px solid #3a3c40;
    border-radius: 6px;
    padding: 7px 14px;
}
QPushButton:hover { background-color: #34363b; }
QPushButton:pressed { background-color: #26282b; }
QPushButton#PrimaryButton {
    background-color: #5865f2;
    border: none;
    color: white;
    font-weight: 600;
}
QPushButton#PrimaryButton:hover { background-color: #6b76f5; }
QPushButton#PrimaryButton:disabled { background-color: #3a3c40; color: #888; }
QPushButton:disabled { color: #6f7075; }

#DropZone {
    background-color: #26282b;
    border: 2px dashed #43454a;
    border-radius: 12px;
}
#DropZone[dragging="true"] { border-color: #5865f2; background-color: #2a2c3a; }
#DropZoneLabel { color: #a8a8ad; font-size: 14px; }

QListWidget, QTreeWidget, QTableWidget {
    background-color: #232427;
    border: 1px solid #303236;
    border-radius: 8px;
    outline: none;
}
QListWidget::item, QTreeWidget::item { padding: 6px; border-bottom: 1px solid #2a2c30; }
QListWidget::item:selected, QTreeWidget::item:selected { background-color: #3a3d90; }
QHeaderView::section {
    background-color: #26282b; color: #c7c7c9; border: none; padding: 6px; font-weight: 600;
}

QProgressBar {
    background-color: #2b2d31; border: none; border-radius: 4px; height: 8px; text-align: center; color: transparent;
}
QProgressBar::chunk { background-color: #5865f2; border-radius: 4px; }

QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox {
    background-color: #26282b; border: 1px solid #3a3c40; border-radius: 6px; padding: 5px;
}
QComboBox QAbstractItemView { background-color: #26282b; selection-background-color: #3a3d90; }

QTabWidget::pane { border: 1px solid #303236; border-radius: 8px; }
QTabBar::tab { background: #232427; padding: 8px 16px; border-top-left-radius: 6px; border-top-right-radius: 6px; }
QTabBar::tab:selected { background: #2b2d31; color: #f2f2f2; }

QStatusBar { background-color: #17181a; color: #a8a8ad; }
QLabel#SectionTitle { font-weight: 600; font-size: 13px; color: #c7c7c9; }
QLabel#Muted { color: #8b8b90; }
QLabel#WarningLabel { color: #e0a840; }
QLabel#ErrorLabel { color: #e05a5a; }
QLabel#SuccessLabel { color: #58c26d; }

QScrollBar:vertical { background: #1e1f22; width: 10px; }
QScrollBar::handle:vertical { background: #3a3c40; border-radius: 5px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: #47494e; }
"""

_LIGHT = """
QWidget {
    background-color: #f7f7f8;
    color: #202124;
    font-family: "Segoe UI", "Inter", "Helvetica Neue", sans-serif;
    font-size: 13px;
}
QMainWindow, QDialog { background-color: #f7f7f8; }
#TitleBar { background-color: #ffffff; border-bottom: 1px solid #e2e2e4; }
#AppTitle { font-size: 16px; font-weight: 600; color: #111; }
QPushButton {
    background-color: #ffffff;
    border: 1px solid #d6d6d9;
    border-radius: 6px;
    padding: 7px 14px;
}
QPushButton:hover { background-color: #f0f0f2; }
QPushButton:pressed { background-color: #e6e6e9; }
QPushButton#PrimaryButton {
    background-color: #5865f2;
    border: none;
    color: white;
    font-weight: 600;
}
QPushButton#PrimaryButton:hover { background-color: #4752c4; }
QPushButton#PrimaryButton:disabled { background-color: #cfd0e6; color: #f0f0f5; }
QPushButton:disabled { color: #a9a9ad; }

#DropZone {
    background-color: #ffffff;
    border: 2px dashed #cfcfd4;
    border-radius: 12px;
}
#DropZone[dragging="true"] { border-color: #5865f2; background-color: #eef0ff; }
#DropZoneLabel { color: #6c6c72; font-size: 14px; }

QListWidget, QTreeWidget, QTableWidget {
    background-color: #ffffff;
    border: 1px solid #e2e2e4;
    border-radius: 8px;
    outline: none;
}
QListWidget::item, QTreeWidget::item { padding: 6px; border-bottom: 1px solid #ececee; }
QListWidget::item:selected, QTreeWidget::item:selected { background-color: #dfe2fb; }
QHeaderView::section {
    background-color: #f0f0f2; color: #46464a; border: none; padding: 6px; font-weight: 600;
}

QProgressBar {
    background-color: #e6e6ea; border: none; border-radius: 4px; height: 8px; text-align: center; color: transparent;
}
QProgressBar::chunk { background-color: #5865f2; border-radius: 4px; }

QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox {
    background-color: #ffffff; border: 1px solid #d6d6d9; border-radius: 6px; padding: 5px;
}
QComboBox QAbstractItemView { background-color: #ffffff; selection-background-color: #dfe2fb; }

QTabWidget::pane { border: 1px solid #e2e2e4; border-radius: 8px; }
QTabBar::tab { background: #eeeef0; padding: 8px 16px; border-top-left-radius: 6px; border-top-right-radius: 6px; }
QTabBar::tab:selected { background: #ffffff; color: #111; }

QStatusBar { background-color: #ffffff; color: #6c6c72; border-top: 1px solid #e2e2e4; }
QLabel#SectionTitle { font-weight: 600; font-size: 13px; color: #46464a; }
QLabel#Muted { color: #86868b; }
QLabel#WarningLabel { color: #a06a00; }
QLabel#ErrorLabel { color: #c62828; }
QLabel#SuccessLabel { color: #2e7d32; }

QScrollBar:vertical { background: #f7f7f8; width: 10px; }
QScrollBar::handle:vertical { background: #d6d6d9; border-radius: 5px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: #c2c2c6; }
"""


def stylesheet(theme: str) -> str:
    return _DARK if theme == "dark" else _LIGHT
