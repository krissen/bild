"""Locate the ``exiftool`` binary robustly.

A GUI-launched process on macOS inherits a minimal PATH that usually lacks
Homebrew's bin directories. Copied from ansikten's core/exiftool.py (36 lines)
so `bild` has no dependency on another repository.
"""

from __future__ import annotations

import os
import shutil

_FALLBACK_PATHS = ("/opt/homebrew/bin/exiftool", "/usr/local/bin/exiftool")


def find_exiftool() -> str:
    """Return an absolute path to a runnable exiftool, or raise."""
    found = shutil.which("exiftool")
    if found:
        return found
    for candidate in _FALLBACK_PATHS:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    raise FileNotFoundError("exiftool not found on PATH or in /opt/homebrew/bin, /usr/local/bin")
