"""
Application settings, stored as config.json in the per-user data folder.
"""

import logging
from dataclasses import asdict, dataclass
from pathlib import Path

from .fsutil import CorruptFileError, atomic_write_json, load_json
from .paths import APP_ROOT

log = logging.getLogger(__name__)

CONFIG_NAME = "config.json"


@dataclass
class AppConfig:
    """User settings that persist between runs."""
    game_path: str = ""
    launch_via_steam: bool = True

    @classmethod
    def load(cls, data_dir):
        """Loads settings, importing a config.json left by older versions."""
        path = Path(data_dir) / CONFIG_NAME
        data = cls._read(path)
        if data is None:
            # Versions before 1.0 kept config.json next to main.py (or in
            # whatever folder the app was started from).
            for legacy in (APP_ROOT / CONFIG_NAME, Path.cwd() / CONFIG_NAME):
                data = cls._read(legacy)
                if data is not None:
                    log.info("Imported settings from %s", legacy)
                    break
        config = cls()
        if data:
            config.game_path = str(data.get("game_path") or "")
            config.launch_via_steam = bool(data.get("launch_via_steam", True))
        config._path = path
        if data is not None and not path.exists():
            config.save()
        return config

    @staticmethod
    def _read(path):
        try:
            data = load_json(path)
        except CorruptFileError as e:
            log.warning("%s", e)
            return None
        return data if isinstance(data, dict) else None

    def save(self):
        """Writes the settings to disk."""
        atomic_write_json(self._path, asdict(self))
