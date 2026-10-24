"""
Mod installation and deployment.

Installed mods are kept untouched in a staging folder and deployed into the
game folder as hard links (or copies when the game is on another drive).
Before a mod file replaces one of the game's own files, the original is
backed up, and it is put back when the mod is disabled or deleted.

When several enabled mods provide the same file, the one later in the load
order wins.
"""

import logging
import os
import shutil
import tempfile
import time
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .constants import MODS_DIR_REL
from .fsutil import (
    CorruptFileError, atomic_write_json, link_or_copy, load_json, move,
    safe_relpath, same_file
)
from .paths import path_key

log = logging.getLogger(__name__)

SCHEMA_VERSION = 2
PAK_EXTENSIONS = {".pak", ".utoc", ".ucas", ".sig"}
DOC_EXTENSIONS = {
    ".txt", ".md", ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp",
    ".url", ".html", ".htm", ".rtf", ".nfo",
}
ARCHIVE_EXTENSIONS = {".zip", ".7z"}
INSTALLABLE_EXTENSIONS = ARCHIVE_EXTENSIONS | PAK_EXTENSIONS
LEGACY_DIR_NAME = "_manager_data"
DISABLED_SUFFIX = ".disabled"


class ModError(Exception):
    """Raised when a mod operation fails."""


def _key(rel):
    """Case-insensitive identity of a game-relative path (Windows semantics)."""
    return rel.replace("\\", "/").lower()


@dataclass
class Mod:
    id: str
    name: str
    files: list
    enabled: bool = True
    installed_at: float = field(default_factory=time.time)
    source: str = ""


@dataclass
class PendingInstall:
    """A mod that has been unpacked and checked but not yet installed."""
    name: str
    source: str
    work_dir: Path
    files: dict           # game-relative target path -> unpacked file
    skipped: list         # archive entries that will not be installed
    warnings: list        # things the user should confirm before installing

    def cleanup(self):
        shutil.rmtree(self.work_dir, ignore_errors=True)


@dataclass
class DetectedMod:
    """A mod found in the game folder that FLiSaMM isn't managing."""
    name: str
    files: list           # game-relative paths as found (may end in .disabled)
    enabled: bool


def plan_layout(rel_paths, game_path):
    """Decides where each file in a mod archive goes inside the game folder.

    - Wrapper folders around the real content are stripped.
    - Paths that start with a folder the game has (e.g. "Game/") are kept.
    - Loose .pak/.utoc/.ucas files go to Game/Content/Paks/~mods.
    - Readmes and images are skipped.

    Returns (mapping of source path -> target path, skipped paths, warnings).
    """
    game_path = Path(game_path)
    game_dirs = {p.name.lower() for p in game_path.iterdir() if p.is_dir()} if game_path.is_dir() else set()
    split = {rel: rel.split("/") for rel in rel_paths}

    # Strip a shared top-level folder (e.g. "MyMod/") unless it's a game folder.
    depth = 0
    while True:
        heads = {parts[depth] for parts in split.values() if len(parts) > depth + 1}
        if (len(heads) != 1 or any(len(parts) <= depth + 1 for parts in split.values())
                or next(iter(heads)).lower() in game_dirs):
            break
        depth += 1

    mapping, skipped, warnings, missing_dirs = {}, [], [], set()
    for rel, parts in split.items():
        parts = parts[depth:]
        ext = os.path.splitext(parts[-1])[1].lower()
        if len(parts) > 1 and parts[0].lower() in game_dirs:
            target = "/".join(parts)
            if not _key(target).startswith(_key(MODS_DIR_REL)):
                parent = game_path.joinpath(*parts[:-1])
                if not parent.is_dir():
                    missing_dirs.add("/".join(parts[:-1]))
        elif ext in PAK_EXTENSIONS:
            target = f"{MODS_DIR_REL}/{parts[-1]}"
        elif ext in DOC_EXTENSIONS:
            skipped.append(rel)
            continue
        else:
            target = "/".join(parts)
            if len(parts) > 1 and not game_path.joinpath(*parts[:-1]).is_dir():
                missing_dirs.add("/".join(parts[:-1]))
        if any(_key(t) == _key(target) for t in mapping.values()):
            warnings.append(f"Two files in the archive both go to '{target}'; only the first is used.")
            continue
        mapping[rel] = target

    for d in sorted(missing_dirs)[:5]:
        warnings.append(f"Creates a new folder '{d}' in the game directory (possible packaging error).")
    if not mapping:
        warnings.append("The archive contains no files that can be installed.")
    return mapping, skipped, warnings


def _extract_zip(src, dest):
    skipped = []
    with zipfile.ZipFile(src) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            rel = safe_relpath(info.filename)
            if rel is None:
                skipped.append(info.filename)
                continue
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as s, open(target, "wb") as d:
                shutil.copyfileobj(s, d)
    return skipped


def _extract_7z(src, dest):
    try:
        import py7zr
    except ImportError as e:
        raise ModError("7z support needs the 'py7zr' package (pip install py7zr).") from e
    with py7zr.SevenZipFile(src, "r") as archive:
        archive.extractall(path=dest)
    return []


def _walk_files(root):
    return sorted(
        p.relative_to(root).as_posix() for p in root.rglob("*")
        if p.is_file() and not p.is_symlink())


class ModManager:
    """Tracks installed mods for one game folder and keeps them deployed."""

    def __init__(self, game_path, store_root):
        self.game_path = Path(game_path)
        self.store_path = Path(store_root) / path_key(game_path)
        self.staging_path = self.store_path / "mods"
        self.vanilla_path = self.store_path / "vanilla"
        self.manifest_path = self.store_path / "mods.json"
        self.mods = []          # Load order: later entries win conflicts.
        self.deployed = {}      # path key -> [mod id, game-relative path]
        self._load()
        self._migrate_legacy()

    # --- Persistence ---

    def _load(self):
        try:
            data = load_json(self.manifest_path)
        except CorruptFileError as e:
            raise ModError(f"The mod list could not be read: {e}") from e
        if not data:
            return
        self.mods = [Mod(**m) for m in data.get("mods", [])]
        self.deployed = {k: list(v) for k, v in data.get("deployed", {}).items()}

    def _save(self):
        atomic_write_json(self.manifest_path, {
            "schema_version": SCHEMA_VERSION,
            "game_path": str(self.game_path),
            "mods": [asdict(m) for m in self.mods],
            "deployed": self.deployed,
        })

    def _migrate_legacy(self):
        """Imports mods installed by pre-1.0 versions straight into the game folder."""
        legacy_dir = self.game_path / LEGACY_DIR_NAME
        legacy_manifest = legacy_dir / "mods.json"
        if not legacy_manifest.exists():
            return
        try:
            entries = load_json(legacy_manifest) or []
        except CorruptFileError as e:
            log.error("%s", e)
            entries = []
        names = {m.name.lower() for m in self.mods}
        for entry in entries:
            if entry.get("name", "").lower() in names:
                continue
            mod = Mod(id=os.urandom(8).hex(), name=entry["name"], files=[],
                      enabled=entry.get("status") == "enabled", source="Imported from FLiSaMM 0.9")
            for raw in entry.get("files", []):
                rel = safe_relpath(raw)
                if rel is None:
                    continue
                for candidate in (self.game_path / rel, self.game_path / (rel + ".disabled")):
                    if candidate.exists():
                        move(candidate, self.staging_path / mod.id / rel)
                        mod.files.append(rel)
                        break
            self.mods.append(mod)
            log.info("Imported legacy mod '%s' (%d files)", mod.name, len(mod.files))
        self._save()
        move(legacy_dir, self.store_path / "legacy_import")
        try:
            self.sync()
        except ModError as e:
            log.warning("Could not deploy imported mods yet: %s", e)

    # --- Queries ---

    def get(self, mod_id):
        for mod in self.mods:
            if mod.id == mod_id:
                return mod
        raise ModError("That mod is no longer installed.")

    def find_by_name(self, name):
        return next((m for m in self.mods if m.name.lower() == name.lower()), None)

    def conflicts(self):
        """Returns {mod id: (names it overrides, names that override it)} for enabled mods."""
        owners = {}
        for mod in self.mods:
            if mod.enabled:
                for rel in mod.files:
                    owners.setdefault(_key(rel), []).append(mod)
        result = {m.id: (set(), set()) for m in self.mods}
        for mods in owners.values():
            for i, mod in enumerate(mods):
                result[mod.id][0].update(m.name for m in mods[:i])
                result[mod.id][1].update(m.name for m in mods[i + 1:])
        return result

    # --- Mods installed outside FLiSaMM ---

    def detect_unmanaged(self):
        """Finds pak mods in ~mods that were installed by hand or by another tool.

        Files in a subfolder of ~mods form one mod; loose files are grouped by
        name, so a .pak with its .utoc/.ucas counts as one mod. Files renamed
        to *.disabled (how FLiSaMM 0.9 disabled mods) are found too.
        """
        mods_dir = self.game_path / MODS_DIR_REL
        if not mods_dir.is_dir():
            return []
        groups = {}
        for path in sorted(mods_dir.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(self.game_path).as_posix()
            disabled = rel.lower().endswith(DISABLED_SUFFIX)
            real_rel = rel[:-len(DISABLED_SUFFIX)] if disabled else rel
            stem, ext = os.path.splitext(real_rel.rsplit("/", 1)[-1])
            if ext.lower() not in PAK_EXTENSIONS or _key(real_rel) in self.deployed:
                continue
            subfolder = path.parent.relative_to(mods_dir).parts
            name = subfolder[0] if subfolder else stem
            group = groups.setdefault(name.lower(), DetectedMod(name, [], False))
            group.files.append(rel)
            group.enabled = group.enabled or not disabled
        return list(groups.values())

    def adopt(self, detected):
        """Takes over detected mods so they can be toggled, ordered and deleted."""
        adopted = []
        for found in detected:
            name, n = found.name, 2
            while self.find_by_name(name):
                name, n = f"{found.name} ({n})", n + 1
            mod = Mod(id=os.urandom(8).hex(), name=name, files=[], enabled=found.enabled,
                      source="Found in the game folder")
            moved = []
            try:
                for rel in found.files:
                    target = rel[:-len(DISABLED_SUFFIX)] if rel.lower().endswith(DISABLED_SUFFIX) else rel
                    if any(_key(f) == _key(target) for f in mod.files):
                        continue
                    move(self.game_path / rel, self.staging_path / mod.id / target)
                    moved.append((rel, target))
                    mod.files.append(target)
            except OSError as e:
                for rel, target in moved:
                    move(self.staging_path / mod.id / target, self.game_path / rel)
                shutil.rmtree(self.staging_path / mod.id, ignore_errors=True)
                self._save()
                if adopted:
                    self.sync()
                raise ModError(f"Could not import '{found.name}' (is the game running?): {e}") from e
            if mod.files:
                self.mods.append(mod)
                adopted.append(mod)
        self._save()
        self.sync()
        return adopted

    # --- Installing ---

    def stage(self, sources):
        """Unpacks an archive (or a group of loose .pak files) for inspection.

        Call commit() to install the result, or cleanup() on it to cancel.
        """
        sources = [Path(s) for s in sources]
        if not sources:
            raise ModError("Nothing to install.")
        tmp_root = self.store_path / "tmp"
        tmp_root.mkdir(parents=True, exist_ok=True)
        work_dir = Path(tempfile.mkdtemp(dir=tmp_root))
        raw = work_dir / "raw"
        raw.mkdir()
        try:
            unsafe = []
            first = sources[0]
            ext = first.suffix.lower()
            if len(sources) == 1 and ext == ".zip":
                unsafe = _extract_zip(first, raw)
            elif len(sources) == 1 and ext == ".7z":
                unsafe = _extract_7z(first, raw)
            elif all(s.suffix.lower() in PAK_EXTENSIONS for s in sources):
                for s in sources:
                    shutil.copy2(s, raw / s.name)
            else:
                raise ModError(f"Unsupported file type: {first.name}")
            mapping, skipped, warnings = plan_layout(_walk_files(raw), self.game_path)
        except Exception as e:
            shutil.rmtree(work_dir, ignore_errors=True)
            if isinstance(e, ModError):
                raise
            # zipfile/py7zr raise a variety of exception types for bad archives.
            raise ModError(f"Could not read '{first.name}': {e}") from e

        if unsafe:
            warnings.insert(0, f"{len(unsafe)} file(s) with unsafe paths were ignored.")
        return PendingInstall(
            name=first.stem, source=", ".join(s.name for s in sources), work_dir=work_dir,
            files={target: raw / rel for rel, target in mapping.items()},
            skipped=skipped + unsafe, warnings=warnings)

    def commit(self, pending, replace=False):
        """Installs a staged mod and deploys it. Replaces a same-named mod if asked."""
        existing = self.find_by_name(pending.name)
        if existing and not replace:
            raise ModError(f"A mod named '{pending.name}' is already installed.")
        if not pending.files:
            raise ModError("The archive contains no files that can be installed.")
        mod = Mod(id=os.urandom(8).hex(), name=pending.name, files=sorted(pending.files),
                  source=pending.source)
        try:
            for target, src in pending.files.items():
                move(src, self.staging_path / mod.id / target)
        finally:
            pending.cleanup()

        if existing:
            mod.enabled = existing.enabled
            self.mods[self.mods.index(existing)] = mod
        else:
            self.mods.append(mod)
        try:
            self.sync()
        finally:
            if existing:
                still_used = any(owner == existing.id for owner, _ in self.deployed.values())
                if not still_used:
                    shutil.rmtree(self.staging_path / existing.id, ignore_errors=True)
            self._save()
        return mod

    # --- Managing ---

    def set_enabled(self, mod_id, enabled):
        self.get(mod_id).enabled = enabled
        self.sync()

    def disable_all(self):
        for mod in self.mods:
            mod.enabled = False
        self.sync()

    def move(self, mod_id, offset):
        """Moves a mod earlier (-1) or later (+1) in the load order."""
        mod = self.get(mod_id)
        index = self.mods.index(mod)
        new_index = max(0, min(len(self.mods) - 1, index + offset))
        if new_index == index:
            return
        self.mods.insert(new_index, self.mods.pop(index))
        self.sync()

    def delete(self, mod_id):
        """Removes a mod's files from the game, restores originals and forgets it."""
        mod = self.get(mod_id)
        index = self.mods.index(mod)
        self.mods.remove(mod)
        try:
            self.sync()
        except ModError:
            # Keep the mod (disabled) so its remaining files are still tracked.
            mod.enabled = False
            self.mods.insert(index, mod)
            self._save()
            raise
        shutil.rmtree(self.staging_path / mod.id, ignore_errors=True)
        self._save()

    # --- Deployment ---

    def sync(self):
        """Makes the game folder match the enabled mods and their load order."""
        desired = {}
        for mod in self.mods:
            if mod.enabled:
                for rel in mod.files:
                    desired[_key(rel)] = (mod, rel)

        errors = []
        for key, (owner_id, rel) in list(self.deployed.items()):
            want = desired.get(key)
            if want and want[0].id == owner_id and self._is_ours(owner_id, rel):
                continue
            try:
                self._undeploy(key, owner_id, rel)
            except OSError as e:
                errors.append(f"{rel}: {e}")

        for key, (mod, rel) in desired.items():
            if key in self.deployed:
                continue
            try:
                self._deploy(key, mod, rel)
            except OSError as e:
                errors.append(f"{rel}: {e}")

        self._save()
        if errors:
            shown = "\n".join(errors[:5])
            more = f"\n...and {len(errors) - 5} more" if len(errors) > 5 else ""
            raise ModError(f"Some files could not be updated (is the game running?):\n{shown}{more}")

    def _is_ours(self, mod_id, rel):
        game_file = self.game_path / rel
        staged = self.staging_path / mod_id / rel
        return game_file.exists() and staged.exists() and same_file(game_file, staged)

    def _deploy(self, key, mod, rel):
        game_file = self.game_path / rel
        staged = self.staging_path / mod.id / rel
        if game_file.exists():
            # A file we did not put there: the game's own (or another tool's).
            move(game_file, self.vanilla_path / rel)
        link_or_copy(staged, game_file)
        self.deployed[key] = [mod.id, rel]

    def _undeploy(self, key, mod_id, rel):
        game_file = self.game_path / rel
        staged = self.staging_path / mod_id / rel
        original = self.vanilla_path / rel
        if game_file.exists():
            if not staged.exists() or same_file(game_file, staged):
                game_file.unlink()
            else:
                # Replaced since we deployed it (e.g. a game update). The new
                # file is now the original, so the old backup is obsolete.
                original.unlink(missing_ok=True)
        if original.exists():
            move(original, game_file)
        del self.deployed[key]
