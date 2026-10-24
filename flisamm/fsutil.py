"""
Small filesystem helpers that make writes crash-safe.

Every file is written to a temporary name first and then swapped into place
with os.replace, so a crash or power loss never leaves a half-written file.
"""

import hashlib
import json
import logging
import os
import shutil
from contextlib import contextmanager
from pathlib import Path

log = logging.getLogger(__name__)


class CorruptFileError(Exception):
    """Raised when a JSON file and its backup copy both fail to load."""


def backup_path(path):
    """Returns the path of the backup copy kept next to a JSON file."""
    path = Path(path)
    return path.with_name(path.name + ".bak")


@contextmanager
def atomic_output(path):
    """Yields a temporary path to write to; moves it over `path` on success."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        yield tmp
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def atomic_write_json(path, data):
    """Writes JSON atomically, keeping the previous version as a .bak file."""
    path = Path(path)
    with atomic_output(path) as tmp:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        if path.exists():
            shutil.copy2(path, backup_path(path))


def load_json(path):
    """Loads a JSON file, falling back to its .bak copy if it is unreadable.

    Returns None when neither file exists and raises CorruptFileError when
    files exist but none can be parsed, so callers never mistake a damaged
    file for an empty one.
    """
    path = Path(path)
    errors = []
    for candidate in (path, backup_path(path)):
        if not candidate.exists():
            continue
        try:
            with open(candidate, "r", encoding="utf-8") as f:
                data = json.load(f)
            if candidate != path:
                log.warning("Loaded %s from its backup copy.", path)
            return data
        except (OSError, ValueError) as e:
            log.warning("Could not read %s: %s", candidate, e)
            errors.append(f"{candidate.name}: {e}")
    if errors:
        raise CorruptFileError(f"Could not read {path}: " + "; ".join(errors))
    return None


def move(src, dst):
    """Moves a file, atomically when source and destination share a drive."""
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    try:
        os.replace(src, dst)
    except OSError:
        # Different drives: fall back to copy + delete.
        shutil.move(str(src), str(dst))


def link_or_copy(src, dst):
    """Hard-links src to dst, copying instead when linking is not possible."""
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def same_file(a, b):
    """True if `a` is a hard link to `b` or an unchanged copy of it."""
    try:
        if os.path.samefile(a, b):
            return True
        sa, sb = os.stat(a), os.stat(b)
    except OSError:
        return False
    # copy2 preserves timestamps, so an untouched copy matches size and mtime.
    return sa.st_size == sb.st_size and abs(sa.st_mtime - sb.st_mtime) < 2


def file_sha256(path):
    """Returns the SHA-256 hex digest of a file."""
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_relpath(name):
    """Normalizes an archive member name to a safe relative POSIX path.

    Returns None for names that are absolute, contain '..', or include a drive
    or stream separator, so extraction can never escape its target folder.
    """
    parts = [p for p in name.replace("\\", "/").split("/") if p not in ("", ".")]
    if not parts or any(p == ".." or ":" in p for p in parts):
        return None
    if name.startswith(("/", "\\")):
        return None
    return "/".join(parts)
