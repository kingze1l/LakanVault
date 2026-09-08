"""Launcher readiness helpers."""
from __future__ import annotations

from lakanvault.launcher import bootstrap


def test_wait_for_url_ready_uses_longer_timeout_when_frozen(monkeypatch) -> None:
    calls: list[tuple[str, int, float]] = []

    def fake_wait(url: str, attempts: int = 40, delay: float = 0.15) -> bool:
        calls.append((url, attempts, delay))
        return True

    monkeypatch.setattr(bootstrap, "wait_for_url", fake_wait)
    monkeypatch.setattr(bootstrap.sys, "frozen", True, raising=False)
    assert bootstrap.wait_for_url_ready("http://127.0.0.1:8080") is True
    assert calls == [("http://127.0.0.1:8080", 180, 0.5)]


def test_wait_for_url_ready_dev_default(monkeypatch) -> None:
    calls: list[tuple] = []

    def fake_wait(url: str, attempts: int = 40, delay: float = 0.15) -> bool:
        calls.append((url, attempts, delay))
        return False

    monkeypatch.setattr(bootstrap, "wait_for_url", fake_wait)
    monkeypatch.setattr(bootstrap.sys, "frozen", False, raising=False)
    assert bootstrap.wait_for_url_ready("http://127.0.0.1:8080") is False
    assert calls[0][1] == 40
