"""Strip metadata with exiftool, keeping orientation and colour profile."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

_FALLBACKS = ("/opt/homebrew/bin/exiftool", "/usr/local/bin/exiftool")


def find_exiftool() -> str:
    found = shutil.which("exiftool") or next((p for p in _FALLBACKS if Path(p).exists()), None)
    if not found:
        raise SystemExit("exiftool not found (brew install exiftool)")
    return found


def strip(files: list[Path], artist: str | None = None, copyright: str | None = None) -> None:
    """Remove all metadata in place except Orientation and the ICC profile."""
    cmd = [find_exiftool(), "-q", "-q", "-overwrite_original", "-all=", "--icc_profile:all",
           "-tagsfromfile", "@", "-Orientation"]
    if artist:
        cmd.append(f"-Artist={artist}")
    if copyright:
        cmd.append(f"-Copyright={copyright}")
    subprocess.run(cmd + [str(f) for f in files], check=True)


def read_rename_map(path: Path) -> dict[str, str]:
    """Tab-separated 'old<TAB>new' lines; blank lines and '#' comments are ignored."""
    mapping = {}
    for n, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        try:
            old, new = line.split("\t")
        except ValueError as e:
            raise SystemExit(f"{path}:{n}: expected 'old<TAB>new'") from e
        mapping[old.strip()] = new.strip()
    return mapping
