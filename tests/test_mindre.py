from types import SimpleNamespace

from bild import mindre
from bild.cli import main


def test_mindre_passes_size_and_files(monkeypatch):
    captured = {}
    monkeypatch.setattr(mindre.shutil, "which", lambda name: "/usr/bin/gor_mindre")

    def fake_run(command, **kwargs):
        captured["command"] = command
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(mindre.subprocess, "run", fake_run)
    assert main(["mindre", "2800", "a.jpg"]) == 0
    command = captured["command"]
    assert command[:2] == ["/usr/bin/gor_mindre", "--size"]
    assert command[2] == "2800"
    assert "a.jpg" in command


def test_mindre_reports_missing_tool(monkeypatch, capsys):
    monkeypatch.setattr(mindre.shutil, "which", lambda name: None)
    assert main(["mindre", "100", "a.jpg"]) == 1
    assert "gor_mindre" in capsys.readouterr().err
