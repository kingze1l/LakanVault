"""Tray status + controller (GUI-free; pystray wraps this)."""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


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
    """Start/stop gateway + open status/review panels. Inject callables for tests."""

    def __init__(self, *, host: str = "127.0.0.1", port: int = 8080) -> None:
        self._host = host
        self._port = port
        self._status = TrayStatus.STOPPED
        self._last_event_id = 0
        self._paused = False

    @property
    def status(self) -> TrayStatus:
        return self._status

    @property
    def dashboard_url(self) -> str:
        """Status panel URL (tray default)."""
        return f"http://{self._host}:{self._port}/status"

    @property
    def review_url(self) -> str:
        return f"http://{self._host}:{self._port}/review"

    @property
    def last_event_id(self) -> int:
        return self._last_event_id

    @property
    def paused(self) -> bool:
        return self._paused

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

    def open_review(self, open_fn: Callable[[str], None]) -> None:
        open_fn(self.review_url)

    def poll_protect_events(
        self,
        fetch_json: Callable[[str], dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch new protect events since last poll. Updates last_event_id + paused."""
        url = (
            f"http://{self._host}:{self._port}/api/protect/recent"
            f"?since_id={self._last_event_id}&limit=50"
        )
        getter = fetch_json or _http_get_json
        try:
            payload = getter(url)
        except Exception as exc:
            logger.debug("protect poll failed: %s", exc)
            return []
        events = list(payload.get("events") or [])
        if events:
            self._last_event_id = max(int(e.get("id", 0)) for e in events)
        try:
            stats = getter(f"http://{self._host}:{self._port}/api/protect/stats")
            self._paused = bool(stats.get("paused"))
        except Exception:
            pass
        return events

    def notify_for_events(
        self,
        events: list[dict[str, Any]],
        notify_fn: Callable[[str, str], None],
    ) -> list[dict[str, Any]]:
        """Notify for warn/mask/block; skip when paused. Returns notified events."""
        if self._paused:
            return []
        notified: list[dict[str, Any]] = []
        for ev in events:
            action = str(ev.get("action") or "").lower()
            if action not in {"warn", "mask", "block"}:
                continue
            types = ", ".join(ev.get("entity_types") or []) or "finding"
            title = f"LakanVault — {action.upper()}"
            body = f"{types} ({ev.get('source', 'protect')})"
            notify_fn(title, body)
            notified.append(ev)
            if action == "block":
                self._status = TrayStatus.ERROR
            elif action in ("warn", "mask") and self._status == TrayStatus.RUNNING:
                self._status = TrayStatus.WARNING
        return notified


def _http_get_json(url: str) -> dict[str, Any]:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=2.0) as resp:  # noqa: S310 — loopback daemon
        raw = resp.read().decode("utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("expected JSON object")
    return data
