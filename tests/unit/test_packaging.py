# packaging layout tray mcp hooks n mvp zip bits
from pathlib import Path

from lakanvault.mcp import stdio_proxy

ROOT = Path(__file__).resolve().parents[2]

# mcp console entry stays its own script
def test_build_script_keeps_mcp_console_separate() -> None:
    script = ROOT / "scripts" / "build_tray_exe.ps1"
    text = script.read_text(encoding="utf-8")
    assert "--windowed" in text
    assert "--console" in text
    assert "lakanvault-mcp" in text
    assert "LakanVault" in text
    assert "--onedir" in text
    assert "lakanvault.tray.app" in text
    assert "--exclude-module" in text
    assert "spacy" in text
    assert "smoke_frozen_exe.ps1" in text
    assert "lakanvault-mcp-server" in text
    assert "stdio_server.py" in text
    assert "lakanvault-hook-prompt" in text
    assert "lakanvault-hook-read" in text
    assert "lakanvault_prompt.py" in text
    assert "package_mvp.ps1" in text
    windowed_idx = text.index("--windowed")
    console_idx = text.index("--console")
    assert windowed_idx != console_idx


def test_package_mvp_script_layout() -> None:
    script = ROOT / "scripts" / "package_mvp.ps1"
    text = script.read_text(encoding="utf-8")
    assert "LakanVault-MVP" in text
    assert "LakanVault-MVP.zip" in text
    assert "START.bat" in text
    assert "DEMO_GUIDE.md" in text
    assert "demo-workspace" in text
    assert "lakanvault-mcp-server" in text
    assert "hook-prompt" in text
    assert "hook-read" in text
    assert "LAKANVAULT_HOOKS_DIR" in text
    assert "mode.txt" in text
    assert "run_prompt.cmd" in text
    assert "run-mcp-server.cmd" in text


def test_smoke_script_accepts_root() -> None:
    script = ROOT / "scripts" / "smoke_frozen_exe.ps1"
    text = script.read_text(encoding="utf-8")
    assert "Root" in text
    assert "LakanVault-MVP" in text
    assert "hook-prompt" in text


def test_pyproject_has_mcp_console_script() -> None:
    pyproject = ROOT / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    assert "lakanvault-mcp" in text
    assert "lakanvault.mcp.stdio_proxy:main" in text
    assert "lakanvault-mcp-server" in text
    assert "lakanvault.mcp.stdio_server:main" in text
    assert "httpx" in text
    assert "mcp>=" in text


def test_stdio_proxy_logs_go_to_stderr_constant() -> None:
    src = Path(stdio_proxy.__file__).read_text(encoding="utf-8")
    assert "stdout" in src
    assert "stderr" in src
    assert "shell=False" in src


def test_hooks_respect_hooks_dir_env() -> None:
    prompt = (ROOT / ".cursor" / "hooks" / "lakanvault_prompt.py").read_text(encoding="utf-8")
    read = (ROOT / ".cursor" / "hooks" / "lakanvault_read.py").read_text(encoding="utf-8")
    assert "LAKANVAULT_HOOKS_DIR" in prompt
    assert "LAKANVAULT_HOOKS_DIR" in read
