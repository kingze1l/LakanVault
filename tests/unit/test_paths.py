"""Frozen vs development path helpers — never write into _MEIPASS."""
from pathlib import Path

from lakanvault.shared import paths


def test_dev_writable_is_repo_data() -> None:
    root = paths.writable_data_root()
    assert root.name == "data"
    assert "_MEIPASS" not in str(root)


def test_frozen_writable_is_beside_exe(monkeypatch, tmp_path: Path) -> None:
    exe = tmp_path / "LakanVault.exe"
    meipass = tmp_path / "_internal"
    meipass.mkdir()
    monkeypatch.setattr(paths.sys, "frozen", True, raising=False)
    monkeypatch.setattr(paths.sys, "executable", str(exe), raising=False)
    monkeypatch.setattr(paths.sys, "_MEIPASS", str(meipass), raising=False)
    writable = paths.writable_data_root()
    assert writable == exe.parent / "data"
    assert meipass not in writable.parents and writable != meipass
    bundled = paths.resource_path("lakanvault", "app", "static")
    assert bundled == meipass / "lakanvault" / "app" / "static"
