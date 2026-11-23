from types import SimpleNamespace

import pytest

from bild import tider
from bild.cli import main


def test_parse_offset():
    assert tider.parse_offset("-01:01:00") == (-3660, "-", "01:01:00")
    assert tider.parse_offset("+00:00:30")[0] == 30
    with pytest.raises(ValueError):
        tider.parse_offset("1 hour")


def test_shifted_name_wraps_at_midnight():
    assert tider.shifted_name("250419_235900_Linda.jpg", 120) == "250419_000100_Linda.jpg"
    assert tider.shifted_name("250419_000100.jpg", -120) == "250419_235900.jpg"
    assert tider.shifted_name("DSC_0001.NEF", 60) is None


def test_tider_dry_run_changes_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    photo = tmp_path / "250419_100000_Linda.jpg"
    photo.write_bytes(b"x")
    monkeypatch.setattr(tider, "find_exiftool", lambda: pytest.fail("exiftool called in dry-run"))
    assert main(["tider", "-n", "-t", "+00:01:00", "-f", "*.jpg"]) == 0
    out = capsys.readouterr().out
    assert "250419_100000_Linda.jpg -> 250419_100100_Linda.jpg" in out
    assert photo.exists()


def test_cli_tider_accepts_negative_offset(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    photo = tmp_path / "250419_100000.jpg"
    photo.write_bytes(b"x")
    assert main(["tider", "-n", "-t", "-01:01:00", "-f", "*.jpg"]) == 0
    assert "Offset -01:01:00" in capsys.readouterr().out
    assert photo.exists()


def test_cli_tider_accepts_long_negative_offset(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    photo = tmp_path / "250419_100000.jpg"
    photo.write_bytes(b"x")
    assert main(["tider", "-n", "--offset", "-01:01:00", "-f", "*.jpg"]) == 0
    assert "Offset -01:01:00" in capsys.readouterr().out


def test_tider_rename_chain_resolves_dependencies(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    first = tmp_path / "250419_100000.jpg"
    second = tmp_path / "250419_100100.jpg"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    monkeypatch.setattr(tider, "find_exiftool", lambda: "/usr/bin/exiftool")
    monkeypatch.setattr(
        tider.subprocess,
        "run",
        lambda command, **kwargs: SimpleNamespace(returncode=0),
    )

    assert main(["tider", "-t", "+00:01:00", "-f", "*.jpg"]) == 0
    assert (tmp_path / "250419_100100.jpg").read_bytes() == b"first"
    assert (tmp_path / "250419_100200.jpg").read_bytes() == b"second"


def test_tider_external_blocker_aborts_before_exif(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "250419_100000.jpg"
    source.write_bytes(b"x")
    (tmp_path / "250419_100100.jpg").write_bytes(b"blocking")
    monkeypatch.setattr(tider, "find_exiftool", lambda: pytest.fail("exiftool called"))

    assert main(["tider", "-t", "+00:01:00", "-f", "250419_100000.jpg"]) == 2
    assert source.exists()


def test_tider_exif_failure_prevents_renames(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "250419_100000.jpg"
    source.write_bytes(b"x")
    monkeypatch.setattr(tider, "find_exiftool", lambda: "/usr/bin/exiftool")
    monkeypatch.setattr(
        tider.subprocess,
        "run",
        lambda command, **kwargs: SimpleNamespace(returncode=1),
    )

    assert main(["tider", "-t", "+00:01:00", "-f", "*.jpg"]) == 1
    assert source.exists()
    assert not (tmp_path / "250419_100100.jpg").exists()


def test_tider_renames_sidecar_with_main(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    raw = tmp_path / "260101_120000.NEF"
    sidecar = tmp_path / "260101_120000.xmp"
    raw.write_bytes(b"raw")
    sidecar.write_text("xmp")
    monkeypatch.setattr(tider, "find_exiftool", lambda: "/usr/bin/exiftool")
    monkeypatch.setattr(
        tider.subprocess,
        "run",
        lambda command, **kwargs: SimpleNamespace(returncode=0),
    )

    assert main(["tider", "-t", "+00:01:00", "-f", "*.NEF"]) == 0
    assert (tmp_path / "260101_120100.NEF").exists()
    assert (tmp_path / "260101_120100.xmp").read_text() == "xmp"
    assert not sidecar.exists()


def test_tider_applies_exif_and_renames(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    photo = tmp_path / "250419_100000_Linda.jpg"
    photo.write_bytes(b"x")
    commands = []
    monkeypatch.setattr(tider, "find_exiftool", lambda: "/usr/bin/exiftool")
    monkeypatch.setattr(
        tider.subprocess,
        "run",
        lambda command, **kwargs: commands.append(command) or SimpleNamespace(returncode=0),
    )
    assert main(["tider", "-t", "+00:01:00", "-f", "*.jpg"]) == 0
    assert (tmp_path / "250419_100100_Linda.jpg").exists()
    assert not photo.exists()
    assert commands[0][1] == "-AllDates+=00:01:00"
