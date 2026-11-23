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


def test_flytta_autodetects_spegla(tmp_path, capsys):
    source, target, photo = make_tree(tmp_path)
    assert main(["flytta", "-n", "--kallrot", str(source), str(target)]) == 0
    out = capsys.readouterr().out
    assert "Auto:" in out and "matchande källor" in out
    assert "(dry)" in out
    assert photo.exists()


def test_flytta_autodetects_datum(tmp_path, capsys):
    root = make_datum_tree(tmp_path)
    assert main(["flytta", "-n", str(root)]) == 0
    out = capsys.readouterr().out
    assert "Auto:" in out and "datummärkta raw-" in out
    assert "(dry)" in out
    assert (root / "260101_090000.NEF").exists()


def test_flytta_asks_for_namna_on_dsc_raws(tmp_path, capsys):
    root = tmp_path / "raws"
    root.mkdir()
    (root / "DSC_0001.NEF").write_bytes(b"raw")
    with pytest.raises(SystemExit, match="namna"):
        main(["flytta", str(root)])
    assert "DSC_-raws" in capsys.readouterr().out


def test_flytta_refuses_ambiguous_input(tmp_path):
    root = make_datum_tree(tmp_path)
    (root / "261030_090000.jpg").write_bytes(b"jpg")
    with pytest.raises(SystemExit, match="ambiguous input"):
        main(["flytta", str(root)])
    assert (root / "260101_090000.NEF").exists()


def make_datum_tree(tmp_path):
    root = tmp_path / "raws"
    root.mkdir()
    for name in ("260101_090000.NEF", "260101_100000.NEF", "260102_090000.NEF"):
        (root / name).write_bytes(b"raw")
    (root / "260101_090000.xmp").write_text("xmp")
    return root


def test_compute_datum_moves_groups_and_filters(tmp_path):
    root = make_datum_tree(tmp_path)
    from bild.flytta import compute_datum_moves

    groups = compute_datum_moves(root)
    assert [len(v) for v in groups.values()] == [2, 1]
    assert groups["260101"][0][1][0].name == "260101_090000.xmp"

    filtered = compute_datum_moves(root, from_date="260102")
    assert list(filtered) == ["260102"]


def test_flytta_datum_moves_into_date_folders(tmp_path):
    root = make_datum_tree(tmp_path)
    (root / "DSC_0001.NEF").write_bytes(b"raw")
    assert main(["flytta", "--datum", str(root)]) == 0
    assert (root / "260101" / "260101_090000.NEF").exists()
    assert (root / "260101" / "260101_090000.xmp").exists()
    assert (root / "260102" / "260102_090000.NEF").exists()
    assert (root / "DSC_0001.NEF").exists()  # no date prefix: untouched


def test_flytta_datum_dry_run_does_not_move(tmp_path):
    root = make_datum_tree(tmp_path)
    assert main(["flytta", "-n", "--datum", str(root)]) == 0
    assert (root / "260101_090000.NEF").exists()
    assert not (root / "260101").exists()


def test_flytta_rejects_invalid_date(tmp_path):
    root = make_datum_tree(tmp_path)
    with pytest.raises(SystemExit, match="unknown date format"):
        main(["flytta", "--datum", "--fore", "not-a-date", str(root)])
