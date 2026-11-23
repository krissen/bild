from pathlib import Path

from bild import namna
from bild.cli import main


def test_compute_renames_sole_file_bare_name():
    src = Path("/tmp/DSC_0001.NEF")
    assert namna.compute_renames([("260101_120000", "00", src)]) == [
        (src, src.parent / "260101_120000.NEF")
    ]


def test_compute_renames_same_second_gets_numbered():
    a, b = Path("/tmp/DSC_0001.NEF"), Path("/tmp/DSC_0002.NEF")
    renames = namna.compute_renames(
        [("260101_120000", "01", a), ("260101_120000", "02", b)]
    )
    assert [dst.name for _src, dst in renames] == ["260101_120000-00.NEF", "260101_120000-01.NEF"]


def test_compute_renames_protected_file_reserves_bare_slot():
    named, unnamed = Path("/tmp/260101_120000_Linda.NEF"), Path("/tmp/DSC_0002.NEF")
    renames = namna.compute_renames(
        [("260101_120000", "01", named), ("260101_120000", "02", unnamed)]
    )
    assert len(renames) == 1
    assert renames[0][0] == unnamed
    assert renames[0][1].name == "260101_120000-00.NEF"


def test_execute_renames_moves_sidecar(tmp_path):
    src = tmp_path / "DSC_0001.NEF"
    sidecar = tmp_path / "DSC_0001.xmp"
    src.write_bytes(b"raw")
    sidecar.write_text("xmp")
    dst = tmp_path / "260101_120000.NEF"

    assert namna.execute_renames([(src, dst)], dry_run=False) == (1, 0)
    assert dst.read_bytes() == b"raw"
    assert dst.with_suffix(".xmp").read_text() == "xmp"
    assert not src.exists()


def test_namna_dry_run_does_not_rename(tmp_path, capsys):
    src = tmp_path / "DSC_0001.NEF"
    src.write_bytes(b"raw")
    namna.execute_renames([(src, tmp_path / "260101_120000.NEF")], dry_run=True)
    assert "(dry)" in capsys.readouterr().out
    assert src.exists()


def test_cli_namna_uses_exif_dates(tmp_path, monkeypatch):
    src = tmp_path / "DSC_0001.NEF"
    src.write_bytes(b"raw")
    monkeypatch.setattr(
        namna, "exif_dates", lambda files: {src.resolve(): ("260101_120000", "00")}
    )
    assert main(["namna", "-n", str(src)]) == 0
    assert src.exists()


def test_auto_detected_namna_only_asks(tmp_path, monkeypatch, capsys):
    import pytest

    root = tmp_path / "raws"
    root.mkdir()
    src = root / "DSC_0001.NEF"
    src.write_bytes(b"raw")
    monkeypatch.setattr(
        namna, "exif_dates", lambda files: {src.resolve(): ("260101_120000", "00")}
    )
    with pytest.raises(SystemExit, match="namna"):
        main(["flytta", str(root)])
    assert "Auto:" in capsys.readouterr().out
    assert src.exists()
