"""
Locations the application reads from and writes to.

All manager data lives under %LOCALAPPDATA%\\FLiSaMM so that nothing is kept
inside the game folder or Steam's cloud-synced save folders.
"""

import hashlib
import os
import sys
from pathlib import Path

from .constants import APP_DATA_DIR_NAME

# Folder that holds main.py when running from source, or the unpacked bundle
# when running as a PyInstaller executable.
APP_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))


def app_data_dir():
    """Returns the per-user data folder, creating it if needed.

    The FLISAMM_DATA_DIR environment variable overrides the location, which is
    useful for portable setups.
    """
    override = os.environ.get("FLISAMM_DATA_DIR")
    if override:
        base = Path(override)
    elif os.environ.get("LOCALAPPDATA"):
        base = Path(os.environ["LOCALAPPDATA"]) / APP_DATA_DIR_NAME
    else:
        base = Path.home() / f".{APP_DATA_DIR_NAME.lower()}"
    base.mkdir(parents=True, exist_ok=True)
    return base


def resource_path(*parts):
    """Returns the path of a bundled file in the resources folder."""
    return APP_ROOT.joinpath("resources", *parts)


def path_key(path):
    """Returns a short, stable folder name identifying a filesystem path."""
    normalized = os.path.normcase(os.path.abspath(str(path)))
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:12]
