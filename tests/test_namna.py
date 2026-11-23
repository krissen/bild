from pathlib import Path
from types import SimpleNamespace

import pytest

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


def test_compute_renames_same_second_same_extension_gets_distinct_slots():
    first = Path("/tmp/DSC_0001.jpg")
    second = Path("/tmp/DSC_0002.jpg")
    renames = namna.compute_renames(
        [("260101_120000", "0", first), ("260101_120000", "0", second)]
    )
    assert [dst.name for _src, dst in renames] == [
        "260101_120000-00.jpg",
        "260101_120000-01.jpg",
    ]


def test_cli_namna_does_not_rename_attached_sidecar_twice(tmp_path, monkeypatch):
    raw = tmp_path / "DSC_0001.NEF"
    sidecar = tmp_path / "DSC_0001.xmp"
    raw.write_bytes(b"raw")
    sidecar.write_text("xmp")
    monkeypatch.setattr(
        namna,
        "exif_dates",
        lambda files: {
            raw.resolve(): ("260101_120000", "00"),
            sidecar.resolve(): ("260101_120000", "00"),
        },
    )

    assert main(["namna", str(raw), str(sidecar)]) == 0
    assert (tmp_path / "260101_120000.NEF").exists()
    assert (tmp_path / "260101_120000.xmp").read_text() == "xmp"


def test_compute_renames_raw_and_jpeg_share_one_stem():
    raw = Path("/tmp/DSC_0001.NEF")
    jpg = Path("/tmp/DSC_0001.jpg")
    renames = namna.compute_renames(
        [("260101_120000", "00", raw), ("260101_120000", "00", jpg)]
    )
    assert [dst.name for _src, dst in renames] == ["260101_120000.NEF", "260101_120000.jpg"]


def test_cli_namna_include_named_orders_dependencies(tmp_path, monkeypatch):
    first = tmp_path / "260101_120000.jpg"
    second = tmp_path / "260101_120000-00.jpg"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    monkeypatch.setattr(
        namna,
        "exif_dates",
        lambda files: {
            first.resolve(): ("260101_120000", "01"),
            second.resolve(): ("260101_120000", "02"),
        },
    )

    assert main(["namna", "--include-named", str(first), str(second)]) == 0
    assert (tmp_path / "260101_120000-00.jpg").read_bytes() == b"first"
    assert (tmp_path / "260101_120000-01.jpg").read_bytes() == b"second"


def test_cli_namna_dry_run_allows_dependent_renames(tmp_path, monkeypatch, capsys):
    first = tmp_path / "260101_120000.jpg"
    second = tmp_path / "260101_120000-00.jpg"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    monkeypatch.setattr(
        namna,
        "exif_dates",
        lambda files: {
            first.resolve(): ("260101_120000", "01"),
            second.resolve(): ("260101_120000", "02"),
        },
    )

    assert main(["namna", "--include-named", "-n", str(first), str(second)]) == 0
    out = capsys.readouterr().out
    assert "SKIP" not in out
    assert "(dry)" in out
    assert first.exists() and second.exists()


def test_plan_attaches_sidecar_for_non_nef_raw(tmp_path):
    raw = tmp_path / "DSC_0001.CR3"
    sidecar = tmp_path / "DSC_0001.xmp"
    raw.write_bytes(b"raw")
    sidecar.write_text("xmp")

    plan = namna.build_move_plan([("260101_120000", "00", raw)])
    assert namna.execute_renames(plan, dry_run=False) == (1, 0)
    assert (tmp_path / "260101_120000.xmp").read_text() == "xmp"


def test_plan_freezes_sidecar_associations(tmp_path):
    raw = tmp_path / "DSC_0001.NEF"
    sidecar = tmp_path / "DSC_0001.xmp"
    jpg = tmp_path / "260101_120000.jpg"
    raw.write_bytes(b"raw")
    sidecar.write_text("xmp")
    jpg.write_bytes(b"jpg")
    entries = [
        ("260101_120000", "00", raw),
        ("260101_120000", "00", sidecar),
        ("260101_120100", "00", jpg),
    ]

    plan = namna.build_move_plan(entries)
    assert namna.execute_renames(plan, dry_run=False) == (2, 0)
    assert (tmp_path / "260101_120000.xmp").read_text() == "xmp"
    assert not (tmp_path / "260101_120100.xmp").exists()


def test_execute_renames_moves_shared_sidecar_once(tmp_path):
    raw = tmp_path / "DSC_0001.NEF"
    jpg = tmp_path / "DSC_0001.jpg"
    sidecar = tmp_path / "DSC_0001.xmp"
    for path in (raw, jpg):
        path.write_bytes(b"x")
    sidecar.write_text("xmp")
    plan = namna.build_move_plan(
        [("260101_120000", "00", raw), ("260101_120000", "00", jpg)]
    )

    assert namna.execute_renames(plan, dry_run=False) == (2, 0)
    assert (tmp_path / "260101_120000.xmp").read_text() == "xmp"
    assert not sidecar.exists()


def test_execute_renames_moves_sidecar(tmp_path):
    src = tmp_path / "DSC_0001.NEF"
    sidecar = tmp_path / "DSC_0001.xmp"
    src.write_bytes(b"raw")
    sidecar.write_text("xmp")
    dst = tmp_path / "260101_120000.NEF"

    plan = namna.build_move_plan([("260101_120000", "00", src)])
    assert namna.execute_renames(plan, dry_run=False) == (1, 0)
    assert dst.read_bytes() == b"raw"
    assert dst.with_suffix(".xmp").read_text() == "xmp"
    assert not src.exists()


def test_namna_dry_run_does_not_rename(tmp_path, capsys):
    src = tmp_path / "DSC_0001.NEF"
    src.write_bytes(b"raw")
    plan = namna.build_move_plan([("260101_120000", "00", src)])
    namna.execute_renames(plan, dry_run=True)
    assert "(dry)" in capsys.readouterr().out
    assert src.exists()


def test_exif_dates_treats_status_2_as_no_dates(monkeypatch):
    monkeypatch.setattr(
        namna.subprocess,
        "run",
        lambda command, **kwargs: SimpleNamespace(returncode=2, stdout="", stderr=""),
    )
    assert namna.exif_dates([Path("/tmp/DSC_0001.NEF")]) == {}


def test_cli_namna_status_2_is_not_an_error(tmp_path, monkeypatch, capsys):
    src = tmp_path / "DSC_0001.NEF"
    src.write_bytes(b"raw")
    monkeypatch.setattr(
        namna.subprocess,
        "run",
        lambda command, **kwargs: SimpleNamespace(returncode=2, stdout="", stderr=""),
    )
    assert main(["namna", str(src)]) == 0
    assert "without EXIF date: 1" in capsys.readouterr().out


def test_exif_dates_reports_exiftool_failure(monkeypatch):
    monkeypatch.setattr(
        namna.subprocess,
        "run",
        lambda command, **kwargs: SimpleNamespace(returncode=1, stdout="", stderr="corrupt NEF"),
    )
    with pytest.raises(RuntimeError, match="corrupt NEF"):
        namna.exif_dates([Path("/tmp/DSC_0001.NEF")])


def test_cli_namna_propagates_exif_failure(tmp_path, monkeypatch, capsys):
    src = tmp_path / "DSC_0001.NEF"
    src.write_bytes(b"raw")
    monkeypatch.setattr(
        namna.subprocess,
        "run",
        lambda command, **kwargs: SimpleNamespace(returncode=1, stdout="", stderr="corrupt NEF"),
    )
    assert main(["namna", str(src)]) == 1
    assert "corrupt NEF" in capsys.readouterr().err
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
