"""Persistent application settings.

Stored as JSON under the platform-appropriate user config directory (no
third-party dependency needed — a couple of lines of platform detection
does the job). Nothing here talks to the network.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


def user_config_dir(app_name: str = "LocalConvert") -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / app_name


def user_cache_dir(app_name: str = "LocalConvert") -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / app_name / "Cache"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / app_name
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / app_name


@dataclass
class Settings:
    output_folder: str = str(Path.home() / "Converted")
    default_quality: str = "high"  # "low" | "medium" | "high" | "maximum"
    theme: str = "dark"  # "dark" | "light"
    hardware_acceleration: bool = True
    temp_file_location: str = str(user_cache_dir() / "tmp")
    max_simultaneous_conversions: int = 2
    preserve_metadata: bool = True
    auto_open_output_folder: bool = False
    overwrite_existing_files: bool = False
    logging_level: str = "INFO"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Settings":
        valid_keys = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)


class SettingsManager:
    """Loads/saves Settings to disk, with sane fallback on corrupt files."""

    def __init__(self, config_dir: Path | None = None):
        self.config_dir = config_dir or user_config_dir()
        self.config_path = self.config_dir / "settings.json"
        self._settings = self._load()

    def _load(self) -> Settings:
        if self.config_path.exists():
            try:
                data = json.loads(self.config_path.read_text(encoding="utf-8"))
                return Settings.from_dict(data)
            except Exception:
                # Corrupt settings file: fall back to defaults rather than
                # crashing the whole app on startup.
                return Settings()
        return Settings()

    @property
    def settings(self) -> Settings:
        return self._settings

    def save(self) -> None:
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(
            json.dumps(self._settings.to_dict(), indent=2), encoding="utf-8"
        )

    def update(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            if hasattr(self._settings, key):
                setattr(self._settings, key, value)
        self.save()
