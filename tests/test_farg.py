import numpy as np
from PIL import Image

from bild import farg
from bild.cli import main


def write_png(path, pixels):
    Image.fromarray(np.array(pixels, dtype=np.uint8), "RGBA").save(path)


def test_mean_color_ignores_transparent_pixels(tmp_path):
    a = tmp_path / "a.png"
    b = tmp_path / "b.png"
    write_png(a, [[[100, 100, 100, 255], [0, 0, 0, 0]]])
    write_png(b, [[[200, 200, 200, 255], [0, 0, 0, 0]]])
    assert farg.mean_color([a, b]) == (150, 150, 150)


def test_recolor_preserves_dark_and_transparent(tmp_path):
    src = tmp_path / "icon.png"
    out = tmp_path / "out.png"
    write_png(
        src,
        [
            [[255, 255, 255, 255], [10, 10, 10, 255]],
            [[240, 240, 240, 0], [220, 220, 220, 255]],
        ],
    )
    changed = farg.recolor_img(src, (200, 100, 50), out, threshold=170)
    assert changed == 2
    result = np.array(Image.open(out))
    assert tuple(result[0, 0, :3]) == (200, 100, 50)
    assert tuple(result[0, 1, :3]) == (10, 10, 10)
    assert tuple(result[1, 0, :3]) == (240, 240, 240)
    assert result[1, 0, 3] == 0


def test_cli_farg_find_mean(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    src = tmp_path / "icon.png"
    write_png(src, [[[100, 150, 200, 255]]])
    assert main(["farg", "-f", str(src)]) == 0
    assert "RGB: (100, 150, 200)" in capsys.readouterr().out
    assert not (tmp_path / "recolored").exists()


def test_cli_farg_rejects_input_already_in_output_dir(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    outdir = tmp_path / "recolored"
    outdir.mkdir()
    src = outdir / "icon.png"
    write_png(src, [[[200, 200, 200, 255]]])
    assert main(["farg", "-c", "1,2,3", str(src)]) == 2
    assert "redan i" in capsys.readouterr().err
    assert tuple(np.array(Image.open(src))[0, 0, :3]) == (200, 200, 200)


def test_cli_farg_rejects_duplicate_output_names(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    first, second = tmp_path / "a" / "icon.png", tmp_path / "b" / "icon.png"
    for path in (first, second):
        path.parent.mkdir()
        write_png(path, [[[200, 200, 200, 255]]])
    assert main(["farg", "-c", "1,2,3", str(first), str(second)]) == 2
    assert "samma fil" in capsys.readouterr().err


def test_cli_farg_writes_to_recolored(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    src = tmp_path / "icon.png"
    write_png(src, [[[200, 200, 200, 255]]])
    assert main(["farg", "-c", "10,20,30", str(src)]) == 0
    result = np.array(Image.open(tmp_path / "recolored" / "icon.png"))
    assert tuple(result[0, 0, :3]) == (10, 20, 30)
    assert tuple(np.array(Image.open(src))[0, 0, :3]) == (200, 200, 200)
