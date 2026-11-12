# flyout host / panel bits without real pywebview
from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

from lakanvault.tray import panel as panel_mod
from lakanvault.tray.panel import (
    FlyoutHost,
    flyout_anchor,
    flyout_size,
    reset_flyout_host_for_tests,
    work_area_rect,
)

# wipe flyout host between tests
@pytest.fixture(autouse=True)
def _fresh_host() -> None:
    reset_flyout_host_for_tests()
    yield
    reset_flyout_host_for_tests()

# stand-in window so we dont need real gui
class _FakeWindow:
    def __init__(self) -> None:
        self.shown = False
        self.hidden = False
        self.destroyed = False
        self.moved: list[tuple[int, int]] = []
        self.loaded_url: str | None = None
        self.current_url = "http://127.0.0.1:8080/status"
        self.js: list[str] = []

    def show(self) -> None:
        self.shown = True
        self.hidden = False

    def hide(self) -> None:
        self.hidden = True
        self.shown = False

    def destroy(self) -> None:
        self.destroyed = True

    def move(self, x: int, y: int) -> None:
        self.moved.append((x, y))

    def load_url(self, url: str) -> None:
        self.loaded_url = url
        self.current_url = url

    def get_current_url(self) -> str:
        return self.current_url

    def evaluate_js(self, script: str) -> None:
        self.js.append(script)

# wire fake window onto a prepared host
def _attach_prepared(host: FlyoutHost, fake: _FakeWindow) -> None:
    host._window = fake  # noqa: SLF001
    host._prepared = True  # noqa: SLF001
    host._ready.set()
    host._visible = False


def test_flyout_anchor_returns_ints() -> None:
    x, y = flyout_anchor(380, 520)
    assert isinstance(x, int) and isinstance(y, int)


def test_flyout_size_fits_work_area() -> None:
    left, top, right, bottom = work_area_rect()
    aw, ah = right - left, bottom - top
    w, h = flyout_size(380, 580)
    assert w <= aw - 24
    assert h <= ah - 24
    assert w >= 260 and h >= 300


def test_flyout_size_shrinks_on_tiny_screen(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(panel_mod, "work_area_rect", lambda: (0, 0, 800, 500))
    w, h = flyout_size(380, 580)
    assert w <= 800 - 24
    assert h <= 500 - 24


def test_toggle_show_hide_with_fake_window() -> None:
    host = FlyoutHost()
    fake = _FakeWindow()
    _attach_prepared(host, fake)

    host.toggle("http://127.0.0.1:8080/status")
    assert host.visible is True
    assert fake.shown is True
    assert fake.moved

    host.toggle("http://127.0.0.1:8080/status")
    assert host.visible is False
    assert fake.hidden is True

    host.show("http://127.0.0.1:8080/status")
    assert host.visible is True


def test_blur_dismiss_hides_after_delay() -> None:
    host = FlyoutHost()
    fake = _FakeWindow()
    _attach_prepared(host, fake)
    host._visible = True  # noqa: SLF001
    host._ignore_blur_until = 0.0  # noqa: SLF001 — grace already expired
    fake.shown = True

    host.dismiss_from_blur()
    assert host.visible is True
    time.sleep(0.55)
    assert host.visible is False
    assert fake.hidden is True

# blur during show grace shouldnt hide yet
def test_blur_ignored_during_show_grace() -> None:
    host = FlyoutHost()
    fake = _FakeWindow()
    _attach_prepared(host, fake)
    host.show("http://127.0.0.1:8080/status")
    assert host.visible is True
    host.dismiss_from_blur()
    time.sleep(0.2)
    assert host.visible is True



def test_toggle_cancels_pending_blur_hide() -> None:
    host = FlyoutHost()
    fake = _FakeWindow()
    _attach_prepared(host, fake)
    host._visible = True  # noqa: SLF001
    fake.shown = True

    host.dismiss_from_blur()
    host.toggle("http://127.0.0.1:8080/status")
    assert host.visible is False
    time.sleep(0.25)
    assert host.visible is False


def test_closing_hides_unless_shutdown() -> None:
    host = FlyoutHost()
    fake = _FakeWindow()
    _attach_prepared(host, fake)
    host._visible = True  # noqa: SLF001
    assert host._on_closing() is False  # noqa: SLF001
    assert host.visible is False
    assert fake.hidden is True

    host._allow_destroy = True  # noqa: SLF001
    assert host._on_closing() is True  # noqa: SLF001


def test_unprepared_host_falls_back_to_open_fn() -> None:
    host = FlyoutHost()
    opened: list[str] = []
    host.show("http://127.0.0.1:8080/status", open_fn=lambda u: opened.append(u))
    assert opened == ["http://127.0.0.1:8080/status"]


def test_failed_host_falls_back_to_open_fn() -> None:
    host = FlyoutHost()
    opened: list[str] = []
    host._failed = True  # noqa: SLF001
    host._prepared = True  # noqa: SLF001
    host._ready.set()
    host.show("http://127.0.0.1:8080/status", open_fn=lambda u: opened.append(u))
    assert opened == ["http://127.0.0.1:8080/status"]


def test_open_panel_falls_back_when_gui_not_ready() -> None:
    opened: list[str] = []
    panel_mod.open_panel(
        "http://127.0.0.1:8080/review",
        open_fn=lambda url: opened.append(url),
    )
    assert opened == ["http://127.0.0.1:8080/review"]


def test_toggle_status_flyout_uses_process_host(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    host = reset_flyout_host_for_tests()

    def fake_toggle(url: str, *, open_fn=None) -> None:
        calls.append(url)

    monkeypatch.setattr(host, "toggle", fake_toggle)
    panel_mod.toggle_status_flyout("http://127.0.0.1:8080/status")
    assert calls == ["http://127.0.0.1:8080/status"]


def test_prepare_marks_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    host = FlyoutHost()
    fake = _FakeWindow()

    class _Ev:
        def __iadd__(self, fn):  # noqa: ANN001
            return self

    fake.events = SimpleNamespace(closing=_Ev(), loaded=_Ev())
    fake.expose = lambda *a, **k: None

    monkeypatch.setitem(
        __import__("sys").modules,
        "webview",
        SimpleNamespace(
            create_window=lambda *a, **k: fake,
            start=lambda: None,
            screens=[],
        ),
    )
    assert host.prepare("http://127.0.0.1:8080/status") is True
    assert host.gui_ready is True
    assert host.visible is False
