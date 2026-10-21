import cv2
import numpy as np
import pytest

from bild.level import angle_from_lines, level, parse_points


def test_angle_from_lines_is_mean_and_direction_free():
    lines = [((0, 100), (100, 90)), ((100, 200), (0, 210))]
    assert angle_from_lines(lines) == pytest.approx(np.degrees(np.arctan2(-10, 100)))


def test_parse_points():
    assert parse_points("1,2;3,4", 2) == [(1, 2), (3, 4)]
    with pytest.raises(ValueError):
        parse_points("1,2,3", 2)


def test_level_makes_tilted_line_horizontal():
    img = np.full((600, 800, 3), 255, np.uint8)
    p0, p1 = (150, 400), (650, 300)  # tilted line
    cv2.line(img, p0, p1, (20, 20, 20), 5)  # not pure black: that counts as fill
    angle = angle_from_lines([(p0, p1)])
    corners = [(150, 280), (650, 280), (650, 420), (150, 420)]
    out, black = level(img, angle, corners, margin=10)
    ys, xs = np.where(out.sum(2) < 100)
    # fit a line through the dark pixels; its slope should now be ~0
    slope = np.polyfit(xs, ys, 1)[0]
    assert abs(slope) < 0.01
    assert black == 0
