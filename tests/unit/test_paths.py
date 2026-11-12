# frozen vs dev paths never write into _MEIPASS
from pathlib import Path

from lakanvault.shared import paths
from lakanvault.shared.config import resolve_config_dir


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


def test_resolve_config_dir_frozen_mcp_layout(monkeypatch, tmp_path: Path) -> None:
    # Cursor cwd = demo-workspace; mcp.exe lives under MVP/mcp/
    mvp = tmp_path / "LakanVault-MVP"
    demo = mvp / "demo-workspace"
    mcp_dir = mvp / "mcp"
    bundled = mcp_dir / "_internal" / "config"
    bundled.mkdir(parents=True)
    demo.mkdir(parents=True)
    (bundled / "default.yaml").write_text("cloud:\n  enabled: false\n", encoding="utf-8")
    exe = mcp_dir / "lakanvault-mcp-server.exe"
    monkeypatch.setattr(paths.sys, "frozen", True, raising=False)
    monkeypatch.setattr(paths.sys, "executable", str(exe), raising=False)
    monkeypatch.setattr(paths.sys, "_MEIPASS", str(mcp_dir / "_internal"), raising=False)
    monkeypatch.chdir(demo)
    found = resolve_config_dir("./config")
    assert found == bundled.resolve()
    assert (found / "default.yaml").is_file()
