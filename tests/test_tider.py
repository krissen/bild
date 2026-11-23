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
