"""Straighten an image from measured lines, and crop around a region."""

from __future__ import annotations

import math

import cv2
import numpy as np


def parse_points(text: str, n: int) -> list[tuple[float, float]]:
    vals = [float(v) for v in text.replace(";", ",").split(",")]
    if len(vals) != 2 * n:
        raise ValueError(f"expected {n} points ({2 * n} numbers), got {text!r}")
    return [(vals[i], vals[i + 1]) for i in range(0, len(vals), 2)]


def angle_from_lines(lines: list[tuple[tuple[float, float], tuple[float, float]]]) -> float:
    """Mean angle in degrees (image coordinates, y down) of lines that should be horizontal."""
    angles = []
    for (x0, y0), (x1, y1) in lines:
        if x1 < x0:
            (x0, y0), (x1, y1) = (x1, y1), (x0, y0)
        angles.append(math.degrees(math.atan2(y1 - y0, x1 - x0)))
    return sum(angles) / len(angles)


def level(
    img: np.ndarray,
    angle: float,
    corners: list[tuple[float, float]] | None = None,
    margin: int = 70,
) -> tuple[np.ndarray, int]:
    """Rotate so that a line at `angle` becomes horizontal; crop around `corners` if given.

    Returns the result and the number of fill pixels in it, i.e. pixels from outside the
    original frame (more than a handful means the crop or margin reaches past the photo).
    """
    h, w = img.shape[:2]
    if corners:
        pts = np.array(corners, float)
        cx, cy = pts.mean(0)
    else:
        pts = np.array([[0, 0], [w, 0], [w, h], [0, h]], float)
        cx, cy = w / 2, h / 2
    m = cv2.getRotationMatrix2D((cx, cy), angle, 1.0)
    rot = cv2.warpAffine(img, m, (w, h), flags=cv2.INTER_CUBIC,
                         borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0))
    # track fill with a mask: counting black pixels would also count dark image content
    inside = cv2.warpAffine(np.ones((h, w), np.uint8), m, (w, h), flags=cv2.INTER_NEAREST,
                            borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    if corners:
        rc = (m @ np.c_[pts, np.ones(len(pts))].T).T
        x0, y0 = rc.min(0) - margin
        x1, y1 = rc.max(0) + margin
        x0, y0 = int(max(0, x0)), int(max(0, y0))
        x1, y1 = int(min(w, x1)), int(min(h, y1))
        rot, inside = rot[y0:y1, x0:x1], inside[y0:y1, x0:x1]
    return rot, int((inside == 0).sum())
