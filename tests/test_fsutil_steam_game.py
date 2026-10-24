import json

import pytest

from flisamm import fsutil, steam
from flisamm.config import AppConfig
from flisamm.game import EacState, GameError, GameInstall, validate_game_path


# --- fsutil ---

def test_atomic_json_keeps_backup_and_recovers(tmp_path):
    path = tmp_path / "data.json"
    fsutil.atomic_write_json(path, {"v": 1})
    fsutil.atomic_write_json(path, {"v": 2})
    assert json.loads(fsutil.backup_path(path).read_text())["v"] == 1
    path.write_text("{ truncated")
    assert fsutil.load_json(path) == {"v": 1}


def test_load_json_raises_when_everything_is_corrupt(tmp_path):
    path = tmp_path / "data.json"
    path.write_text("nope")
    with pytest.raises(fsutil.CorruptFileError):
        fsutil.load_json(path)
    assert fsutil.load_json(tmp_path / "missing.json") is None


@pytest.mark.parametrize("name, expected", [
    ("Game/Content/x.pak", "Game/Content/x.pak"),
    ("Game\\Content\\x.pak", "Game/Content/x.pak"),
    ("./a/./b.txt", "a/b.txt"),
    ("../evil.dll", None),
    ("a/../../evil.dll", None),
    ("/abs/path", None),
    ("C:/Windows/evil.dll", None),
    ("file.txt:stream", None),
])
def test_safe_relpath(name, expected):
    assert fsutil.safe_relpath(name) == expected


# --- steam ---

LIBRARY_VDF = '''
"libraryfolders"
{
    "0"
    {
        "path"      "%s"
        "apps" { "228980" "1" }
    }
    "1"
    {
        "path"      "%s"
    }
}
'''


def test_parse_vdf_handles_nesting_and_escapes():
    data = steam.parse_vdf('"a" { "b" "c:\\\\x" // comment\n "d" { "e" "f" } }')
    assert data == {"a": {"b": "c:\\x", "d": {"e": "f"}}}


def test_find_game_in_secondary_library(tmp_path):
    main = tmp_path / "Steam"
    other = tmp_path / "Library2"
    (main / "steamapps").mkdir(parents=True)
    vdf = LIBRARY_VDF % (str(main).replace("\\", "\\\\"), str(other).replace("\\", "\\\\"))
    (main / "steamapps" / "libraryfolders.vdf").write_text(vdf)
    game_dir = other / "steamapps" / "common" / "FANTASY LIFE i"
    game_dir.mkdir(parents=True)
    (other / "steamapps" / "appmanifest_2993780.acf").write_text(
        '"AppState" { "appid" "2993780" "installdir" "FANTASY LIFE i" }')
    assert steam.library_folders(main) == [main, other]
    assert steam.find_game_install(main) == game_dir


def test_steam_save_folders(tmp_path):
    (tmp_path / "userdata" / "123").mkdir(parents=True)
    (tmp_path / "userdata" / "anonymous").mkdir()
    folders = steam.steam_save_folders(tmp_path)
    assert list(folders) == ["123"]
    assert folders["123"].parts[-2:] == ("2993780", "remote")


# --- config ---

def test_config_round_trip(store):
    config = AppConfig.load(store)
    config.game_path = "D:/Games/FANTASY LIFE i"
    config.launch_via_steam = False
    config.save()
    loaded = AppConfig.load(store)
    assert loaded.game_path == "D:/Games/FANTASY LIFE i"
    assert loaded.launch_via_steam is False


# --- game / EAC ---

def test_validate_game_path(game, tmp_path):
    assert validate_game_path(game) == []
    assert validate_game_path(tmp_path / "nope") == ["Path does not exist."]


def test_eac_bypass_cycle(game, store):
    install = GameInstall(game, store)
    assert install.eac_state() is EacState.OFF
    install.apply_eac_bypass()
    assert install.eac_state() is EacState.ON
    assert (game / "EACLauncher.exe").read_bytes() == b"game bootstrap"
    assert (game / "EACLauncher.exe.bak").read_bytes() == b"eac launcher"
    install.remove_eac_bypass()
    assert install.eac_state() is EacState.OFF
    assert (game / "EACLauncher.exe").read_bytes() == b"eac launcher"
    assert not (game / "EACLauncher.exe.bak").exists()


def test_eac_detects_steam_restoring_launcher(game, store):
    install = GameInstall(game, store)
    install.apply_eac_bypass()
    # Steam "verify files" puts a (possibly newer) launcher back.
    (game / "EACLauncher.exe").write_bytes(b"eac launcher v2")
    assert install.eac_state() is EacState.STALE
    install.remove_eac_bypass()
    assert install.eac_state() is EacState.OFF
    assert (game / "EACLauncher.exe").read_bytes() == b"eac launcher v2"


def test_eac_survives_game_exe_update(game, store):
    install = GameInstall(game, store)
    install.apply_eac_bypass()
    (game / "NFL1.exe").write_bytes(b"game bootstrap v2")
    assert install.eac_state() is EacState.ON  # Recognized via the recorded hash.
    install.refresh_eac_bypass()
    assert (game / "EACLauncher.exe").read_bytes() == b"game bootstrap v2"


def test_eac_missing_launcher(game, store):
    (game / "EACLauncher.exe").unlink()
    install = GameInstall(game, store)
    assert install.eac_state() is EacState.MISSING
    with pytest.raises(GameError):
        install.apply_eac_bypass()
