"""Safe filesystem moves shared by the file-moving verbs.

The small, self-contained part of ansikten's ``core.fs_ops``: never overwrite,
move sidecars with their main file, and roll the whole unit back on failure.
There is deliberately no journal here — undo belongs to ansikten, not to bild.
"""

from __future__ import annotations

import os
import re
import uuid
from datetime import datetime
from pathlib import Path

# Canonical extension sets, copied from ansikten's core/files.py (29 lines).
RAW_EXTENSIONS = (".nef", ".cr2", ".cr3", ".arw", ".dng", ".raw", ".raf", ".orf", ".rw2")
JPEG_EXTENSIONS = (".jpg", ".jpeg")
STANDARD_EXTENSIONS = (".jpg", ".jpeg", ".tiff", ".tif", ".png")
SUPPORTED_EXTENSIONS = RAW_EXTENSIONS + STANDARD_EXTENSIONS

TIMESTAMP_PATTERN = re.compile(r"^(\d{6}_\d{6})")
DATE_PATTERN = re.compile(r"^(\d{6})")


def parse_date_arg(value: str) -> str:
    """Accept YYMMDD, YYYYMMDD, YYYY-MM-DD or YY-MM-DD; return YYMMDD."""
    value = value.strip()
    if re.fullmatch(r"\d{6}", value):
        return value
    if re.fullmatch(r"\d{8}", value):
        return value[2:]
    for fmt in ("%Y-%m-%d", "%y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).strftime("%y%m%d")
        except ValueError:
            continue
    raise ValueError(f"unknown date format: {value}")


def extract_date(filename: str) -> str | None:
    """Return the leading YYMMDD of a filename, if it parses as a date."""
    match = DATE_PATTERN.match(filename)
    if not match:
        return None
    token = match.group(1)
    try:
        datetime.strptime(token, "%y%m%d")
    except ValueError:
        return None
    return token


def extract_timestamp(filename: str) -> tuple[str, datetime] | None:
    """Return a leading YYMMDD_HHMMSS token and its naive local datetime."""
    match = TIMESTAMP_PATTERN.match(filename)
    if not match:
        return None
    token = match.group(1)
    try:
        return token, datetime.strptime(token, "%y%m%d_%H%M%S")
    except ValueError:
        return None


def iter_supported_images(root: Path, recursive: bool) -> list[Path]:
    """List supported images in deterministic order."""
    candidates = root.rglob("*") if recursive else root.iterdir()
    return sorted(
        path
        for path in candidates
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )


def find_sidecar_files(file: Path) -> list[Path]:
    """Find the .xmp sidecar for a file, if any (one on a case-insensitive FS)."""
    for sidecar in file.parent.glob(f"{file.stem}.[xX][mM][pP]"):
        if sidecar.exists() and sidecar != file:
            return [sidecar]
    return []


def claim_sidecars(path: Path, claimed: set[Path]) -> list[Path]:
    """Return only sidecars not yet claimed by another move in the same plan.

    A RAW/JPEG pair with a shared XMP must not move that sidecar twice: the
    second move would fail on an already occupied target, leaving a half-done
    plan. Claiming at plan time also keeps dry-run honest.
    """
    sidecars = [sc for sc in find_sidecar_files(path) if sc.resolve() not in claimed]
    claimed.update(sc.resolve() for sc in sidecars)
    return sidecars


def _is_case_only_same(a: Path, b: Path) -> bool:
    try:
        return a.exists() and a.samefile(b)
    except OSError:
        return False


def _safe_rename(src: Path, dst: Path) -> None:
    """Rename src to dst, handling a case-only rename on macOS."""
    if dst.exists() and dst.samefile(src):
        tmp = src.with_name(f".{uuid.uuid4().hex}.rename.tmp")
        src.rename(tmp)
        tmp.rename(dst)
    else:
        src.rename(dst)


def preflight_destinations(destinations: list[Path]) -> str | None:
    """Return a non-mutating error for a planned move unit, or None."""
    seen: set[str] = set()
    for destination in destinations:
        key = str(destination).casefold()
        if key in seen:
            return f"destination collision within the operation: {destination.name}"
        seen.add(key)
        if destination.exists() or destination.is_symlink():
            return f"destination already exists: {destination}"
        parent = destination.parent
        while (
            not parent.exists()
            and not parent.is_symlink()
            and parent != parent.parent
        ):
            parent = parent.parent
        if not parent.is_dir():
            return f"parent path blocked by a file: {parent}"
        if not os.access(parent, os.W_OK | os.X_OK):
            return f"parent directory not writable: {parent}"
    return None


def move_unit(
    main_src: Path,
    main_dst: Path,
    sidecar_pairs: list[tuple[Path, Path]] | None = None,
) -> list[tuple[Path, Path]]:
    """Move a main file and its sidecars as one all-or-nothing unit.

    Never overwrites an existing file or dangling symlink. On any failure the
    moves already completed are rolled back before the error is re-raised.
    Returns the pairs that were actually moved, main first.
    """
    pairs = sidecar_pairs or []
    all_dsts = [main_dst, *(dst for _src, dst in pairs)]
    seen: set[str] = set()
    for dst in all_dsts:
        key = str(dst).casefold()
        if key in seen:
            raise FileExistsError(f"destination collision within the unit: {dst.name}")
        seen.add(key)

    for src, dst in [(main_src, main_dst), *pairs]:
        if (dst.exists() or dst.is_symlink()) and not _is_case_only_same(dst, src):
            raise FileExistsError(f"destination already exists: {dst.name}")

    done: list[tuple[Path, Path]] = []
    try:
        _safe_rename(main_src, main_dst)
        done.append((main_src, main_dst))
        for sc_src, sc_dst in pairs:
            _safe_rename(sc_src, sc_dst)
            done.append((sc_src, sc_dst))
    except Exception:
        for moved_src, moved_dst in reversed(done):
            try:
                _safe_rename(moved_dst, moved_src)
            except OSError:
                pass
        raise
    return done
