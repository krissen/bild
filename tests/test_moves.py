from pathlib import Path

import pytest

from bild.moves import (
    extract_timestamp,
    find_sidecar_files,
    move_unit,
    order_moves,
    preflight_destinations,
)


def test_extract_timestamp():
    assert extract_timestamp("260101_120000_Linda.jpg")[0] == "260101_120000"
    assert extract_timestamp("260101_120000.jpg")[0] == "260101_120000"
    assert extract_timestamp("DSC_1234.NEF") is None
    assert extract_timestamp("260199_999999.jpg") is None


def test_order_moves_handles_a_chain_of_three(tmp_path):
    paths = [tmp_path / f"a{index}.jpg" for index in range(3)]
    moves = [(paths[0], paths[1], []), (paths[1], paths[2], []), (paths[2], tmp_path / "z.jpg", [])]

    ordered = order_moves(moves)
    assert [source.name for source, _target, _scs in ordered] == ["a2.jpg", "a1.jpg", "a0.jpg"]


def test_find_sidecar_files_matches_stem_literally(tmp_path):
    raw = tmp_path / "DSC_[1].NEF"
    real = tmp_path / "DSC_[1].xmp"
    decoy = tmp_path / "DSC_1.xmp"
    raw.write_bytes(b"raw")
    real.write_text("real")
    decoy.write_text("decoy")

    assert find_sidecar_files(raw) == [real]


def test_move_unit_moves_main_and_sidecar(tmp_path):
    main = tmp_path / "260101_120000.jpg"
    sidecar = tmp_path / "260101_120000.xmp"
    main.write_bytes(b"jpg")
    sidecar.write_text("xmp")
    outdir = tmp_path / "out"
    outdir.mkdir()

    moved = move_unit(main, outdir / main.name, [(sidecar, outdir / sidecar.name)])

    assert len(moved) == 2
    assert (outdir / main.name).read_bytes() == b"jpg"
    assert (outdir / sidecar.name).read_text() == "xmp"
    assert not main.exists() and not sidecar.exists()


def test_move_unit_refuses_overwrite(tmp_path):
    src = tmp_path / "a.jpg"
    dst = tmp_path / "out" / "a.jpg"
    src.write_bytes(b"new")
    dst.parent.mkdir()
    dst.write_bytes(b"old")

    with pytest.raises(FileExistsError):
        move_unit(src, dst)
    assert src.read_bytes() == b"new"
    assert dst.read_bytes() == b"old"


def test_move_unit_refuses_symlink_alias_target(tmp_path):
    real = tmp_path / "260101_120000.NEF"
    alias = tmp_path / "DSC_0001.NEF"
    real.write_bytes(b"original")
    alias.symlink_to(real.name)

    with pytest.raises(FileExistsError):
        move_unit(alias, real)

    assert real.read_bytes() == b"original"
    assert alias.is_symlink()


def test_move_unit_rolls_back_when_a_sidecar_target_is_blocked(tmp_path):
    main = tmp_path / "a.jpg"
    sidecar = tmp_path / "a.xmp"
    main.write_bytes(b"jpg")
    sidecar.write_text("xmp")
    outdir = tmp_path / "out"
    outdir.mkdir()
    (outdir / "a.xmp").write_text("pre-existing")

    with pytest.raises(FileExistsError):
        move_unit(main, outdir / "a.jpg", [(sidecar, outdir / "a.xmp")])

    assert main.read_bytes() == b"jpg"
    assert sidecar.read_text() == "xmp"
    assert not (outdir / "a.jpg").exists()
    assert (outdir / "a.xmp").read_text() == "pre-existing"


def test_preflight_detects_existing_and_collisions(tmp_path):
    existing = tmp_path / "a.jpg"
    existing.write_bytes(b"x")
    assert "already exists" in preflight_destinations([existing])

    target = tmp_path / "out" / "a.jpg"
    assert preflight_destinations([target]) is None
    assert "collision" in preflight_destinations([target, Path(str(target).upper())])
