"""Teams-style Status flyout via pywebview (main-thread GUI), with browser fallback."""
from __future__ import annotations

import logging
import sys
import threading
import time
from typing import Callable

logger = logging.getLogger(__name__)

FLYOUT_WIDTH = 380
FLYOUT_HEIGHT = 520
# Tray left-click steals focus briefly; ignore blur until the flyout settles.
_SHOW_GRACE_S = 1.5
_BLUR_HIDE_DELAY_S = 0.5


def flyout_anchor(width: int = FLYOUT_WIDTH, height: int = FLYOUT_HEIGHT) -> tuple[int, int]:
    """Return top-left (x, y) for a tray-corner popup (Windows work area; else primary screen)."""
    margin = 12
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            class RECT(ctypes.Structure):
                _fields_ = [
                    ("left", wintypes.LONG),
                    ("top", wintypes.LONG),
                    ("right", wintypes.LONG),
                    ("bottom", wintypes.LONG),
                ]

            rect = RECT()
            SPI_GETWORKAREA = 0x0030
            ok = ctypes.windll.user32.SystemParametersInfoW(
                SPI_GETWORKAREA, 0, ctypes.byref(rect), 0
            )
            if ok:
                x = int(rect.right - width - margin)
                y = int(rect.bottom - height - margin)
                return max(int(rect.left), x), max(int(rect.top), y)
        except Exception as exc:  # pragma: no cover - platform quirks
            logger.debug("work-area anchor failed: %s", exc)

    try:
        import webview

        screens = list(webview.screens or [])
        if screens:
            screen = min(screens, key=lambda s: (getattr(s, "y", 0), getattr(s, "x", 0)))
            sx = int(getattr(screen, "x", 0))
            sy = int(getattr(screen, "y", 0))
            sw = int(getattr(screen, "width", width + margin))
            sh = int(getattr(screen, "height", height + margin))
            if sys.platform == "darwin":
                return sx + sw - width - margin, sy + 28
            return sx + sw - width - margin, sy + sh - height - margin
    except Exception as exc:  # pragma: no cover
        logger.debug("screen anchor failed: %s", exc)

    return margin, margin


class FlyoutHost:
    """Frameless Status popup.

    Windows/pywebview requires ``webview.start()`` on the **main** thread.
    Call ``prepare()`` then ``pump()`` from the main thread; run pystray elsewhere.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._window = None
        self._prepared = False
        self._ready = threading.Event()
        self._failed = False
        self._visible = False
        self._url = ""
        self._hide_timer: threading.Timer | None = None
        self._allow_destroy = False
        self._open_fn: Callable[[str], None] | None = None
        self._ignore_blur_until = 0.0

    @property
    def visible(self) -> bool:
        with self._lock:
            return self._visible

    @property
    def failed(self) -> bool:
        with self._lock:
            return self._failed

    @property
    def gui_ready(self) -> bool:
        return self._ready.is_set() and not self.failed and self._prepared

    def prepare(self, url: str) -> bool:
        """Create the hidden flyout window. Call before ``pump()``. Returns False → use browser."""
        with self._lock:
            if self._prepared:
                return not self._failed
            if self._failed:
                return False
            self._url = url
        try:
            import webview
        except Exception as exc:
            logger.warning("pywebview unavailable (%s)", exc)
            with self._lock:
                self._failed = True
                self._ready.set()
            return False
        try:
            x, y = flyout_anchor()
            window = webview.create_window(
                "LakanVault",
                url,
                width=FLYOUT_WIDTH,
                height=FLYOUT_HEIGHT,
                x=x,
                y=y,
                resizable=False,
                frameless=True,
                on_top=True,
                focus=True,
                easy_drag=False,
                hidden=True,
                background_color="#0f1419",
            )
            if window is None:
                raise RuntimeError("create_window returned None")

            def dismiss_flyout() -> None:
                self.dismiss_from_blur()

            window.events.closing += self._on_closing
            # Blur-dismiss is unreliable with tray focus steal on Windows; left-click toggles.
            window.expose(dismiss_flyout)

            with self._lock:
                self._window = window
                self._prepared = True
                self._visible = False
                self._ready.set()
            return True
        except Exception as exc:
            logger.warning("pywebview flyout prepare failed (%s)", exc)
            with self._lock:
                self._failed = True
                self._ready.set()
            return False

    def pump(self) -> None:
        """Block on the webview GUI loop (must be main thread on Windows)."""
        if not self._prepared or self._failed:
            return
        import webview

        webview.start()

    def toggle(
        self,
        url: str,
        *,
        open_fn: Callable[[str], None] | None = None,
    ) -> None:
        with self._lock:
            self._cancel_hide_timer()
            if self._visible:
                self._hide_unlocked()
            else:
                self._show_unlocked(url, open_fn=open_fn)

    def show(
        self,
        url: str,
        *,
        open_fn: Callable[[str], None] | None = None,
    ) -> None:
        with self._lock:
            self._cancel_hide_timer()
            self._show_unlocked(url, open_fn=open_fn)

    def hide(self) -> None:
        with self._lock:
            self._cancel_hide_timer()
            self._hide_unlocked()

    def dismiss_from_blur(self) -> None:
        """JS blur → delayed hide (ignored during post-show grace / tray focus steal)."""
        with self._lock:
            self._cancel_hide_timer()
            if not self._visible:
                return
            if time.monotonic() < self._ignore_blur_until:
                return
            timer = threading.Timer(_BLUR_HIDE_DELAY_S, self._blur_hide_fire)
            timer.daemon = True
            self._hide_timer = timer
            timer.start()

    def shutdown(self) -> None:
        """Allow the flyout window to destroy (tray Quit) and end ``pump()``."""
        with self._lock:
            self._allow_destroy = True
            self._cancel_hide_timer()
            win = self._window
            self._visible = False
        if win is not None:
            try:
                win.destroy()
            except Exception as exc:  # pragma: no cover
                logger.debug("flyout destroy: %s", exc)

    def _blur_hide_fire(self) -> None:
        with self._lock:
            self._hide_timer = None
            if self._visible:
                self._hide_unlocked()

    def _cancel_hide_timer(self) -> None:
        if self._hide_timer is not None:
            self._hide_timer.cancel()
            self._hide_timer = None

    def _fallback(self, url: str, open_fn: Callable[[str], None] | None) -> None:
        if open_fn is not None:
            open_fn(url)
            return
        import webbrowser

        webbrowser.open(url)

    def _show_unlocked(
        self,
        url: str,
        *,
        open_fn: Callable[[str], None] | None = None,
    ) -> None:
        self._url = url
        if open_fn is not None:
            self._open_fn = open_fn
        if self._failed or not self._prepared:
            self._fallback(url, self._open_fn)
            return
        if not self._ready.wait(timeout=8.0):
            logger.warning("flyout GUI not ready; browser fallback")
            self._failed = True
            self._fallback(url, self._open_fn)
            return
        win = self._window
        if win is None:
            self._fallback(url, self._open_fn)
            return
        try:
            # Reload so counts/activity are fresh when popping for a block.
            if url:
                win.load_url(url)
            x, y = flyout_anchor()
            win.move(x, y)
            self._ignore_blur_until = time.monotonic() + _SHOW_GRACE_S
            win.show()
            self._visible = True
        except Exception as exc:
            logger.warning("flyout show failed (%s); browser fallback", exc)
            self._failed = True
            self._fallback(url, self._open_fn)

    def _hide_unlocked(self) -> None:
        win = self._window
        self._visible = False
        if win is None:
            return
        try:
            win.hide()
        except Exception as exc:  # pragma: no cover
            logger.debug("flyout hide: %s", exc)

    def _on_closing(self) -> bool:
        # Return False → Event.set reports abort → window stays alive; we just hide.
        with self._lock:
            if self._allow_destroy:
                return True
            self._visible = False
            win = self._window
        if win is not None:
            try:
                win.hide()
            except Exception:
                pass
        return False

    def _inject_blur_handler(self) -> None:
        """Dismiss only on genuine focus loss after grace — not mousedown inside the panel."""
        win = self._window
        if win is None:
            return
        script = """
        (function () {
          if (window.__lvFlyoutBlurBound) return;
          window.__lvFlyoutBlurBound = true;
          var armed = false;
          setTimeout(function () { armed = true; }, 1500);
          window.addEventListener('blur', function () {
            if (!armed) return;
            try {
              if (window.pywebview && window.pywebview.api && window.pywebview.api.dismiss_flyout) {
                window.pywebview.api.dismiss_flyout();
              }
            } catch (e) {}
          });
        })();
        """
        try:
            win.evaluate_js(script)
        except Exception as exc:  # pragma: no cover
            logger.debug("blur inject failed: %s", exc)


_HOST = FlyoutHost()


def get_flyout_host() -> FlyoutHost:
    return _HOST


def reset_flyout_host_for_tests() -> FlyoutHost:
    """Replace process-wide host (unit tests only)."""
    global _HOST
    _HOST = FlyoutHost()
    return _HOST


def toggle_status_flyout(
    url: str,
    *,
    open_fn: Callable[[str], None] | None = None,
) -> None:
    get_flyout_host().toggle(url, open_fn=open_fn)


def open_panel(
    url: str,
    *,
    title: str = "LakanVault",
    width: int = 960,
    height: int = 720,
    open_fn: Callable[[str], None] | None = None,
) -> None:
    """Open Prompt Review: extra webview window if GUI ready, else browser."""

    def _fallback() -> None:
        if open_fn is not None:
            open_fn(url)
            return
        import webbrowser

        webbrowser.open(url)

    host = get_flyout_host()
    if not host.gui_ready:
        _fallback()
        return

    try:
        import webview

        webview.create_window(
            title,
            url,
            width=width,
            height=height,
            resizable=True,
            on_top=False,
        )
    except Exception as exc:
        logger.warning("review panel failed (%s); opening browser", exc)
        _fallback()
