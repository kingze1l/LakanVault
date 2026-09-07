"""Tray status + controller (GUI-free; pystray wraps this)."""
from __future__ import annotations

from enum import Enum
from typing import Callable


class TrayStatus(Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    WARNING = "warning"
    ERROR = "error"

    @property
    def color_rgb(self) -> tuple[int, int, int]:
        return {
            TrayStatus.STOPPED: (120, 120, 120),
            TrayStatus.STARTING: (120, 120, 120),
            TrayStatus.RUNNING: (0, 180, 80),
            TrayStatus.WARNING: (220, 160, 40),
            TrayStatus.ERROR: (220, 60, 60),
        }[self]


class TrayController:
    """Start/stop gateway + open dashboard. Inject callables for tests."""

    def __init__(self, *, host: str = "127.0.0.1", port: int = 8080) -> None:
        self._host = host
        self._port = port
        self._status = TrayStatus.STOPPED

    @property
    def status(self) -> TrayStatus:
        return self._status

    @property
    def dashboard_url(self) -> str:
        return f"http://{self._host}:{self._port}/"

    def set_status(self, status: TrayStatus) -> None:
        self._status = status

    def start_gateway(self, start_fn: Callable[[], bool]) -> bool:
        self._status = TrayStatus.STARTING
        ok = bool(start_fn())
        self._status = TrayStatus.RUNNING if ok else TrayStatus.ERROR
        return ok

    def stop_gateway(self, stop_fn: Callable[[], bool]) -> bool:
        ok = bool(stop_fn())
        self._status = TrayStatus.STOPPED
        return ok

    def open_dashboard(self, open_fn: Callable[[str], None]) -> None:
        open_fn(self.dashboard_url)
