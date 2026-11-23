"""Adjust photo timestamps: EXIF dates and the time in file names.

Ported from `fixa_fototider.zsh`. Both the EXIF dates and the file names change,
so a preview is printed before anything is written and `-n` shows it only.
XMP sidecars follow their main image even if the pattern did not match them.
"""

from __future__ import annotations

import re
import subprocess
import sys
from glob import glob
from pathlib import Path

from .exiftool import find_exiftool
from .moves import claim_sidecars, move_unit, order_moves

OFFSET_PATTERN = re.compile(r"^([+-])(\d{2}):(\d{2}):(\d{2})$")
NAME_PATTERN = re.compile(r"^(\d{6})_(\d{6})(.*)\.([^.]+)$")
EXIF_SUFFIXES = {".nef", ".jpg", ".jpeg"}
ALL_SUFFIXES = EXIF_SUFFIXES | {".xmp"}

# (main source, main target, sidecar pairs that move with it)
Rename = tuple[Path, Path, list[tuple[Path, Path]]]


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


def preflight_renames(renames: list[Rename]) -> str | None:
    """Reject blocked or colliding destinations before any metadata is written."""
    sources: set[Path] = set()
    for source, _target, sidecars in renames:
        sources.add(source.resolve())
        sources.update(sc_src.resolve() for sc_src, _dst in sidecars)
    seen: set[str] = set()
    for _source, target, sidecars in renames:
        for destination in (target, *(dst for _src, dst in sidecars)):
            key = str(destination).casefold()
            if key in seen:
                return f"målnamn krockar inom operationen: {destination.name}"
            seen.add(key)
            if (destination.exists() or destination.is_symlink()) \
                    and destination.resolve() not in sources:
                return f"målet finns redan: {destination}"
    return None


def resolve_files(pattern: str) -> list[Path]:
    """Expand a glob pattern and keep only photo/sidecar extensions."""
    return sorted(
        path
        for path in (Path(match) for match in glob(pattern))
        if path.is_file() and path.suffix.lower() in ALL_SUFFIXES
    )


def build_renames(files: list[Path], seconds: int) -> list[Rename]:
    """Plan main-file renames, attaching any unclaimed XMP sidecar to its main."""
    base = [
        (path, path.with_name(shifted))
        for path in files
        if (shifted := shifted_name(path.name, seconds)) is not None
    ]
    claimed: set[Path] = set()
    renames: list[Rename] = []
    for source, target in base:
        sidecars: list[tuple[Path, Path]] = []
        if source.suffix.lower() in EXIF_SUFFIXES:
            for sidecar in claim_sidecars(source, claimed):
                name = shifted_name(sidecar.name, seconds)
                sidecar_target = sidecar.parent / (name or target.with_suffix(sidecar.suffix).name)
                sidecars.append((sidecar, sidecar_target))
        renames.append((source, target, sidecars))

    # An XMP the pattern matched explicitly is already carried by its main.
    attached = {sc.resolve() for _s, _t, pairs in renames for sc, _dst in pairs}
    return [rename for rename in renames if rename[0].resolve() not in attached]


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
    renames = build_renames(files, seconds)

    problem = preflight_renames(renames)
    if problem:
        print(f"FEL: {problem}", file=sys.stderr)
        return 2
    try:
        renames = order_moves(renames)
    except ValueError as error:
        print(f"FEL: {error}", file=sys.stderr)
        return 2

    count = len(renames) + sum(len(pairs) for _s, _t, pairs in renames)
    print(
        f"Offset {offset} ({seconds} s): {len(files)} files, "
        f"{len(exif_files)} EXIF updates, {count} renames."
    )
    for source, target, sidecars in renames:
        print(f"  {source.name} -> {target.name}")
        for sidecar, sidecar_target in sidecars:
            print(f"    {sidecar.name} -> {sidecar_target.name}")

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
            result = subprocess.run(command, check=False)
            if result.returncode != 0:
                print(
                    "FEL: exiftool kunde inte uppdatera alla filer; inga filer döps om.",
                    file=sys.stderr,
                )
                return 1
        except FileNotFoundError as error:
            print(f"FEL: {error}", file=sys.stderr)
            return 1

    failed = 0
    for source, target, sidecars in renames:
        try:
            move_unit(source, target, sidecars)
        except OSError as error:
            failed += 1
            print(f"FEL: {source.name}: {error}", file=sys.stderr)
    return 1 if failed else 0
