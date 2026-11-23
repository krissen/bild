"""Move images: mirror the source folder structure (``--spegla``).

``--datum`` (grouping by date) and the auto-detecting default arrive in phase 2;
see docs/PLAN.md. Matching is by the leading YYMMDD_HHMMSS token, so the text
after the timestamp and the file extension may differ between source and target.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from .moves import (
    extract_timestamp,
    find_sidecar_files,
    iter_supported_images,
    move_unit,
    preflight_destinations,
)


def build_source_index(source_root: Path) -> dict[str, set[Path]]:
    """Map a timestamp token to the relative folders where it occurs."""
    by_token: dict[str, set[Path]] = defaultdict(set)
    for path in iter_supported_images(source_root, recursive=True):
        parsed = extract_timestamp(path.name)
        if not parsed:
            continue
        token, _timestamp = parsed
        by_token[token].add(path.parent.relative_to(source_root))
    return dict(by_token)


def compute_spegla_moves(
    source_root: Path, target_root: Path
) -> tuple[list[tuple[Path, Path]], list[Path]]:
    """Classify root images as safe moves or unresolved.

    Only an unambiguous source folder counts as safe; a token found in several
    folders (or not at all) is left for the user to resolve. A source sitting in
    the source root itself has no subfolder to mirror and is skipped.
    """
    index = build_source_index(source_root)
    safe: list[tuple[Path, Path]] = []
    unresolved: list[Path] = []
    for path in iter_supported_images(target_root, recursive=False):
        parsed = extract_timestamp(path.name)
        if not parsed:
            unresolved.append(path)
            continue
        token, _timestamp = parsed
        folders = index.get(token, set())
        if len(folders) != 1:
            unresolved.append(path)
            continue
        folder = next(iter(folders))
        if folder == Path("."):
            continue
        safe.append((path, target_root / folder / path.name))
    return safe, unresolved


def execute_spegla_moves(
    pairs: list[tuple[Path, Path]], *, dry_run: bool, verbose: bool
) -> tuple[int, int]:
    """Move each image with its sidecar; return (moved, failed) counts."""
    moved = failed = 0
    for source, target in pairs:
        sidecars = find_sidecar_files(source)
        sidecar_pairs = [(sc, target.with_suffix(sc.suffix)) for sc in sidecars]
        if dry_run:
            error = preflight_destinations([target, *(dst for _src, dst in sidecar_pairs)])
            if error:
                failed += 1
                print(f"SKIP: {source.name}: {error}")
                continue
            print(f"(dry) {source.name} -> {target.parent}/")
            for sidecar, _dst in sidecar_pairs:
                print(f"(dry) {sidecar.name} -> {target.parent}/")
            continue
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            move_unit(source, target, sidecar_pairs)
        except OSError as error:
            failed += 1
            print(f"FEL: {source.name}: {error}")
            continue
        moved += 1
        if verbose:
            print(f"{source.name} -> {target.parent}/")
    return moved, failed
