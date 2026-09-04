"""LocalConvert entry point.

Run with:  python -m app.main
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow `python app/main.py` as well as `python -m app.main` by ensuring
# the project root is importable either way.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication  # noqa: E402

from app.config import SettingsManager, user_cache_dir  # noqa: E402
from app.converters import register_all  # noqa: E402
from app.gui.main_window import MainWindow  # noqa: E402
from app.utils.logging_setup import get_logger, setup_logging  # noqa: E402


def main() -> int:
    settings_manager = SettingsManager()
    settings = settings_manager.settings

    log_dir = user_cache_dir() / "logs"
    setup_logging(log_dir, level=settings.logging_level)
    logger = get_logger("main")
    logger.info("Starting LocalConvert (fully local, no network calls made for conversion).")

    register_all()

    app = QApplication(sys.argv)
    app.setApplicationName("LocalConvert")
    app.setOrganizationName("LocalConvert")

    window = MainWindow(settings_manager)
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
