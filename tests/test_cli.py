import shutil
import subprocess

import numpy as np
import pytest
from PIL import Image

from bild.cli import main


def write_jpg(path, w=300, h=200):
    arr = np.random.default_rng(1).integers(0, 255, (h, w, 3), dtype=np.uint8)
    Image.fromarray(arr).save(path, quality=90)


def test_blur_no_detect_with_add_box(tmp_path):
    src = tmp_path / "a.jpg"
    write_jpg(src)
    assert main(["blur", str(src), "-o", str(tmp_path / "out"), "--no-detect",
                 "--add", "0.4,0.4,0.6,0.6", "--preview", str(tmp_path / "pv")]) == 0
    assert (tmp_path / "out" / "a__blur.jpg").exists()
    assert (tmp_path / "pv" / "a__preview.jpg").exists()


def test_contact_sheet(tmp_path):
    files = []
    for i in range(3):
        f = tmp_path / f"{i}.jpg"
        write_jpg(f)
        files.append(str(f))
    out = tmp_path / "sheet.png"
    assert main(["contact", *files, "-o", str(out), "--cols", "2", "--size", "100"]) == 0
    assert Image.open(out).size == (200, 240)


@pytest.mark.skipif(not shutil.which("exiftool"), reason="exiftool missing")
def test_strip_copies_renames_and_sets_artist(tmp_path):
    src = tmp_path / "Lina_Peter.jpg"
    write_jpg(src)
    subprocess.run(["exiftool", "-q", "-overwrite_original", "-Keywords=secret",
                    "-GPSLatitude=25", str(src)], check=True)
    rmap = tmp_path / "map.tsv"
    rmap.write_text("Lina_Peter.jpg\t01_group.jpg\n")
    out = tmp_path / "out"
    assert main(["strip", str(src), "-o", str(out), "--rename-map", str(rmap),
                 "--artist", "K N"]) == 0
    dst = out / "01_group.jpg"
    tags = subprocess.run(["exiftool", "-s", "-s", "-s", "-Keywords", "-GPSLatitude",
                           "-Artist", "-Copyright", str(dst)],
                          capture_output=True, text=True, check=True).stdout.split("\n")
    assert "secret" not in "".join(tags)
    assert "K N" in tags and "Foto: K N" in tags
    assert src.exists()  # original untouched
