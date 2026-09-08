"""Launcher readiness helpers."""
from __future__ import annotations

from pathlib import Path

from lakanvault.launcher import bootstrap


def test_seed_bundled_config_copies_default_when_frozen(monkeypatch, tmp_path: Path) -> None:
    meipass = tmp_path / "_internal"
    (meipass / "config").mkdir(parents=True)
    (meipass / "config" / "default.yaml").write_text("local: {}\n", encoding="utf-8")
    exe = tmp_path / "LakanVault.exe"
    root = tmp_path
    monkeypatch.setattr(bootstrap.sys, "frozen", True, raising=False)
    monkeypatch.setattr(bootstrap.sys, "executable", str(exe), raising=False)
    monkeypatch.setattr(bootstrap.sys, "_MEIPASS", str(meipass), raising=False)

    bootstrap.ensure_data_dirs(root)
    dest = root / "config" / "default.yaml"
    assert dest.is_file()
    assert "local:" in dest.read_text(encoding="utf-8")


def test_seed_bundled_config_does_not_overwrite(monkeypatch, tmp_path: Path) -> None:
    meipass = tmp_path / "_internal"
    (meipass / "config").mkdir(parents=True)
    (meipass / "config" / "default.yaml").write_text("bundled: true\n", encoding="utf-8")
    exe = tmp_path / "LakanVault.exe"
    (tmp_path / "config").mkdir()
    existing = tmp_path / "config" / "default.yaml"
    existing.write_text("user: true\n", encoding="utf-8")
    monkeypatch.setattr(bootstrap.sys, "frozen", True, raising=False)
    monkeypatch.setattr(bootstrap.sys, "executable", str(exe), raising=False)
    monkeypatch.setattr(bootstrap.sys, "_MEIPASS", str(meipass), raising=False)

    bootstrap.seed_bundled_config(tmp_path)
    assert existing.read_text(encoding="utf-8") == "user: true\n"


def test_wait_for_url_ready_uses_longer_timeout_when_frozen(monkeypatch) -> None:
    calls: list[tuple[str, int, float]] = []

    def fake_wait(url: str, attempts: int = 40, delay: float = 0.15) -> bool:
        calls.append((url, attempts, delay))
        return True

    monkeypatch.setattr(bootstrap, "wait_for_url", fake_wait)
    monkeypatch.setattr(bootstrap.sys, "frozen", True, raising=False)
    assert bootstrap.wait_for_url_ready("http://127.0.0.1:8080") is True
    assert calls == [("http://127.0.0.1:8080", 120, 0.5)]


def test_wait_for_url_ready_dev_default(monkeypatch) -> None:
    calls: list[tuple] = []

    def fake_wait(url: str, attempts: int = 40, delay: float = 0.15) -> bool:
        calls.append((url, attempts, delay))
        return False

    monkeypatch.setattr(bootstrap, "wait_for_url", fake_wait)
    monkeypatch.setattr(bootstrap.sys, "frozen", False, raising=False)
    assert bootstrap.wait_for_url_ready("http://127.0.0.1:8080") is False
    assert calls[0][1] == 40


def test_frozen_daemon_command_includes_daemon_only(monkeypatch) -> None:
    monkeypatch.setattr(bootstrap.sys, "executable", r"C:\dist\LakanVault\LakanVault.exe")
    cmd = bootstrap.frozen_daemon_command("127.0.0.1", 8080)
    assert cmd[0].endswith("LakanVault.exe")
    assert "--daemon-only" in cmd
    assert "--port" in cmd
    assert "8080" in cmd
    assert "--no-runtime" in cmd
