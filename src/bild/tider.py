"""Adjust photo timestamps: EXIF dates and the time in file names.

Ported from `fixa_fototider.zsh`. Both the EXIF dates and the file names change,
so a preview is printed before anything is written and `-n` shows it only.
"""

from __future__ import annotations

import re
import subprocess
from glob import glob
from pathlib import Path

from .exiftool import find_exiftool
from .moves import move_unit

OFFSET_PATTERN = re.compile(r"^([+-])(\d{2}):(\d{2}):(\d{2})$")
NAME_PATTERN = re.compile(r"^(\d{6})_(\d{6})(.*)\.([^.]+)$")
EXIF_SUFFIXES = {".nef", ".jpg", ".jpeg"}
ALL_SUFFIXES = EXIF_SUFFIXES | {".xmp"}


def parse_offset(value: str) -> tuple[int, str, str]:
    """Return (seconds, exiftool sign, HH:MM:SS)."""
    match = OFFSET_PATTERN.match(value)
    if not match:
        raise ValueError(f"bad time offset: {value} (expected ±HH:MM:SS, e.g. -01:01:00)")
    sign, hours, minutes, seconds = match.groups()
    total = int(hours) * 3600 + int(minutes) * 60 + int(seconds)
    return (total if sign == "+" else -total), sign, f"{hours}:{minutes}:{seconds}"


def shifted_name(name: str, seconds: int) -> str | None:
    """Return the name with its YYMMDD_HHMMSS time shifted, or None."""
    match = NAME_PATTERN.match(name)
    if not match:
        return None
    date, clock, suffix, extension = match.groups()
    old = int(clock[0:2]) * 3600 + int(clock[2:4]) * 60 + int(clock[4:6])
    new = (old + seconds) % 86400
    shifted = f"{new // 3600:02d}{(new % 3600) // 60:02d}{new % 60:02d}"
    if shifted == clock:
        return None
    return f"{date}_{shifted}{suffix}.{extension}"


def resolve_files(pattern: str) -> list[Path]:
    """Expand a glob pattern and keep only photo/sidecar extensions."""
    return sorted(
        path
        for path in (Path(match) for match in glob(pattern))
        if path.is_file() and path.suffix.lower() in ALL_SUFFIXES
    )


def run_tider(pattern: str, offset: str, *, dry_run: bool) -> int:
    """Shift EXIF dates and file-name times for all files matching pattern."""
    try:
        seconds, sign, exif_offset = parse_offset(offset)
    except ValueError as error:
        print(f"FEL: {error}")
        return 2

    files = resolve_files(pattern)
    if not files:
        print(f"No files match {pattern!r}.")
        return 1
    exif_files = [path for path in files if path.suffix.lower() in EXIF_SUFFIXES]
    renames = [
        (path, path.with_name(shifted))
        for path in files
        if (shifted := shifted_name(path.name, seconds)) is not None
    ]
    print(
        f"Offset {offset} ({seconds} s): {len(files)} files, "
        f"{len(exif_files)} EXIF updates, {len(renames)} renames."
    )
    for source, target in renames:
        print(f"  {source.name} -> {target.name}")

    if dry_run:
        print("(dry) nothing changed")
        return 0

    if exif_files:
        try:
            command = [
                find_exiftool(),
                f"-AllDates{sign}={exif_offset}",
                "-overwrite_original",
                *[str(path) for path in exif_files],
            ]
            subprocess.run(command, check=False)
        except FileNotFoundError as error:
            print(f"FEL: {error}")
            return 1

    failed = 0
    for source, target in renames:
        try:
            move_unit(source, target)
        except OSError as error:
            failed += 1
            print(f"FEL: {source.name}: {error}")
    return 1 if failed else 0
