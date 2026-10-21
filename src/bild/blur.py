"""Face blurring: soft feathered ellipses (default) or pixelated blocks."""

from __future__ import annotations

import cv2
import numpy as np

from .faces import Box


def parse_frac_box(text: str) -> tuple[float, float, float, float]:
    """Parse 'x0,y0,x1,y1' given as fractions (0-1) of image width and height."""
    parts = [float(p) for p in text.split(",")]
    if len(parts) != 4 or not all(0 <= p <= 1 for p in parts):
        raise ValueError(f"expected four fractions 0-1 as x0,y0,x1,y1, got {text!r}")
    x0, y0, x1, y1 = parts
    if x1 <= x0 or y1 <= y0:
        raise ValueError(f"box must have x1>x0 and y1>y0, got {text!r}")
    return x0, y0, x1, y1


def frac_to_box(frac: tuple[float, float, float, float], w: int, h: int) -> Box:
    x0, y0, x1, y1 = frac
    return Box(x0 * w, y0 * h, x1 * w, y1 * h)


def drop_kept(boxes: list[Box], keep: list[tuple], w: int, h: int) -> list[Box]:
    """Remove detected boxes whose centre falls inside any keep region (fractions)."""
    out = []
    for b in boxes:
        cx, cy = b.center
        fx, fy = cx / w, cy / h
        if any(k[0] <= fx <= k[2] and k[1] <= fy <= k[3] for k in keep):
            continue
        out.append(b)
    return out


def _ellipse_axes(b: Box) -> tuple[float, float]:
    # a little beyond the detector box, which is tight around eyes-to-chin
    return b.width * 0.68, b.height * 0.78


def blur_soft(img: np.ndarray, boxes: list[Box]) -> np.ndarray:
    out = img.copy()
    h, w = img.shape[:2]
    for b in boxes:
        cx, cy = b.center
        ax, ay = _ellipse_axes(b)
        pad = int(max(ax, ay) * 1.6)
        x0, y0 = int(max(0, cx - pad)), int(max(0, cy - pad))
        x1, y1 = int(min(w, cx + pad)), int(min(h, cy + pad))
        roi = img[y0:y1, x0:x1]
        if roi.size == 0:
            continue
        sigma = max(6.0, b.width / 5.0)
        blurred = cv2.GaussianBlur(cv2.GaussianBlur(roi, (0, 0), sigma), (0, 0), sigma)
        mask = np.zeros(roi.shape[:2], np.float32)
        cv2.ellipse(mask, (int(cx - x0), int(cy - y0)), (int(ax), int(ay)), 0, 0, 360, 1.0, -1)
        mask = cv2.GaussianBlur(mask, (0, 0), max(2.0, b.width / 12.0))
        mask = np.clip(mask * 1.25, 0, 1)[..., None]
        cur = out[y0:y1, x0:x1].astype(np.float32)
        out[y0:y1, x0:x1] = (cur * (1 - mask) + blurred.astype(np.float32) * mask).astype(np.uint8)
    return out


def blur_pixel(img: np.ndarray, boxes: list[Box]) -> np.ndarray:
    out = img.copy()
    h, w = img.shape[:2]
    for b in boxes:
        cx, cy = b.center
        bw, bh = b.width * 1.5, b.height * 1.6
        x0, y0 = int(max(0, cx - bw / 2)), int(max(0, cy - bh / 2))
        x1, y1 = int(min(w, cx + bw / 2)), int(min(h, cy + bh / 2))
        roi = out[y0:y1, x0:x1]
        if roi.size == 0:
            continue
        k = max(10, (x1 - x0) // 6)
        small = cv2.resize(roi, (max(1, (x1 - x0) // k), max(1, (y1 - y0) // k)))
        big = cv2.resize(small, (x1 - x0, y1 - y0), interpolation=cv2.INTER_NEAREST)
        out[y0:y1, x0:x1] = cv2.GaussianBlur(big, (0, 0), k)
    return out


def blur(img: np.ndarray, boxes: list[Box], style: str = "soft") -> np.ndarray:
    if style == "soft":
        return blur_soft(img, boxes)
    if style == "pixel":
        return blur_pixel(img, boxes)
    raise ValueError(f"unknown style {style!r}")


def preview(img: np.ndarray, boxes: list[Box], kept: list[Box] = ()) -> np.ndarray:
    """Draw what will be blurred (red, with score or 'manual') and what is kept (green)."""
    out = img.copy()
    w = img.shape[1]
    thick = max(3, w // 400)
    scale = max(0.8, w / 1500)
    for b, colour in [(b, (0, 0, 255)) for b in boxes] + [(b, (0, 200, 0)) for b in kept]:
        cx, cy = b.center
        ax, ay = _ellipse_axes(b)
        cv2.ellipse(out, (int(cx), int(cy)), (int(ax), int(ay)), 0, 0, 360, colour, thick)
        label = "manual" if b.score < 0 else f"{b.score:.2f}"
        cv2.putText(out, label, (int(cx - ax), int(cy - ay) - 6), cv2.FONT_HERSHEY_SIMPLEX,
                    scale, colour, max(2, thick // 2))
    return out
