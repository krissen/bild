"""Rename images from EXIF CreateDate to YYMMDD_HHMMSS.

Already-named files are left alone, but reserve their slot so a same-second
unnamed frame cannot be renamed into a future collision. XMP sidecars follow
their main file. See docs/PLAN.md for why this is a separate verb from `flytta`.
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

from .exiftool import find_exiftool
from .moves import claim_sidecars, move_unit, preflight_destinations

_NAMED_REST = re.compile(r"(-\d+)?[a-zA-Z]{0,3}(_.*)?$")
_BARE = "bare"


def exif_dates(files: list[Path]) -> dict[Path, tuple[str, str]]:
    """Read EXIF CreateDate and SubSecTimeOriginal in one exiftool call."""
    if not files:
        return {}
    cmd = [
        find_exiftool(),
        "-q",
        "-q",
        "-m",
        "-if",
        "defined $CreateDate",
        "-d",
        "%y%m%d_%H%M%S",
        "-p",
        "$CreateDate|${SubSecTimeOriginal;$_||=0}|$FilePath",
        "--",
        *[str(f) for f in files],
    ]
    result = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=300)
    dates: dict[Path, tuple[str, str]] = {}
    for line in result.stdout.strip().splitlines():
        parts = line.split("|", 2)
        if len(parts) == 3:
            dates[Path(parts[2]).resolve()] = (parts[0], parts[1])
    return dates


def is_already_named(name: str, timestamp: str) -> bool:
    """True when the stem already begins with its EXIF timestamp."""
    stem = Path(name).stem
    return stem.startswith(timestamp) and _NAMED_REST.fullmatch(stem[len(timestamp) :]) is not None


def _slot(name: str, timestamp: str) -> str | int:
    rest = Path(name).stem[len(timestamp) :]
    match = re.match(r"-(\d+)", rest)
    return int(match.group(1)) if match else _BARE


def compute_renames(
    entries: list[tuple[str, str, Path]], *, include_named: bool = False
) -> list[tuple[Path, Path]]:
    """Plan renames for (timestamp, subsecond, path) entries.

    One exposure is one (timestamp, subsecond) pair: its RAW and JPEG variants
    share a destination stem so a shared XMP sidecar stays associated with both.
    Distinct exposures at the same timestamp still get distinct -N slots.
    """
    to_rename: list[tuple[str, str, Path]] = []
    protected: list[tuple[str, str, Path]] = []
    for entry in entries:
        if not include_named and is_already_named(entry[2].name, entry[0]):
            protected.append(entry)
        else:
            to_rename.append(entry)

    exposures: dict[str, dict[str, list[tuple[str, str, Path]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for timestamp, subsecond, src in to_rename:
        exposures[timestamp][subsecond].append((timestamp, subsecond, src))

    taken: dict[str, set] = defaultdict(set)
    for timestamp, _sub, src in protected:
        taken[timestamp].add(_slot(src.name, timestamp))

    renames: list[tuple[Path, Path]] = []
    for timestamp, by_subsecond in sorted(exposures.items()):
        subseconds = sorted(by_subsecond)
        digits = max(2, len(str(len(subseconds) + len(taken[timestamp]) - 1)))
        for subsecond in subseconds:
            slots = taken[timestamp]
            if len(subseconds) == 1 and _BARE not in slots:
                base = timestamp
                slots.add(_BARE)
            else:
                index = 0
                while index in slots:
                    index += 1
                slots.add(index)
                base = f"{timestamp}-{str(index).zfill(digits)}"
            for _ts, _sub, src in sorted(by_subsecond[subsecond], key=lambda e: e[2].name):
                dst = src.parent / f"{base}{src.suffix}"
                if src.name != dst.name:
                    renames.append((src, dst))
    return renames


def execute_renames(renames: list[tuple[Path, Path]], *, dry_run: bool) -> tuple[int, int]:
    """Rename with sidecars, never overwriting. Returns (renamed, failed)."""
    moved = failed = 0
    claimed: set[Path] = set()
    for src, dst in renames:
        sidecars = claim_sidecars(src, claimed)
        sidecar_pairs = [(sc, dst.with_suffix(sc.suffix)) for sc in sidecars]
        if dry_run:
            error = preflight_destinations([dst, *(d for _s, d in sidecar_pairs)])
            if error:
                failed += 1
                print(f"SKIP: {src.name}: {error}")
                continue
            print(f"(dry) {src.name} -> {dst.name}")
            for sidecar, _target in sidecar_pairs:
                print(f"(dry) {sidecar.name} -> {dst.with_suffix(sidecar.suffix).name}")
            continue
        try:
            move_unit(src, dst, sidecar_pairs)
        except OSError as error:
            failed += 1
            print(f"FEL: {src.name}: {error}")
            continue
        moved += 1
        print(f"{src.name} -> {dst.name}")
    return moved, failed


def run_namna(files: list[Path], *, dry_run: bool, include_named: bool = False) -> int:
    """Full rename flow: read EXIF, plan, preview or execute."""
    if not files:
        print("No files matched.")
        return 0
    try:
        dates = exif_dates(files)
    except FileNotFoundError as error:
        print(f"FEL: {error}", file=sys.stderr)
        return 1
    except subprocess.TimeoutExpired:
        print("FEL: exiftool timeout", file=sys.stderr)
        return 1

    entries = []
    for path in files:
        resolved = path.resolve()
        if resolved in dates:
            timestamp, subsecond = dates[resolved]
            entries.append((timestamp, subsecond, resolved))
    renames = compute_renames(entries, include_named=include_named)
    print(f"Planned renames: {len(renames)}, without EXIF date: {len(files) - len(entries)}.")
    moved, failed = execute_renames(renames, dry_run=dry_run)
    if not dry_run:
        print(f"Renamed {moved} files.")
    return 1 if failed else 0
