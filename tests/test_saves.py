import json
import os
import zipfile

import pytest

from conftest import read_save, write_save
from flisamm.saves import (
    ACTIVE_SAVE_NAME, SaveError, SaveProfile, discover_save_locations
)


def make_profile(live, store, initial=b"original"):
    if initial is not None:
        write_save(live, initial)
    profile = SaveProfile("Test", live, store)
    if initial is not None:
        profile.initialize_from_live_save("First")
    return profile


def test_adopts_existing_save(live, store):
    profile = make_profile(live, store)
    slot_id = profile.active_slot_id
    assert profile.is_slot_loaded(slot_id)
    assert (profile.slot_dir(slot_id) / ACTIVE_SAVE_NAME).exists()
    # Manager data is kept out of the game's save folder.
    assert sorted(p.name for p in live.iterdir()) == ["gamedata.bin", "gamedata.binbak"]


def test_switch_slots_preserves_progress(live, store):
    profile = make_profile(live, store)
    first = profile.active_slot_id
    second = profile.create_slot("Second")

    write_save(live, b"first-progress")
    assert profile.load_slot(second) is False      # Empty slot: live save cleared.
    assert read_save(live) is None

    write_save(live, b"second-progress")           # The game creates a new save.
    assert profile.load_slot(first) is True
    assert read_save(live) == b"first-progress"
    assert profile.load_slot(second) is True
    assert read_save(live) == b"second-progress"


def test_reloading_loaded_slot_keeps_progress(live, store):
    profile = make_profile(live, store)
    write_save(live, b"newer")
    profile.load_slot(profile.active_slot_id)
    assert read_save(live) == b"newer"


def test_safety_snapshots_are_kept_and_pruned(live, store):
    profile = make_profile(live, store)
    first = profile.active_slot_id
    other = profile.create_slot("Other")
    for i in range(15):
        write_save(live, f"progress {i}".encode())
        profile.load_slot(other if i % 2 == 0 else first)
    snapshots = list(profile.safety_path.glob("*.zip"))
    assert len(snapshots) == 10


def test_failed_swap_rolls_back(live, store, monkeypatch):
    profile = make_profile(live, store)
    first = profile.active_slot_id
    second = profile.create_slot("Second")
    profile.load_slot(second)
    write_save(live, b"second data")
    real_replace = os.replace

    def flaky_replace(src, dst):
        # Fail while moving the incoming save into place (e.g. a locked file).
        if "flisamm-in" in str(src):
            raise PermissionError("file locked")
        return real_replace(src, dst)

    monkeypatch.setattr(os, "replace", flaky_replace)
    with pytest.raises(SaveError):
        profile.load_slot(first)
    monkeypatch.setattr(os, "replace", real_replace)
    assert read_save(live) == b"second data"


def test_backup_and_restore(live, store):
    profile = make_profile(live, store)
    slot = profile.active_slot_id
    backup = profile.create_backup(slot)
    assert profile.slots[slot].backups[backup].name == "Backup - 0001"
    write_save(live, b"later")
    profile.restore_backup(slot, backup)
    assert read_save(live) == b"original"
    profile.rename_backup(slot, backup, "Before boss")
    assert SaveProfile("Test", live, store).slots[slot].backups[backup].name == "Before boss"
    profile.delete_backup(slot, backup)
    assert not profile.slots[slot].backups


def test_restore_backup_from_other_slot_switches_slot(live, store):
    profile = make_profile(live, store)
    first = profile.active_slot_id
    backup = profile.create_backup(first)
    second = profile.create_slot("Second")
    profile.load_slot(second)
    write_save(live, b"second")
    profile.restore_backup(first, backup)
    assert profile.active_slot_id == first
    assert read_save(live) == b"original"
    # The second slot's progress was saved on the way out.
    profile.load_slot(second)
    assert read_save(live) == b"second"


def test_backup_requires_loaded_slot(live, store):
    profile = make_profile(live, store)
    other = profile.create_slot("Other")
    with pytest.raises(SaveError):
        profile.create_backup(other)


def test_delete_loaded_slot_clears_live_save(live, store):
    profile = make_profile(live, store)
    profile.delete_slot(profile.active_slot_id)
    assert read_save(live) is None
    assert profile.active_slot_id is None
    assert list(profile.safety_path.glob("*delete-slot.zip"))


def test_copy_slot_includes_latest_progress(live, store, tmp_path):
    profile = make_profile(live, store)
    slot = profile.active_slot_id
    write_save(live, b"latest")
    other_live = tmp_path / "other"
    other_live.mkdir()
    dest = SaveProfile("Other", other_live, store)
    profile.copy_slot_to(dest, slot)
    assert dest.slots[slot].name == "First"
    dest.load_slot(slot)
    assert read_save(other_live) == b"latest"
    # The copy is independent of the source.
    dest.rename_slot(slot, "Renamed")
    assert profile.slots[slot].name == "First"
    with pytest.raises(SaveError):
        profile.copy_slot_to(dest, slot)       # Loaded in the destination.


def test_corrupt_metadata_is_recovered(live, store):
    profile = make_profile(live, store)
    slot = profile.active_slot_id
    profile.create_backup(slot)
    profile.metadata_path.write_text("{ broken")
    from flisamm.fsutil import backup_path
    backup_path(profile.metadata_path).write_text("also broken")
    recovered = SaveProfile("Test", live, store)
    assert slot in recovered.slots
    assert len(recovered.slots[slot].backups) == 1


def test_migrates_legacy_manager_data(live, store):
    write_save(live, b"legacy")
    legacy = live / "_manager_data"
    (legacy / "slots" / "abc").mkdir(parents=True)
    with zipfile.ZipFile(legacy / "slots" / "abc" / "active_save.zip", "w") as zf:
        zf.writestr("gamedata.bin", b"legacy")
    with zipfile.ZipFile(legacy / "slots" / "abc" / "b1.zip", "w") as zf:
        zf.writestr("gamedata.bin", b"legacy backup")
    (legacy / "metadata.json").write_text(json.dumps({
        "active_slot_uuid": "abc",
        "slots": {"abc": {"name": "Old Slot", "backup_counter": 2, "backups": {
            "b1": {"name": "Backup - 0001", "timestamp": 1700000000}}}},
    }))
    profile = SaveProfile("Test", live, store)
    assert not legacy.exists()
    assert profile.active_slot_id == "abc"
    assert profile.slots["abc"].name == "Old Slot"
    write_save(live, b"changed")
    profile.restore_backup("abc", "b1")
    assert read_save(live) == b"legacy backup"


def test_discover_save_locations(tmp_path):
    steam = tmp_path / "Steam"
    (steam / "userdata" / "111").mkdir(parents=True)
    locations = discover_save_locations(tmp_path / "game", steam)
    assert locations["Steam"] == steam / "userdata" / "111" / "2993780" / "remote"
    assert "TENOKE" in locations
