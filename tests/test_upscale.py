from types import SimpleNamespace

from bild import upscale
from bild.cli import main


def test_upscale_passes_flags_through(monkeypatch):
    captured = {}
    def fake_run(arguments):
        captured["arguments"] = arguments
        return 0

    monkeypatch.setattr(upscale, "run_upscale", fake_run)
    assert main(["upscale", "-m", "x4plus", "--half", "in.png"]) == 0
    assert captured["arguments"] == ["-m", "x4plus", "--half", "in.png"]


def test_upscale_reports_missing_interpreter(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("BILD_UPSCALE_PYTHON", str(tmp_path / "missing"))
    assert upscale.run_upscale([]) == 1
    assert "hittas inte" in capsys.readouterr().err


def test_upscale_invokes_env_interpreter(monkeypatch, tmp_path):
    python = tmp_path / "python"
    python.write_text("")
    script = tmp_path / "gor_upscale.py"
    script.write_text("")
    monkeypatch.setenv("BILD_UPSCALE_PYTHON", str(python))
    monkeypatch.setenv("BILD_UPSCALE_SCRIPT", str(script))
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(upscale.subprocess, "run", fake_run)
    assert upscale.run_upscale(["--models"]) == 0
    assert captured["command"] == [str(python), str(script), "--models"]
