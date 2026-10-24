"""
Save profile management: slots, manual backups, and swapping the live save
files the game reads.

Each save location (Steam account, emulator folder, ...) is a profile. The
manager's own data for a profile lives in the app data folder, never next to
the game's saves, so Steam Cloud does not see or sync it.

Every operation that overwrites or deletes the live save first writes a
safety snapshot, and swaps are done with renames that are rolled back if
anything fails.
"""

import copy
import logging
import os
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .constants import STEAM_APP_ID, TENOKE_SAVE_REL
from .fsutil import CorruptFileError, atomic_output, atomic_write_json, load_json
from .paths import path_key
from .steam import steam_save_folders

log = logging.getLogger(__name__)

SCHEMA_VERSION = 2
SAVE_FILE_SUFFIXES = ("gamedata.bin", ".binbak")
SAFETY_SNAPSHOT_LIMIT = 10
LEGACY_DIR_NAME = "_manager_data"
ACTIVE_SAVE_NAME = "active_save.zip"


class SaveError(Exception):
    """Raised when a save operation cannot be completed."""


def is_save_file(name):
    """True for the files that make up a game save."""
    return name.lower().endswith(SAVE_FILE_SUFFIXES)


def new_id():
    return os.urandom(8).hex()


@dataclass
class Backup:
    name: str
    timestamp: float


@dataclass
class Slot:
    name: str
    backup_counter: int = 1
    active_save_timestamp: float | None = None
    backups: dict = field(default_factory=dict)

    def to_dict(self):
        return {
            "name": self.name,
            "backup_counter": self.backup_counter,
            "active_save_timestamp": self.active_save_timestamp,
            "backups": {bid: {"name": b.name, "timestamp": b.timestamp} for bid, b in self.backups.items()},
        }

    @classmethod
    def from_dict(cls, data):
        backups = {
            bid: Backup(name=str(b.get("name") or "Backup"), timestamp=float(b.get("timestamp") or 0))
            for bid, b in (data.get("backups") or {}).items()
        }
        return cls(
            name=str(data.get("name") or "Unnamed"),
            backup_counter=int(data.get("backup_counter") or 1),
            active_save_timestamp=data.get("active_save_timestamp"),
            backups=backups,
        )


def discover_save_locations(game_path=None, steam_path=None):
    """Returns {display name: save folder} for every known save location."""
    locations = {}
    steam_folders = steam_save_folders(steam_path)
    if len(steam_folders) == 1:
        locations["Steam"] = next(iter(steam_folders.values()))
    else:
        for steam_id, folder in steam_folders.items():
            locations[f"Steam ({steam_id})"] = folder

    appdata = Path(os.environ.get("APPDATA", ""))
    public_docs = Path(os.path.expandvars(r"%PUBLIC%\Documents"))
    locations["Online-Fix"] = public_docs / "OnlineFix" / STEAM_APP_ID / "Saves"
    locations["GBE_Fork"] = appdata / "GSE Saves" / STEAM_APP_ID / "remote"
    locations["Goldberg"] = appdata / "Goldberg SteamEmu Saves" / STEAM_APP_ID / "remote"
    locations["RUNE"] = public_docs / "RUNE" / STEAM_APP_ID / "Saves"
    if game_path:
        locations["TENOKE"] = Path(game_path) / TENOKE_SAVE_REL
    return locations


class SaveProfile:
    """Manages the slots, backups and live save files of one save location."""

    def __init__(self, name, live_path, store_root):
        self.name = name
        self.live_path = Path(live_path)
        self.store_path = Path(store_root) / path_key(live_path)
        self.slots_path = self.store_path / "slots"
        self.safety_path = self.store_path / "safety"
        self.metadata_path = self.store_path / "metadata.json"
        self.active_slot_id = None
        self.slots = {}
        self._migrate_legacy()
        self._load()

    # --- Persistence ---

    def _load(self):
        try:
            data = load_json(self.metadata_path)
        except CorruptFileError as e:
            log.error("%s", e)
            data = self._recover_metadata()
        if data:
            self._apply(data)

    def _apply(self, data):
        # Version 1 (pre-1.0) used "active_slot_uuid"; the slot layout is unchanged.
        self.active_slot_id = data.get("active_slot_id", data.get("active_slot_uuid"))
        self.slots = {sid: Slot.from_dict(s) for sid, s in (data.get("slots") or {}).items()}
        if self.active_slot_id not in self.slots:
            self.active_slot_id = None

    def save(self):
        """Writes this profile's metadata to disk."""
        atomic_write_json(self.metadata_path, {
            "schema_version": SCHEMA_VERSION,
            "source_path": str(self.live_path),
            "active_slot_id": self.active_slot_id,
            "slots": {sid: s.to_dict() for sid, s in self.slots.items()},
        })

    def _recover_metadata(self):
        """Rebuilds metadata from the snapshot files when the JSON is unreadable."""
        slots = {}
        if self.slots_path.is_dir():
            for slot_dir in sorted(self.slots_path.iterdir()):
                if not slot_dir.is_dir():
                    continue
                slot = Slot(name=f"Recovered {slot_dir.name[:6]}")
                active = slot_dir / ACTIVE_SAVE_NAME
                if active.exists():
                    slot.active_save_timestamp = active.stat().st_mtime
                for i, backup in enumerate(sorted(slot_dir.glob("*.zip"), key=lambda p: p.stat().st_mtime), 1):
                    if backup.name != ACTIVE_SAVE_NAME:
                        slot.backups[backup.stem] = Backup(f"Recovered Backup {i:04d}", backup.stat().st_mtime)
                slot.backup_counter = len(slot.backups) + 1
                slots[slot_dir.name] = slot.to_dict()
        log.warning("Recovered %d slot(s) for %s from disk.", len(slots), self.live_path)
        data = {"active_slot_id": None, "slots": slots}
        self._apply(data)
        self.save()
        return data

    def _migrate_legacy(self):
        """Moves pre-1.0 manager data out of the game's save folder."""
        legacy = self.live_path / LEGACY_DIR_NAME
        if not legacy.is_dir():
            return
        log.info("Migrating legacy save data from %s", legacy)
        self.store_path.mkdir(parents=True, exist_ok=True)
        legacy_slots = legacy / "slots"
        if legacy_slots.is_dir():
            self.slots_path.mkdir(parents=True, exist_ok=True)
            for slot_dir in legacy_slots.iterdir():
                target = self.slots_path / slot_dir.name
                if not target.exists():
                    shutil.move(str(slot_dir), str(target))
        if not self.metadata_path.exists():
            try:
                data = load_json(legacy / "metadata.json")
            except CorruptFileError as e:
                log.error("%s", e)
                data = None
            if data:
                self._apply(data)
                self.save()
        archive = self.store_path / f"legacy_import_{datetime.now():%Y%m%d-%H%M%S}"
        shutil.move(str(legacy), str(archive))

    # --- Live save files ---

    def live_save_files(self):
        """Returns the game's current save files in this location."""
        if not self.live_path.is_dir():
            return []
        return [p for p in self.live_path.iterdir() if p.is_file() and is_save_file(p.name)]

    def has_live_save(self):
        return bool(self.live_save_files())

    def is_slot_loaded(self, slot_id):
        """True if the slot's save is the one the game will use."""
        return slot_id is not None and slot_id == self.active_slot_id and self.has_live_save()

    def slot_dir(self, slot_id):
        return self.slots_path / slot_id

    def _write_snapshot(self, dest):
        files = self.live_save_files()
        if not files:
            return False
        with atomic_output(dest) as tmp:
            with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
                for f in files:
                    zf.write(f, arcname=f.name)
        return True

    @staticmethod
    def _extract_snapshot(snapshot, dest_dir):
        with zipfile.ZipFile(snapshot, "r") as zf:
            for info in zf.infolist():
                name = Path(info.filename.replace("\\", "/")).name
                if info.is_dir() or not is_save_file(name):
                    continue
                target = Path(dest_dir) / name
                with zf.open(info) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                # Keep the original save time so "Last Played" stays accurate.
                saved_at = datetime(*info.date_time).timestamp()
                os.utime(target, (saved_at, saved_at))

    def _replace_live_files(self, snapshot):
        """Swaps the live save for a snapshot's contents (or nothing).

        New files are extracted before anything is touched, and the old files
        are moved aside rather than deleted, so a failure part-way through
        puts everything back the way it was.
        """
        self.live_path.mkdir(parents=True, exist_ok=True)
        incoming = Path(tempfile.mkdtemp(prefix=".flisamm-in-", dir=self.live_path))
        outgoing = Path(tempfile.mkdtemp(prefix=".flisamm-out-", dir=self.live_path))
        try:
            if snapshot is not None:
                self._extract_snapshot(snapshot, incoming)
            moved_out, moved_in = [], []
            try:
                for f in self.live_save_files():
                    os.replace(f, outgoing / f.name)
                    moved_out.append(f.name)
                for f in incoming.iterdir():
                    os.replace(f, self.live_path / f.name)
                    moved_in.append(f.name)
            except OSError as e:
                for name in moved_in:
                    (self.live_path / name).unlink(missing_ok=True)
                for name in moved_out:
                    os.replace(outgoing / name, self.live_path / name)
                raise SaveError(f"Could not replace the save files (is the game running?): {e}") from e
        except (OSError, zipfile.BadZipFile) as e:
            raise SaveError(f"Could not read the saved snapshot: {e}") from e
        finally:
            shutil.rmtree(incoming, ignore_errors=True)
            shutil.rmtree(outgoing, ignore_errors=True)

    def _safety_snapshot(self, reason):
        """Keeps a copy of the live save before it is overwritten or deleted."""
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        if not self._write_snapshot(self.safety_path / f"{stamp}_{reason}.zip"):
            return
        snapshots = sorted(self.safety_path.glob("*.zip"))
        for old in snapshots[:-SAFETY_SNAPSHOT_LIMIT]:
            old.unlink(missing_ok=True)

    # --- Slots ---

    def create_slot(self, name):
        """Creates an empty slot and returns its id."""
        slot_id = new_id()
        self.slots[slot_id] = Slot(name=name)
        self.slot_dir(slot_id).mkdir(parents=True, exist_ok=True)
        self.save()
        return slot_id

    def rename_slot(self, slot_id, name):
        self.slots[slot_id].name = name
        self.save()

    def initialize_from_live_save(self, name):
        """Adopts an existing game save into a new slot."""
        if self.active_slot_id or not self.has_live_save():
            return None
        slot_id = self.create_slot(name)
        self.active_slot_id = slot_id
        self.sync_active_slot()
        return slot_id

    def sync_active_slot(self):
        """Copies the live save into the loaded slot's Active Save."""
        slot_id = self.active_slot_id
        if not slot_id or slot_id not in self.slots:
            return False
        if not self._write_snapshot(self.slot_dir(slot_id) / ACTIVE_SAVE_NAME):
            return False
        last_played = max(f.stat().st_mtime for f in self.live_save_files())
        self.slots[slot_id].active_save_timestamp = last_played
        self.save()
        return True

    def load_slot(self, slot_id):
        """Makes a slot's Active Save the live save.

        Returns False when the slot is empty, in which case the live save is
        cleared so the game starts a new one for this slot.
        """
        if slot_id not in self.slots:
            raise SaveError("That slot no longer exists.")
        if self.is_slot_loaded(slot_id):
            return True
        self.sync_active_slot()
        self._safety_snapshot("load-slot")
        active_save = self.slot_dir(slot_id) / ACTIVE_SAVE_NAME
        has_save = active_save.exists()
        self._replace_live_files(active_save if has_save else None)
        self.active_slot_id = slot_id
        if not has_save:
            self.slots[slot_id].active_save_timestamp = None
        self.save()
        return has_save

    def delete_slot(self, slot_id):
        """Deletes a slot and its backups; clears the live save if it was loaded."""
        if slot_id == self.active_slot_id:
            self._safety_snapshot("delete-slot")
            self._replace_live_files(None)
            self.active_slot_id = None
        shutil.rmtree(self.slot_dir(slot_id), ignore_errors=True)
        del self.slots[slot_id]
        self.save()

    def copy_slot_to(self, dest, slot_id):
        """Copies a slot, its Active Save and its backups to another profile."""
        if dest.active_slot_id == slot_id:
            raise SaveError(
                f"This slot is currently loaded in '{dest.name}'. "
                "Load a different slot there before replacing it.")
        if slot_id == self.active_slot_id:
            self.sync_active_slot()
        dest.slots_path.mkdir(parents=True, exist_ok=True)
        target = dest.slot_dir(slot_id)
        tmp = dest.slots_path / f".{slot_id}.tmp"
        shutil.rmtree(tmp, ignore_errors=True)
        source = self.slot_dir(slot_id)
        if source.is_dir():
            shutil.copytree(source, tmp)
        else:
            tmp.mkdir()
        shutil.rmtree(target, ignore_errors=True)
        os.replace(tmp, target)
        dest.slots[slot_id] = copy.deepcopy(self.slots[slot_id])
        dest.save()

    # --- Backups ---

    def create_backup(self, slot_id, name=None):
        """Snapshots the live save as a manual backup of the loaded slot."""
        if not self.is_slot_loaded(slot_id):
            raise SaveError("Backups can only be made of the loaded slot.")
        slot = self.slots[slot_id]
        backup_id = new_id()
        if not self._write_snapshot(self.slot_dir(slot_id) / f"{backup_id}.zip"):
            raise SaveError("There is no save file to back up.")
        slot.backups[backup_id] = Backup(
            name=name or f"Backup - {slot.backup_counter:04d}",
            timestamp=datetime.now().timestamp())
        slot.backup_counter += 1
        self.save()
        return backup_id

    def rename_backup(self, slot_id, backup_id, name):
        self.slots[slot_id].backups[backup_id].name = name
        self.save()

    def delete_backup(self, slot_id, backup_id):
        (self.slot_dir(slot_id) / f"{backup_id}.zip").unlink(missing_ok=True)
        del self.slots[slot_id].backups[backup_id]
        self.save()

    def restore_backup(self, slot_id, backup_id):
        """Loads a backup as the live save, making its slot the loaded slot."""
        backup_zip = self.slot_dir(slot_id) / f"{backup_id}.zip"
        if not backup_zip.exists():
            raise SaveError("The backup file is missing.")
        self.sync_active_slot()
        self._safety_snapshot("restore-backup")
        self._replace_live_files(backup_zip)
        self.active_slot_id = slot_id
        self.sync_active_slot()
