import json
import zipfile

import pytest

from flisamm.mods import ModError, ModManager, plan_layout

MODS = "Game/Content/Paks/~mods"


def make_zip(path, files):
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return path


def install(manager, archive, replace=False):
    pending = manager.stage([archive])
    return manager.commit(pending, replace=replace)


def test_plan_routes_loose_paks_and_skips_docs(game):
    mapping, skipped, warnings = plan_layout(
        ["MyMod/cool_P.pak", "MyMod/cool_P.utoc", "MyMod/readme.txt"], game)
    assert mapping == {"MyMod/cool_P.pak": f"{MODS}/cool_P.pak",
                       "MyMod/cool_P.utoc": f"{MODS}/cool_P.utoc"}
    assert skipped == ["MyMod/readme.txt"]
    assert warnings == []


def test_plan_keeps_game_layout_inside_wrapper(game):
    mapping, _, warnings = plan_layout(
        ["Wrapper/Game/Content/Paks/~mods/a.pak", "Wrapper/Game/Binaries/Win64/x.dll"], game)
    assert mapping["Wrapper/Game/Content/Paks/~mods/a.pak"] == f"{MODS}/a.pak"
    assert mapping["Wrapper/Game/Binaries/Win64/x.dll"] == "Game/Binaries/Win64/x.dll"
    assert warnings == []


def test_plan_warns_about_new_folders(game):
    _, _, warnings = plan_layout(["Game/Nonexistent/file.dat"], game)
    assert any("Nonexistent" in w for w in warnings)


def test_install_deploys_hardlinks_and_toggles(game, store, tmp_path):
    manager = ModManager(game, store)
    mod = install(manager, make_zip(tmp_path / "Cool Mod.zip", {"Cool/cool_P.pak": b"cool"}))
    deployed = game / MODS / "cool_P.pak"
    assert deployed.read_bytes() == b"cool"
    assert mod.name == "Cool Mod"

    manager.set_enabled(mod.id, False)
    assert not deployed.exists()
    manager.set_enabled(mod.id, True)
    assert deployed.read_bytes() == b"cool"

    manager.delete(mod.id)
    assert not deployed.exists()
    assert manager.mods == []
    assert not (manager.staging_path / mod.id).exists()


def test_overwritten_game_files_are_restored(game, store, tmp_path):
    manager = ModManager(game, store)
    mod = install(manager, make_zip(tmp_path / "Replace.zip", {
        "Game/Content/Paks/pakchunk0.pak": b"modded"}))
    target = game / "Game/Content/Paks/pakchunk0.pak"
    assert target.read_bytes() == b"modded"
    manager.set_enabled(mod.id, False)
    assert target.read_bytes() == b"vanilla pak"
    manager.set_enabled(mod.id, True)
    manager.delete(mod.id)
    assert target.read_bytes() == b"vanilla pak"


def test_load_order_resolves_conflicts(game, store, tmp_path):
    manager = ModManager(game, store)
    a = install(manager, make_zip(tmp_path / "A.zip", {"shared.pak": b"A"}))
    b = install(manager, make_zip(tmp_path / "B.zip", {"shared.pak": b"B"}))
    target = game / MODS / "shared.pak"
    assert target.read_bytes() == b"B"
    conflicts = manager.conflicts()
    assert conflicts[b.id] == ({"A"}, set())
    assert conflicts[a.id] == (set(), {"B"})

    manager.move(b.id, -1)
    assert target.read_bytes() == b"A"
    manager.delete(a.id)
    assert target.read_bytes() == b"B"
    manager.delete(b.id)
    assert not target.exists()


def test_game_update_replacing_mod_file_is_respected(game, store, tmp_path):
    manager = ModManager(game, store)
    mod = install(manager, make_zip(tmp_path / "Replace.zip", {
        "Game/Content/Paks/pakchunk0.pak": b"modded"}))
    target = game / "Game/Content/Paks/pakchunk0.pak"
    target.unlink()
    target.write_bytes(b"patched vanilla")    # Steam update writes a new file.
    manager.set_enabled(mod.id, False)
    assert target.read_bytes() == b"patched vanilla"


def test_sync_repairs_missing_files(game, store, tmp_path):
    manager = ModManager(game, store)
    install(manager, make_zip(tmp_path / "M.zip", {"m.pak": b"m"}))
    (game / MODS / "m.pak").unlink()
    manager.sync()
    assert (game / MODS / "m.pak").read_bytes() == b"m"


def test_duplicate_name_and_replace(game, store, tmp_path):
    manager = ModManager(game, store)
    install(manager, make_zip(tmp_path / "M.zip", {"m.pak": b"v1"}))
    with pytest.raises(ModError):
        install(manager, make_zip(tmp_path / "M.zip", {"m.pak": b"v2"}))
    install(manager, make_zip(tmp_path / "M.zip", {"m.pak": b"v2", "extra.pak": b"x"}), replace=True)
    assert len(manager.mods) == 1
    assert (game / MODS / "m.pak").read_bytes() == b"v2"
    assert len(list(manager.staging_path.iterdir())) == 1


def test_unsafe_archive_paths_are_ignored(game, store, tmp_path):
    manager = ModManager(game, store)
    pending = manager.stage([make_zip(tmp_path / "Evil.zip", {
        "../../evil.dll": b"x", "ok.pak": b"ok"})])
    assert list(pending.files) == [f"{MODS}/ok.pak"]
    assert "../../evil.dll" in pending.skipped
    manager.commit(pending)
    assert not (tmp_path / "evil.dll").exists()


def test_loose_pak_install(game, store, tmp_path):
    manager = ModManager(game, store)
    files = []
    for ext in (".pak", ".utoc", ".ucas"):
        f = tmp_path / f"Loose_P{ext}"
        f.write_bytes(ext.encode())
        files.append(f)
    mod = manager.commit(manager.stage(files))
    assert mod.name == "Loose_P"
    assert sorted(p.name for p in (game / MODS).iterdir()) == ["Loose_P.pak", "Loose_P.ucas", "Loose_P.utoc"]


def test_bad_archive_reports_error(game, store, tmp_path):
    bad = tmp_path / "Bad.zip"
    bad.write_bytes(b"not a zip")
    with pytest.raises(ModError):
        ModManager(game, store).stage([bad])
    assert not any((ModManager(game, store).store_path / "tmp").iterdir())


def test_state_persists(game, store, tmp_path):
    manager = ModManager(game, store)
    mod = install(manager, make_zip(tmp_path / "M.zip", {"m.pak": b"m"}))
    manager.set_enabled(mod.id, False)
    reloaded = ModManager(game, store)
    assert reloaded.get(mod.id).enabled is False


def test_migrates_legacy_mods(game, store):
    (game / MODS).mkdir(parents=True)
    (game / MODS / "on.pak").write_bytes(b"on")
    (game / MODS / "off.pak.disabled").write_bytes(b"off")
    legacy = game / "_manager_data"
    legacy.mkdir()
    (legacy / "mods.json").write_text(json.dumps([
        {"name": "On", "status": "enabled", "files": [f"{MODS}/on.pak"]},
        {"name": "Off", "status": "disabled", "files": [f"{MODS}/off.pak"]},
    ]))
    manager = ModManager(game, store)
    assert not legacy.exists()
    assert [m.name for m in manager.mods] == ["On", "Off"]
    assert (game / MODS / "on.pak").read_bytes() == b"on"
    assert not (game / MODS / "off.pak.disabled").exists()
    manager.set_enabled(manager.find_by_name("Off").id, True)
    assert (game / MODS / "off.pak").read_bytes() == b"off"


def test_detects_mods_installed_by_hand(game, store, tmp_path):
    manager = ModManager(game, store)
    managed = install(manager, make_zip(tmp_path / "Managed.zip", {"managed.pak": b"m"}))
    mods_dir = game / MODS
    for ext in (".pak", ".utoc", ".ucas"):
        (mods_dir / f"Hand_P{ext}").write_bytes(b"hand")
    (mods_dir / "Bundle").mkdir()
    (mods_dir / "Bundle" / "one.pak").write_bytes(b"1")
    (mods_dir / "Bundle" / "two.pak").write_bytes(b"2")
    (mods_dir / "Old_P.pak.disabled").write_bytes(b"old")
    (mods_dir / "notes.txt").write_text("not a mod")

    found = {d.name: d for d in manager.detect_unmanaged()}
    assert sorted(found) == ["Bundle", "Hand_P", "Old_P"]
    assert len(found["Hand_P"].files) == 3
    assert len(found["Bundle"].files) == 2
    assert found["Old_P"].enabled is False
    assert managed.name not in found


def test_adopting_detected_mods(game, store, tmp_path):
    manager = ModManager(game, store)
    install(manager, make_zip(tmp_path / "Hand_P.zip", {"other.pak": b"x"}))   # Name clash.
    mods_dir = game / MODS
    (mods_dir / "Hand_P.pak").write_bytes(b"hand")
    (mods_dir / "Old_P.pak.disabled").write_bytes(b"old")

    adopted = manager.adopt(manager.detect_unmanaged())
    assert sorted(m.name for m in adopted) == ["Hand_P (2)", "Old_P"]
    assert manager.detect_unmanaged() == []
    # Enabled mods stay in place (now linked); disabled ones leave the game folder.
    assert (mods_dir / "Hand_P.pak").read_bytes() == b"hand"
    assert not (mods_dir / "Old_P.pak.disabled").exists()
    assert not (mods_dir / "Old_P.pak").exists()

    old = manager.find_by_name("Old_P")
    manager.set_enabled(old.id, True)
    assert (mods_dir / "Old_P.pak").read_bytes() == b"old"
    manager.delete(manager.find_by_name("Hand_P (2)").id)
    assert not (mods_dir / "Hand_P.pak").exists()


def test_failed_adopt_leaves_files_in_place(game, store, monkeypatch):
    import flisamm.mods as mods_module
    manager = ModManager(game, store)
    mods_dir = game / MODS
    mods_dir.mkdir(parents=True)
    (mods_dir / "Locked_P.pak").write_bytes(b"pak")
    (mods_dir / "Locked_P.utoc").write_bytes(b"utoc")
    real_move = mods_module.move

    def flaky_move(src, dst):
        if str(src).endswith(".utoc"):
            raise PermissionError("in use")
        return real_move(src, dst)

    monkeypatch.setattr(mods_module, "move", flaky_move)
    with pytest.raises(ModError):
        manager.adopt(manager.detect_unmanaged())
    monkeypatch.setattr(mods_module, "move", real_move)
    assert sorted(p.name for p in mods_dir.iterdir()) == ["Locked_P.pak", "Locked_P.utoc"]
    assert manager.mods == []
