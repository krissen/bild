"""Move images: mirror the source folder structure (``--spegla``).

``--datum`` (grouping by date) and the auto-detecting default arrive in phase 2;
see docs/PLAN.md. Matching is by the leading YYMMDD_HHMMSS token, so the text
after the timestamp and the file extension may differ between source and target.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from .moves import (
    JPEG_EXTENSIONS,
    RAW_EXTENSIONS,
    claim_sidecars,
    extract_date,
    extract_timestamp,
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
) -> tuple[list[tuple[Path, Path, list[Path]]], list[Path]]:
    """Classify root images as safe moves or unresolved.

    Only an unambiguous source folder counts as safe; a token found in several
    folders (or not at all) is left for the user to resolve. A source sitting in
    the source root itself has no subfolder to mirror and is skipped.
    """
    index = build_source_index(source_root)
    safe: list[tuple[Path, Path, list[Path]]] = []
    unresolved: list[Path] = []
    claimed: set[Path] = set()
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
        target = target_root / folder / path.name
        safe.append((path, target, claim_sidecars(path, claimed)))
    return safe, unresolved


def detect_mode(target_root: Path, source_root: Path) -> tuple[str | None, str]:
    """Guess the intended mode from the files in the target root.

    Returns (mode, explanation). ``mode`` is None when the input is ambiguous —
    detection never touches the filesystem, it only reports.
    """
    entries = [path for path in target_root.iterdir() if path.is_file()]
    unnamed_raw = [
        path
        for path in entries
        if path.name.startswith("DSC_") and path.suffix.lower() in RAW_EXTENSIONS
    ]
    # XMP files are sidecars: their fate follows the main file, so they must not
    # create a second category next to a dated jpeg in the same directory.
    dated_raw = [
        path
        for path in entries
        if extract_date(path.name) and path.suffix.lower() in RAW_EXTENSIONS
    ]
    dated_jpg = [
        path
        for path in entries
        if extract_date(path.name) and path.suffix.lower() in JPEG_EXTENSIONS
    ]
    categories = {
        "unnamed_raw": unnamed_raw,
        "dated_raw": dated_raw,
        "dated_jpg": dated_jpg,
    }
    present = [name for name, paths in categories.items() if paths]
    if len(present) != 1:
        detail = ", ".join(f"{len(categories[name])} {name}" for name in present) or "inga kända filer"
        return None, f"blandad eller okänd indata: {detail}"

    if present == ["unnamed_raw"]:
        return "namna", (
            f"{len(unnamed_raw)} DSC_-raws utan datum i namnet — menade du 'bild namna'?"
        )
    if present == ["dated_raw"]:
        return "datum", f"{len(dated_raw)} datummärkta raw-/xmp-filer i {target_root.name}/"

    matched = 0
    if source_root.is_dir():
        index = build_source_index(source_root)
        for path in dated_jpg:
            parsed = extract_timestamp(path.name)
            if parsed and parsed[0] in index:
                matched += 1
    return "spegla", (
        f"{len(dated_jpg)} datummärkta jpegs, {matched} matchande källor under {source_root}"
    )


def compute_datum_moves(
    root: Path,
    *,
    before: str | None = None,
    after: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
) -> dict[str, list[tuple[Path, list[Path]]]]:
    """Group root images by their leading YYMMDD, carrying sidecars along."""
    groups: dict[str, list[tuple[Path, list[Path]]]] = defaultdict(list)
    claimed: set[Path] = set()
    for path in iter_supported_images(root, recursive=False):
        date = extract_date(path.name)
        if not date:
            continue
        if before and date >= before:
            continue
        if after and date <= after:
            continue
        if from_date and date < from_date:
            continue
        if to_date and date > to_date:
            continue
        groups[date].append((path, claim_sidecars(path, claimed)))
    return dict(groups)


def execute_datum_moves(
    groups: dict[str, list[tuple[Path, list[Path]]]],
    root: Path,
    *,
    dry_run: bool,
    verbose: bool,
) -> tuple[int, int]:
    """Move each date group into its YYMMDD subdirectory."""
    moved = failed = 0
    for date, pairs in sorted(groups.items()):
        target_dir = root / date
        for main, sidecars in pairs:
            target = target_dir / main.name
            sidecar_pairs = [(sc, target_dir / sc.name) for sc in sidecars]
            if dry_run:
                error = preflight_destinations([target, *(dst for _src, dst in sidecar_pairs)])
                if error:
                    failed += 1
                    print(f"SKIP: {main.name}: {error}")
                    continue
                print(f"(dry) {main.name} -> {date}/")
                for sidecar, _dst in sidecar_pairs:
                    print(f"(dry) {sidecar.name} -> {date}/")
                continue
            try:
                target_dir.mkdir(parents=True, exist_ok=True)
                move_unit(main, target, sidecar_pairs)
            except OSError as error:
                failed += 1
                print(f"FEL: {main.name}: {error}")
                continue
            moved += 1
            if verbose:
                print(f"{main.name} -> {date}/")
    return moved, failed


def execute_spegla_moves(
    pairs: list[tuple[Path, Path, list[Path]]], *, dry_run: bool, verbose: bool
) -> tuple[int, int]:
    """Move each image with the sidecars claimed for it in the plan."""
    moved = failed = 0
    for source, target, sidecars in pairs:
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
