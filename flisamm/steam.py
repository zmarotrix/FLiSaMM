"""
Locates Steam, its library folders, the game install and Steam user profiles.
"""

import logging
import os
import re
from pathlib import Path

from .constants import GAME_FOLDER_NAME, STEAM_APP_ID

try:
    import winreg
except ImportError:  # Not on Windows.
    winreg = None

log = logging.getLogger(__name__)

_REGISTRY_LOCATIONS = (
    ("HKEY_CURRENT_USER", r"Software\Valve\Steam", "SteamPath"),
    ("HKEY_LOCAL_MACHINE", r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
    ("HKEY_LOCAL_MACHINE", r"SOFTWARE\Valve\Steam", "InstallPath"),
)

_VDF_TOKEN = re.compile(r'"((?:[^"\\]|\\.)*)"|([{}])|//[^\n]*|\s+')


def find_steam_path():
    """Returns the Steam installation folder, or None if it cannot be found.

    The FLISAMM_STEAM_PATH environment variable overrides the registry lookup.
    """
    override = os.environ.get("FLISAMM_STEAM_PATH")
    if override:
        return Path(override)
    if winreg is None:
        return None
    for hive_name, key_path, value_name in _REGISTRY_LOCATIONS:
        try:
            with winreg.OpenKey(getattr(winreg, hive_name), key_path) as key:
                value = winreg.QueryValueEx(key, value_name)[0]
        except OSError:
            continue
        path = Path(value)
        if path.is_dir():
            return path
    return None


def parse_vdf(text):
    """Parses Valve's KeyValues text format into nested dictionaries."""
    stack = [{}]
    key = None
    for match in _VDF_TOKEN.finditer(text):
        string, brace = match.group(1), match.group(2)
        if string is not None:
            value = string.replace('\\"', '"').replace("\\\\", "\\")
            if key is None:
                key = value
            else:
                stack[-1][key] = value
                key = None
        elif brace == "{":
            child = {}
            stack[-1][key if key is not None else ""] = child
            stack.append(child)
            key = None
        elif brace == "}":
            if len(stack) > 1:
                stack.pop()
            key = None
    return stack[0]


def _read_vdf(path):
    try:
        return parse_vdf(Path(path).read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return {}


def library_folders(steam_path):
    """Returns every Steam library folder, starting with the main one."""
    steam_path = Path(steam_path)
    folders = [steam_path]
    data = _read_vdf(steam_path / "steamapps" / "libraryfolders.vdf")
    libraries = data.get("libraryfolders") or data.get("LibraryFolders") or {}
    for value in libraries.values():
        # Newer files store a block with a "path" key; older ones the path itself.
        raw = value.get("path") if isinstance(value, dict) else value
        if not raw or not isinstance(raw, str) or not (":" in raw or raw.startswith("/")):
            continue
        folder = Path(raw)
        if folder.is_dir() and all(folder != f for f in folders):
            folders.append(folder)
    return folders


def find_game_install(steam_path=None):
    """Searches all Steam libraries for the game and returns its folder."""
    steam_path = steam_path or find_steam_path()
    if not steam_path:
        return None
    for library in library_folders(steam_path):
        steamapps = library / "steamapps"
        manifest = _read_vdf(steamapps / f"appmanifest_{STEAM_APP_ID}.acf")
        install_dir = manifest.get("AppState", {}).get("installdir") or GAME_FOLDER_NAME
        candidate = steamapps / "common" / install_dir
        if candidate.is_dir():
            log.info("Found game install at %s", candidate)
            return candidate
    return None


def steam_save_folders(steam_path=None):
    """Returns {steam_id: save_folder} for every Steam user on this PC."""
    steam_path = steam_path or find_steam_path()
    if not steam_path:
        return {}
    userdata = Path(steam_path) / "userdata"
    if not userdata.is_dir():
        return {}
    return {
        entry.name: entry / STEAM_APP_ID / "remote"
        for entry in sorted(userdata.iterdir())
        if entry.name.isdigit() and entry.is_dir()
    }
