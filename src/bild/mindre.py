"""Downscaled copies through `gor_mindre` on PATH.

The shell tool owns the ImageMagick -> jpegtran -> oxipng pipeline and its
metadata guarantees (EXIF/XMP preserved, lossless optimisations). This verb is
only a discoverable entry point with bild's argument conventions; see
docs/PLAN.md for the environment contract.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def run_mindre(
    *, size: int, quality: int, outdir: Path, files: list[str], force: bool
) -> int:
    """Invoke gor_mindre and return its exit status."""
    executable = shutil.which("gor_mindre")
    if executable is None:
        print(
            "FEL: gor_mindre hittas inte på PATH (behövs för 'bild mindre')",
            file=sys.stderr,
        )
        return 1
    command = [
        executable,
        "--size",
        str(size),
        "--quality",
        str(quality),
        "--outdir",
        str(outdir),
    ]
    if force:
        command.append("--force")
    command.extend(files)
    return subprocess.run(command, check=False).returncode
