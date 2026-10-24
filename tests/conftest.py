import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def store(tmp_path):
    path = tmp_path / "appdata"
    path.mkdir()
    return path


@pytest.fixture
def game(tmp_path):
    """A minimal fake game folder."""
    root = tmp_path / "FANTASY LIFE i"
    (root / "Game/Binaries/Win64").mkdir(parents=True)
    (root / "Game/Content/Paks").mkdir(parents=True)
    (root / "Engine").mkdir()
    (root / "EACLauncher.exe").write_bytes(b"eac launcher")
    (root / "NFL1.exe").write_bytes(b"game bootstrap")
    (root / "Game/Binaries/Win64/NFL1-Win64-Shipping.exe").write_bytes(b"shipping")
    (root / "Game/Content/Paks/pakchunk0.pak").write_bytes(b"vanilla pak")
    return root


@pytest.fixture
def live(tmp_path):
    """A save folder containing a game save."""
    path = tmp_path / "remote"
    path.mkdir()
    return path


def write_save(folder, content):
    (Path(folder) / "gamedata.bin").write_bytes(content)
    (Path(folder) / "gamedata.binbak").write_bytes(content + b"-bak")


def read_save(folder):
    path = Path(folder) / "gamedata.bin"
    return path.read_bytes() if path.exists() else None


@pytest.fixture(autouse=True)
def _isolated_env(tmp_path, monkeypatch):
    monkeypatch.setenv("FLISAMM_DATA_DIR", str(tmp_path / "data-dir"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
    monkeypatch.setenv("PUBLIC", str(tmp_path / "public"))
    os.makedirs(tmp_path / "roaming", exist_ok=True)
