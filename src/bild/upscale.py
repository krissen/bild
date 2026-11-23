"""AI upscaling through gor_upscale.py in the realesrgan conda environment.

`gor_upscale.py` needs cv2/basicsr/realesrgan, which live in a dedicated conda
environment. Rather than making bild's venv heavy, this verb invokes that
environment's interpreter in a subprocess. Paths can be overridden with
`BILD_UPSCALE_PYTHON` and `BILD_UPSCALE_SCRIPT`; see docs/PLAN.md.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

DEFAULT_PYTHON = Path("~/.local/share/miniforge3/envs/realesrgan/bin/python").expanduser()
DEFAULT_SCRIPT = Path("~/bin/scripts/gor_upscale.py").expanduser()


def run_upscale(arguments: list[str]) -> int:
    """Run gor_upscale.py in its conda env and return its exit status."""
    python = Path(os.environ.get("BILD_UPSCALE_PYTHON", str(DEFAULT_PYTHON))).expanduser()
    script = Path(os.environ.get("BILD_UPSCALE_SCRIPT", str(DEFAULT_SCRIPT))).expanduser()
    for label, path in (("python", python), ("script", script)):
        if not path.is_file():
            print(f"FEL: {label} for upscale hittas inte: {path}", file=sys.stderr)
            return 1
    return subprocess.run([str(python), str(script), *arguments], check=False).returncode
