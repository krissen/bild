"""Recolour PNG icons with a mean or chosen RGB, keeping transparency.

Ported from `gor_snittfarg.py`. Light fill pixels can be recoloured while dark
lines stay intact, which is what makes this useful for icons with outlines.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image


def mean_color(files: list[Path]) -> tuple[int, int, int] | None:
    """Mean RGB over all visible (alpha > 0) pixels, or None if there are none."""
    chunks = []
    for path in files:
        try:
            array = np.array(Image.open(path).convert("RGBA"))
        except OSError as error:
            print(f"warning: skipping {path}: {error}", file=sys.stderr)
            continue
        visible = array[:, :, 3] > 0
        if visible.any():
            chunks.append(array[visible][:, :3])
    if not chunks:
        return None
    return tuple(int(v) for v in np.concatenate(chunks).mean(axis=0).round())


def recolor_img(
    path: Path,
    rgb: tuple[int, int, int],
    out: Path,
    *,
    preserve_dark: bool = True,
    threshold: int = 170,
) -> int:
    """Recolour visible pixels; return the number of pixels actually changed."""
    array = np.array(Image.open(path).convert("RGBA"))
    mask = array[:, :, 3] > 0
    if preserve_dark:
        luminance = (
            0.2126 * array[:, :, 0]
            + 0.7152 * array[:, :, 1]
            + 0.0722 * array[:, :, 2]
        )
        mask &= luminance >= threshold
    before = array[mask, :3].copy()
    array[mask, :3] = rgb
    changed = int(np.any(before != rgb, axis=1).sum())
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(array).save(out)
    return changed


def run_farg(
    files: list[Path],
    *,
    colour: tuple[int, int, int] | None = None,
    overwrite: bool = False,
    find_mean: bool = False,
    preserve_dark: bool = True,
    threshold: int = 170,
) -> int:
    """Choose a colour, report it, and optionally recolour the PNGs."""
    if colour is None:
        colour = mean_color(files)
        if colour is None:
            print("No visible pixels found.", file=sys.stderr)
            return 1
    print(f"RGB: {colour}  #{colour[0]:02x}{colour[1]:02x}{colour[2]:02x}")
    if find_mean:
        return 0

    outdir = Path("recolored")
    if not overwrite:
        planned: dict[str, Path] = {}
        for path in files:
            if path.suffix.lower() != ".png":
                continue
            target = outdir / path.name
            if target.resolve() == path.resolve():
                print(
                    f"FEL: {path} ligger redan i {outdir}; använd --overwrite",
                    file=sys.stderr,
                )
                return 2
            key = str(target).casefold()
            if key in planned:
                print(f"FEL: två indata skriver till samma fil: {target.name}", file=sys.stderr)
                return 2
            planned[key] = path
        outdir.mkdir(parents=True, exist_ok=True)
    done = 0
    for path in files:
        if path.suffix.lower() != ".png":
            print(f"skipping {path}: not a PNG", file=sys.stderr)
            continue
        target = path if overwrite else outdir / path.name
        try:
            changed = recolor_img(
                path, colour, target, preserve_dark=preserve_dark, threshold=threshold
            )
        except OSError as error:
            print(f"failed {path}: {error}", file=sys.stderr)
            continue
        done += 1
        note = "no change" if changed == 0 else f"{changed} pixels changed"
        print(f"{path} -> {target} ({note})")
    return 0 if done else 1
