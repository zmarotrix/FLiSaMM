"""
Game install handling: path validation, the EAC bypass, launching the game and
detecting whether it is running.
"""

import enum
import logging
import os
import shutil
import threading
from pathlib import Path

import psutil

from .constants import (
    EAC_LAUNCHER_EXE, GAME_EXE, GAME_FOLDER_NAME, GAME_PROCESS_NAMES,
    SHIPPING_EXE_REL, STEAM_APP_ID
)
from .fsutil import atomic_write_json, file_sha256, load_json, CorruptFileError

log = logging.getLogger(__name__)


class GameError(Exception):
    """Raised when an operation on the game install fails."""


class EacState(enum.Enum):
    OFF = "off"            # Original launcher in place.
    ON = "on"              # Launcher replaced by a copy of the game executable.
    STALE = "stale"        # A backup exists, but Steam has restored the launcher.
    MISSING = "missing"    # EACLauncher.exe is missing entirely.


def validate_game_path(path):
    """Checks a folder for the game's files and returns a list of problems."""
    if not path or not os.path.isdir(path):
        return ["Path does not exist."]
    path = Path(path)
    errors = []
    if path.name != GAME_FOLDER_NAME:
        errors.append(f"Folder not named '{GAME_FOLDER_NAME}'.")
    if not (path / EAC_LAUNCHER_EXE).exists() and not (path / (EAC_LAUNCHER_EXE + ".bak")).exists():
        errors.append(f"Missing '{EAC_LAUNCHER_EXE}'.")
    if not (path / GAME_EXE).exists():
        errors.append(f"Missing '{GAME_EXE}'.")
    if not (path / SHIPPING_EXE_REL).exists():
        errors.append("Missing shipping executable.")
    return errors


def is_game_running():
    """True if the game's process is currently running."""
    for proc in psutil.process_iter(["name"]):
        if proc.info.get("name") in GAME_PROCESS_NAMES:
            return True
    return False


class GameInstall:
    """A game folder plus the state the manager keeps about it."""

    def __init__(self, path, state_dir):
        self.path = Path(path)
        self.launcher = self.path / EAC_LAUNCHER_EXE
        self.launcher_backup = self.path / (EAC_LAUNCHER_EXE + ".bak")
        self.game_exe = self.path / GAME_EXE
        self._record_path = Path(state_dir) / "eac.json"

    # --- EAC bypass ---

    def eac_state(self):
        """Works out whether the bypass is active, including after game updates."""
        if not self.launcher.exists():
            return EacState.MISSING
        if not self.launcher_backup.exists():
            return EacState.OFF
        current = file_sha256(self.launcher)
        if current == self._load_record().get("bypass_sha256"):
            return EacState.ON
        if self.game_exe.exists() and current == file_sha256(self.game_exe):
            return EacState.ON
        # The launcher is neither our copy nor the game executable, so Steam
        # (an update or "verify files") has put a fresh launcher back.
        return EacState.STALE

    def apply_eac_bypass(self):
        """Replaces EACLauncher.exe with a copy of the game executable."""
        state = self.eac_state()
        if state is EacState.ON:
            self.refresh_eac_bypass()
            return
        if state is EacState.MISSING:
            raise GameError(f"{EAC_LAUNCHER_EXE} is missing. Verify the game files in Steam first.")
        if not self.game_exe.exists():
            raise GameError(f"{GAME_EXE} was not found in the game folder.")
        if state is EacState.STALE:
            self.launcher_backup.unlink()

        tmp = self.launcher.with_name(self.launcher.name + ".flisamm-tmp")
        try:
            shutil.copy2(self.game_exe, tmp)
            os.replace(self.launcher, self.launcher_backup)
            os.replace(tmp, self.launcher)
        except OSError as e:
            if self.launcher_backup.exists() and not self.launcher.exists():
                os.replace(self.launcher_backup, self.launcher)
            tmp.unlink(missing_ok=True)
            raise GameError(f"Could not apply the EAC bypass: {e}") from e
        self._save_record()

    def refresh_eac_bypass(self):
        """Re-copies the game executable if a game update changed it."""
        if not self.game_exe.exists():
            return
        if file_sha256(self.launcher) == file_sha256(self.game_exe):
            return
        tmp = self.launcher.with_name(self.launcher.name + ".flisamm-tmp")
        try:
            shutil.copy2(self.game_exe, tmp)
            os.replace(tmp, self.launcher)
        except OSError as e:
            tmp.unlink(missing_ok=True)
            raise GameError(f"Could not update the EAC bypass: {e}") from e
        self._save_record()
        log.info("Refreshed the EAC bypass after a game update.")

    def remove_eac_bypass(self):
        """Restores the original EACLauncher.exe."""
        state = self.eac_state()
        try:
            if state is EacState.STALE:
                # Steam already restored the launcher; the backup is outdated.
                self.launcher_backup.unlink()
            elif self.launcher_backup.exists():
                os.replace(self.launcher_backup, self.launcher)
        except OSError as e:
            raise GameError(f"Could not remove the EAC bypass: {e}") from e

    def _load_record(self):
        try:
            return load_json(self._record_path) or {}
        except CorruptFileError:
            return {}

    def _save_record(self):
        atomic_write_json(self._record_path, {"bypass_sha256": file_sha256(self.launcher)})

    # --- Launching ---

    def launch(self, via_steam):
        """Starts the game through Steam or directly via its launcher."""
        target = f"steam://run/{STEAM_APP_ID}" if via_steam else str(self.launcher)
        if not via_steam and not self.launcher.exists():
            raise GameError(f"{EAC_LAUNCHER_EXE} not found in the game directory.")
        try:
            os.startfile(target)
        except (OSError, AttributeError) as e:
            raise GameError(f"Failed to launch the game: {e}") from e


class GameWatcher:
    """Polls for the game process on a background thread.

    The UI reads `running` from its own thread; scanning processes never
    blocks the interface.
    """

    def __init__(self, interval=2.0):
        self.running = False
        self.checked = False
        self._interval = interval
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="GameWatcher", daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _run(self):
        while True:
            try:
                self.running = is_game_running()
            except Exception:
                log.exception("Process scan failed")
            self.checked = True
            if self._stop.wait(self._interval):
                return
