import numpy as np
import pytest

from bild.blur import blur, drop_kept, frac_to_box, parse_frac_box
from bild.faces import Box


def noisy(h=400, w=600, seed=0):
    return np.random.default_rng(seed).integers(0, 255, (h, w, 3), dtype=np.uint8)


def test_parse_frac_box_rejects_bad_input():
    assert parse_frac_box("0.1,0.2,0.3,0.4") == (0.1, 0.2, 0.3, 0.4)
    for bad in ["0.1,0.2,0.3", "0.3,0.2,0.1,0.4", "0,0,1.5,1"]:
        with pytest.raises(ValueError):
            parse_frac_box(bad)


def test_drop_kept_uses_box_centre():
    a, b = Box(10, 10, 50, 50, 0.9), Box(300, 100, 340, 140, 0.8)
    left = drop_kept([a, b], [(0.0, 0.0, 0.2, 0.3)], 600, 400)
    assert left == [b]


@pytest.mark.parametrize("style", ["soft", "pixel"])
def test_blur_changes_face_and_leaves_far_pixels(style):
    img = noisy()
    box = frac_to_box((0.4, 0.4, 0.5, 0.55), 600, 400)
    out = blur(img, [box], style)
    cx, cy = (int(c) for c in box.center)
    face = (slice(cy - 10, cy + 10), slice(cx - 10, cx + 10))
    # blurred noise has far lower variance than the original noise
    assert out[face].std() < img[face].std() / 2
    assert np.array_equal(out[:40, :40], img[:40, :40])
    assert out.shape == img.shape and out.dtype == np.uint8


def test_soft_blur_has_feathered_edge():
    img = noisy()
    box = Box(250, 150, 350, 270)
    out = blur(img, [box], "soft")
    diff = np.abs(out.astype(int) - img.astype(int)).sum(2)
    row = diff[210, 150:300]
    # change grows gradually from outside the ellipse inwards, no hard step
    assert row[0] == 0 and row[-1] > 0
    assert (row > 0).sum() > 30
