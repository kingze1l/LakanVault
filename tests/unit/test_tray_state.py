"""Tray state machine tests — no real pystray / GUI."""
from __future__ import annotations

from lakanvault.tray.state import TrayController, TrayStatus


def test_initial_status_is_stopped() -> None:
    ctl = TrayController(host="127.0.0.1", port=8080)
    assert ctl.status == TrayStatus.STOPPED
    assert ctl.dashboard_url == "http://127.0.0.1:8080/"


def test_start_sets_running_when_ready() -> None:
    started: list[bool] = []

    def start() -> bool:
        started.append(True)
        return True

    ctl = TrayController(host="127.0.0.1", port=8080)
    assert ctl.start_gateway(start) is True
    assert started == [True]
    assert ctl.status == TrayStatus.RUNNING


def test_start_sets_error_when_ready_fails() -> None:
    ctl = TrayController(host="127.0.0.1", port=8080)
    assert ctl.start_gateway(lambda: False) is False
    assert ctl.status == TrayStatus.ERROR


def test_stop_returns_to_stopped() -> None:
    stopped: list[bool] = []
    ctl = TrayController(host="127.0.0.1", port=8080)
    ctl.start_gateway(lambda: True)
    ctl.stop_gateway(lambda: stopped.append(True) or True)
    assert stopped == [True]
    assert ctl.status == TrayStatus.STOPPED


def test_set_status_warning_and_error() -> None:
    ctl = TrayController(host="127.0.0.1", port=9090)
    ctl.set_status(TrayStatus.WARNING)
    assert ctl.status == TrayStatus.WARNING
    ctl.set_status(TrayStatus.ERROR)
    assert ctl.status == TrayStatus.ERROR
    assert ctl.dashboard_url == "http://127.0.0.1:9090/"


def test_open_dashboard_calls_opener() -> None:
    opened: list[str] = []
    ctl = TrayController(host="127.0.0.1", port=8080)
    ctl.open_dashboard(lambda url: opened.append(url))
    assert opened == ["http://127.0.0.1:8080/"]


def test_status_color_map() -> None:
    assert TrayStatus.RUNNING.color_rgb == (0, 180, 80)
    assert TrayStatus.WARNING.color_rgb == (220, 160, 40)
    assert TrayStatus.ERROR.color_rgb == (220, 60, 60)
    assert TrayStatus.STOPPED.color_rgb == (120, 120, 120)
    assert TrayStatus.STARTING.color_rgb == (120, 120, 120)
