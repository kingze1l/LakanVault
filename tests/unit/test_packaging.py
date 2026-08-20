"""Packaging contract: separate daemon vs MCP console artifacts."""
from pathlib import Path

from lakanvault.mcp import stdio_proxy


def test_build_script_keeps_mcp_console_separate() -> None:
    script = Path(__file__).resolve().parents[2] / "scripts" / "build_tray_exe.ps1"
    text = script.read_text(encoding="utf-8")
    assert "--windowed" in text
    assert "--console" in text
    assert "lakanvault-mcp" in text
    assert "LakanVault" in text
    assert "--onedir" in text
    # MCP must not reuse the windowed daemon stdout.
    windowed_idx = text.index("--windowed")
    console_idx = text.index("--console")
    assert windowed_idx != console_idx


def test_pyproject_has_mcp_console_script() -> None:
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    assert "lakanvault-mcp" in text
    assert "lakanvault.mcp.stdio_proxy:main" in text
    assert "httpx" in text


def test_stdio_proxy_logs_go_to_stderr_constant() -> None:
    src = Path(stdio_proxy.__file__).read_text(encoding="utf-8")
    assert "stdout" in src
    assert "stderr" in src
    assert "shell=False" in src
