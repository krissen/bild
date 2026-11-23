import pytest

from bild.cli import main
from bild.flytta import compute_spegla_moves


def make_tree(tmp_path):
    source = tmp_path / "nerladdat"
    target = tmp_path / "framkallat"
    raw_dir = source / "261031" / "1-Furustigens_trappa"
    raw_dir.mkdir(parents=True)
    target.mkdir()
    raw = raw_dir / "261031_103851.Dixi.NEF"
    raw.write_bytes(b"raw")
    (raw_dir / "261031_103851.Dixi.xmp").write_text("xmp")
    photo = target / "261031_103851_Dixi.jpg"
    photo.write_bytes(b"jpg")
    (target / "261031_103851_Dixi.xmp").write_text("xmp")
    return source, target, photo


def test_compute_spegla_moves_exact_token(tmp_path):
    source, target, photo = make_tree(tmp_path)
    safe, unresolved = compute_spegla_moves(source, target)

    assert [(s.name, t.name) for s, t in safe] == [(photo.name, photo.name)]
    assert safe[0][1].parent == target / "261031" / "1-Furustigens_trappa"
    assert unresolved == []


def test_compute_spegla_moves_reports_unresolved(tmp_path):
    source, target, photo = make_tree(tmp_path)
    (raw_dir := source / "261031" / "2-Lamberget").mkdir(parents=True)
    (raw_dir / "261031_103851.Dixi.NEF").write_bytes(b"raw")
    other = target / "991231_000000_Unknown.jpg"
    other.write_bytes(b"jpg")

    safe, unresolved = compute_spegla_moves(source, target)

    assert safe == []  # ambiguous token: the same timestamp in two source folders
    assert {p.name for p in unresolved} == {photo.name, other.name}


def test_flytta_spegla_dry_run_does_not_move(tmp_path, capsys):
    source, target, photo = make_tree(tmp_path)
    assert main(["flytta", "-n", "--spegla", "--kallrot", str(source), str(target)]) == 0
    out = capsys.readouterr()
    assert "Safe: 1, unresolved: 0" in out.out
    assert "(dry)" in out.out
    assert photo.exists()
    assert not (target / "261031" / "1-Furustigens_trappa" / photo.name).exists()


def test_flytta_spegla_moves_image_and_sidecar(tmp_path):
    source, target, photo = make_tree(tmp_path)
    assert main(["flytta", "--spegla", "--kallrot", str(source), str(target)]) == 0

    moved = target / "261031" / "1-Furustigens_trappa" / photo.name
    assert moved.read_bytes() == b"jpg"
    assert moved.with_suffix(".xmp").read_text() == "xmp"
    assert not photo.exists()
    assert not (target / "261031_103851_Dixi.xmp").exists()


def test_flytta_rejects_overlapping_roots(tmp_path):
    source, _target, _photo = make_tree(tmp_path)
    with pytest.raises(SystemExit, match="must not overlap"):
        main(["flytta", "--spegla", "--kallrot", str(source), str(source)])


def test_flytta_requires_a_mode(tmp_path):
    _source, target, _photo = make_tree(tmp_path)
    with pytest.raises(SystemExit, match="no mode given"):
        main(["flytta", str(target)])
