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
from .moves import (
    SUPPORTED_EXTENSIONS,
    claim_sidecars,
    move_unit,
    order_moves,
    preflight_destinations,
)

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
    # exiftool returns 2 when every file failed the `-if defined $CreateDate`
    # condition — that is an ordinary "no dates here" result, not a read error.
    if result.returncode == 2:
        return {}
    if result.returncode != 0:
        detail = result.stderr.strip() or f"exiftool exited with status {result.returncode}"
        raise RuntimeError(detail[:300])
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

    # timestamp -> subsecond -> original stem -> entries. Files sharing a stem
    # are one frame (RAW + JPEG + XMP); distinct stems are distinct frames and
    # must never collapse onto the same destination even within one second.
    frames: dict[str, dict[str, dict[str, list[tuple[str, str, Path]]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(list))
    )
    for timestamp, subsecond, src in to_rename:
        frames[timestamp][subsecond][src.stem].append((timestamp, subsecond, src))

    taken: dict[str, set] = defaultdict(set)
    for timestamp, _sub, src in protected:
        taken[timestamp].add(_slot(src.name, timestamp))

    renames: list[tuple[Path, Path]] = []
    for timestamp, by_subsecond in sorted(frames.items()):
        by_subsecond = dict(sorted(by_subsecond.items()))
        frame_count = sum(len(stems) for stems in by_subsecond.values())
        digits = max(2, len(str(frame_count + len(taken[timestamp]) - 1)))
        for stems in by_subsecond.values():
            for entries_in_frame in sorted(stems.values()):
                slots = taken[timestamp]
                if frame_count == 1 and _BARE not in slots:
                    base = timestamp
                    slots.add(_BARE)
                else:
                    index = 0
                    while index in slots:
                        index += 1
                    slots.add(index)
                    base = f"{timestamp}-{str(index).zfill(digits)}"
                for _ts, _sub, src in entries_in_frame:
                    dst = src.parent / f"{base}{src.suffix}"
                    if src.name != dst.name:
                        renames.append((src, dst))
    return renames


# (main source, main target, sidecar pairs discovered before any rename)
Move = tuple[Path, Path, list[tuple[Path, Path]]]


def build_move_plan(
    entries: list[tuple[str, str, Path]], *, include_named: bool = False
) -> list[Move]:
    """Freeze every sidecar association before the first filesystem change.

    Discovering sidecars inside the execution loop can pick up an XMP that an
    earlier rename just created at a later source's stem, transferring the
    wrong photo's editing metadata. Discovery therefore happens once, up front.
    """
    claimed: set[Path] = set()
    sidecars_by_main: dict[Path, list[Path]] = {}
    attached: set[Path] = set()
    for _timestamp, _subsecond, path in entries:
        if path.suffix.lower() in SUPPORTED_EXTENSIONS:
            sidecars = claim_sidecars(path, claimed)
            sidecars_by_main[path.resolve()] = sidecars
            attached.update(sidecar.resolve() for sidecar in sidecars)

    # An XMP carried by its main must not also appear as a standalone rename.
    planned = [entry for entry in entries if entry[2].resolve() not in attached]
    renames = compute_renames(planned, include_named=include_named)
    return [
        (
            src,
            dst,
            [(sc, dst.with_suffix(sc.suffix)) for sc in sidecars_by_main.get(src.resolve(), [])],
        )
        for src, dst in renames
    ]


def execute_renames(plan: list[Move], *, dry_run: bool) -> tuple[int, int]:
    """Rename with the sidecars frozen in the plan. Returns (renamed, failed)."""
    moved = failed = 0
    vacated: set[Path] = set()
    for source, _target, sidecars in plan:
        vacated.add(source.resolve())
        vacated.update(sc_src.resolve() for sc_src, _dst in sidecars)
    for src, dst, sidecar_pairs in plan:
        if dry_run:
            error = preflight_destinations(
                [dst, *(d for _s, d in sidecar_pairs)], vacated=vacated
            )
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
    except RuntimeError as error:
        print(f"FEL: exiftool: {error}", file=sys.stderr)
        return 1

    entries = []
    for path in files:
        # EXIF is keyed by the resolved path, but the plan must operate on the
        # path the user selected: otherwise a symlink renames its target away.
        timestamp_pair = dates.get(path.resolve())
        if timestamp_pair is not None:
            timestamp, subsecond = timestamp_pair
            entries.append((timestamp, subsecond, path))
    plan = build_move_plan(entries, include_named=include_named)
    try:
        plan = order_moves(plan)
    except ValueError as error:
        print(f"FEL: {error}", file=sys.stderr)
        return 2
    print(f"Planned renames: {len(plan)}, without EXIF date: {len(files) - len(entries)}.")
    moved, failed = execute_renames(plan, dry_run=dry_run)
    if not dry_run:
        print(f"Renamed {moved} files.")
    return 1 if failed else 0
