"""Face detection with InsightFace (buffalo_l, detection module only)."""

from __future__ import annotations

import contextlib
import io
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class Box:
    """A box in pixel coordinates. score is -1 for boxes added by hand."""

    x0: float
    y0: float
    x1: float
    y1: float
    score: float = -1.0

    @property
    def center(self) -> tuple[float, float]:
        return (self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0


_app = None
_app_key = None


def _get_app(det_size: int, threshold: float):
    global _app, _app_key
    key = (det_size, threshold)
    if _app is None or _app_key != key:
        # insightface prints model info on stdout; keep the CLI output clean
        with contextlib.redirect_stdout(io.StringIO()):
            from insightface.app import FaceAnalysis

            app = FaceAnalysis(
                name="buffalo_l",
                allowed_modules=["detection"],
                providers=["CPUExecutionProvider"],
            )
            app.prepare(ctx_id=-1, det_size=(det_size, det_size), det_thresh=threshold)
        _app, _app_key = app, key
    return _app


def detect(
    img: np.ndarray, *, max_side: int = 2400, det_size: int = 1280, threshold: float = 0.25
) -> list[Box]:
    """Detect faces on a downscaled copy and return boxes in full-resolution coordinates.

    The low threshold and large det_size favour recall: for anonymising, a missed face costs
    more than a blurred patch of wall.
    """
    h, w = img.shape[:2]
    s = min(1.0, max_side / max(h, w))
    small = cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA) if s < 1 else img
    faces = _get_app(det_size, threshold).get(small)
    boxes = [Box(*(f.bbox / s).tolist(), score=float(f.det_score)) for f in faces]
    return sorted(boxes, key=lambda b: -b.score)
