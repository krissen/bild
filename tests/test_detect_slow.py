from pathlib import Path

import pytest

pytestmark = pytest.mark.slow


def test_detects_faces_in_insightface_sample():
    import insightface

    from bild.faces import detect
    from bild.io import load_image

    sample = Path(insightface.__file__).parent / "data" / "images" / "t1.jpg"
    boxes = detect(load_image(sample))
    assert len(boxes) >= 5
    assert all(b.width > 0 and b.height > 0 for b in boxes)
