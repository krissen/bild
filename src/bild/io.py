"""Loading and saving images as BGR arrays, with EXIF orientation applied."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

RAW_EXTENSIONS = {".nef", ".cr2", ".cr3", ".arw", ".dng", ".raf", ".orf", ".rw2"}
HEIC_EXTENSIONS = {".heic", ".heif"}


def load_image(path: str | Path) -> np.ndarray:
    """Return the image as a BGR uint8 array, upright according to EXIF."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in RAW_EXTENSIONS:
        try:
            import rawpy
        except ImportError as e:
            raise SystemExit(f"{path.name}: RAW support needs the 'raw' extra (rawpy)") from e
        with rawpy.imread(str(path)) as raw:
            rgb = raw.postprocess(use_camera_wb=True)
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    if suffix in HEIC_EXTENSIONS:
        try:
            import pillow_heif
        except ImportError as e:
            raise SystemExit(f"{path.name}: HEIC support needs the 'heic' extra") from e
        pillow_heif.register_heif_opener()
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        return cv2.cvtColor(np.asarray(im), cv2.COLOR_RGB2BGR)


def save_jpg(path: str | Path, img: np.ndarray, quality: int = 92) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), img, [cv2.IMWRITE_JPEG_QUALITY, quality]):
        raise SystemExit(f"could not write {path}")


def resized(img: np.ndarray, width: int) -> np.ndarray:
    h, w = img.shape[:2]
    if w <= width:
        return img
    return cv2.resize(img, (width, int(h * width / w)), interpolation=cv2.INTER_AREA)
