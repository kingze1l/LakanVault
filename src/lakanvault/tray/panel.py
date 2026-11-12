# teams-ish status flyout via pywebview (falls back to browser if needed)
"""Teams-style Status flyout via pywebview (main-thread GUI), with browser fallback."""
from __future__ import annotations

import logging
import sys
import threading
import time
from typing import Callable

logger = logging.getLogger(__name__)

FLYOUT_WIDTH = 380
FLYOUT_HEIGHT = 580
TOAST_WIDTH = 360
TOAST_HEIGHT = 118
# Tray left-click steals focus briefly; ignore blur until the flyout settles.
_SHOW_GRACE_S = 1.5
_BLUR_HIDE_DELAY_S = 0.5


# work area of the monitor under the cursor (laptop vs big monitor)
def work_area_rect() -> tuple[int, int, int, int]:
    """Return (left, top, right, bottom) for the monitor under the mouse, else primary."""
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            class POINT(ctypes.Structure):
                _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

            class RECT(ctypes.Structure):
                _fields_ = [
                    ("left", wintypes.LONG),
                    ("top", wintypes.LONG),
                    ("right", wintypes.LONG),
                    ("bottom", wintypes.LONG),
                ]

            class MONITORINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.DWORD),
                    ("rcMonitor", RECT),
                    ("rcWork", RECT),
                    ("dwFlags", wintypes.DWORD),
                ]

            pt = POINT()
            ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
            MONITOR_DEFAULTTONEAREST = 2
            hmon = ctypes.windll.user32.MonitorFromPoint(pt, MONITOR_DEFAULTTONEAREST)
            info = MONITORINFO()
            info.cbSize = ctypes.sizeof(MONITORINFO)
            if hmon and ctypes.windll.user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
                r = info.rcWork
                return int(r.left), int(r.top), int(r.right), int(r.bottom)

            rect = RECT()
            if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):
                return int(rect.left), int(rect.top), int(rect.right), int(rect.bottom)
        except Exception as exc:  # pragma: no cover - platform quirks
            logger.debug("work_area_rect failed: %s", exc)

    try:
        import webview

        screens = list(webview.screens or [])
        if screens:
            screen = min(screens, key=lambda s: (getattr(s, "y", 0), getattr(s, "x", 0)))
            sx = int(getattr(screen, "x", 0))
            sy = int(getattr(screen, "y", 0))
            sw = int(getattr(screen, "width", 1280))
            sh = int(getattr(screen, "height", 800))
            return sx, sy, sx + sw, sy + sh
    except Exception as exc:  # pragma: no cover
        logger.debug("webview work area failed: %s", exc)

    return 0, 0, 1280, 800


# shrink flyout so it fits the screen youre on now
def flyout_size(
    preferred_w: int = FLYOUT_WIDTH,
    preferred_h: int = FLYOUT_HEIGHT,
) -> tuple[int, int]:
    """Clamp popup size to the current monitor work area (big monitor vs laptop)."""
    left, top, right, bottom = work_area_rect()
    aw = max(320, right - left)
    ah = max(400, bottom - top)
    margin = 24
    w = min(preferred_w, aw - margin, max(280, int(aw * 0.42)))
    h = min(preferred_h, ah - margin, max(320, int(ah * 0.78)))
    w = max(260, min(w, aw - margin))
    h = max(300, min(h, ah - margin))
    return int(w), int(h)


# figure out where to park the popup near the tray corner
def flyout_anchor(width: int | None = None, height: int | None = None) -> tuple[int, int]:
    """Return top-left (x, y) for a tray-corner popup on the current screen."""
    if width is None or height is None:
        fw, fh = flyout_size()
        width = fw if width is None else width
        height = fh if height is None else height
    margin = 12
    left, top, right, bottom = work_area_rect()
    x = int(right - width - margin)
    y = int(bottom - height - margin)
    if sys.platform == "darwin":
        y = int(top + 28)
    return max(left, x), max(top, y)


class FlyoutHost:
    """Frameless Status popup.

    Windows/pywebview requires ``webview.start()`` on the **main** thread.
    Call ``prepare()`` then ``pump()`` from the main thread; run pystray elsewhere.
    """

    # set up locks n window handles
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
        self._toast_window = None
        self._toast_visible = False
        self._base_url = "http://127.0.0.1:8080"

    # is the flyout showing
    @property
    def visible(self) -> bool:
        with self._lock:
            return self._visible

    # did prepare fail so we use browser
    @property
    def failed(self) -> bool:
        with self._lock:
            return self._failed

    # gui ready to open extra windows
    @property
    def gui_ready(self) -> bool:
        return self._ready.is_set() and not self.failed and self._prepared

    # create hidden flyout + toast windows (call before pump)
    def prepare(self, url: str) -> bool:
        """Create the hidden flyout window. Call before ``pump()``. Returns False → use browser."""
        with self._lock:
            if self._prepared:
                return not self._failed
            if self._failed:
                return False
            self._url = url
            if url.startswith("http://") or url.startswith("https://"):
                # status URL → origin for toast/review
                parts = url.split("/", 3)
                if len(parts) >= 3:
                    self._base_url = parts[0] + "//" + parts[2]
        try:
            import webview
        except Exception as exc:
            logger.warning("pywebview unavailable (%s)", exc)
            with self._lock:
                self._failed = True
                self._ready.set()
            return False
        try:
            fw, fh = flyout_size()
            x, y = flyout_anchor(fw, fh)
            window = webview.create_window(
                "LakanVault",
                url,
                width=fw,
                height=fh,
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

            # js can ask us to hide on blur
            def dismiss_flyout() -> None:
                self.dismiss_from_blur()

            # js minimize button
            def minimize_flyout() -> None:
                self.hide()

            # open full dashboard (or any url) in the system browser
            def open_external(url: str = "") -> None:
                target = (url or "").strip() or f"{self._base_url}/dashboard"
                if target.startswith("/"):
                    target = f"{self._base_url.rstrip('/')}{target}"
                try:
                    import webbrowser

                    webbrowser.open(target)
                except Exception as exc:  # pragma: no cover
                    logger.debug("open_external failed: %s", exc)

            window.events.closing += self._on_closing
            # Blur-dismiss is unreliable with tray focus steal on Windows; left-click toggles.
            window.expose(dismiss_flyout)
            window.expose(minimize_flyout)
            window.expose(open_external)

            tw = min(TOAST_WIDTH, flyout_size(TOAST_WIDTH, TOAST_HEIGHT)[0])
            th = TOAST_HEIGHT
            toast_x, toast_y = flyout_anchor(tw, th)
            toast = webview.create_window(
                "LakanVault Alert",
                f"{self._base_url}/toast",
                width=tw,
                height=th,
                x=toast_x,
                y=toast_y,
                resizable=False,
                frameless=True,
                on_top=True,
                focus=False,
                easy_drag=False,
                hidden=True,
                background_color="#12171e",
            )
            if toast is not None:
                # close the toast window
                def toast_dismiss() -> None:
                    self.hide_toast()

                # view → open status flyout with that event
                def toast_view(event_id: str = "") -> None:
                    # Stay inside the small Status flyout (not a separate Review window).
                    self.hide_toast()
                    eid = str(event_id or "").strip()
                    url = f"{self._base_url}/status"
                    if eid:
                        url = f"{url}?event={eid}"
                    else:
                        url = f"{url}?panel=review"
                    self.show(url, open_fn=self._open_fn)

                toast.events.closing += self._on_toast_closing
                toast.expose(toast_dismiss)
                toast.expose(toast_view)

            with self._lock:
                self._window = window
                self._toast_window = toast
                self._prepared = True
                self._visible = False
                self._toast_visible = False
                self._ready.set()
            return True
        except Exception as exc:
            logger.warning("pywebview flyout prepare failed (%s)", exc)
            with self._lock:
                self._failed = True
                self._ready.set()
            return False

    # block on the webview gui loop (main thread on win)
    def pump(self) -> None:
        """Block on the webview GUI loop (must be main thread on Windows)."""
        if not self._prepared or self._failed:
            return
        import webview

        webview.start()

    # show/hide toggle
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

    # force show the flyout
    def show(
        self,
        url: str,
        *,
        open_fn: Callable[[str], None] | None = None,
    ) -> None:
        with self._lock:
            self._cancel_hide_timer()
            self._show_unlocked(url, open_fn=open_fn)

    # hide the flyout
    def hide(self) -> None:
        with self._lock:
            self._cancel_hide_timer()
            self._hide_unlocked()

    # little toast above the status corner
    def show_toast(
        self,
        *,
        event_id: int | str,
        action: str,
        source: str = "protect",
        entity_types: list[str] | tuple[str, ...] | None = None,
        open_fn: Callable[[str], None] | None = None,
    ) -> None:
        """Show Fig 17–19 style toast; falls back to browser/OS notify caller on failure."""
        if open_fn is not None:
            self._open_fn = open_fn
        act = (action or "warn").lower()
        types = ",".join(list(entity_types or [])[:4])
        from urllib.parse import quote

        url = (
            f"{self._base_url}/toast?event={quote(str(event_id))}"
            f"&action={quote(act)}&source={quote(source or 'protect')}"
            f"&types={quote(types)}"
        )
        with self._lock:
            if self._failed or not self._prepared or self._toast_window is None:
                return
            win = self._toast_window
        try:
            win.load_url(url)
            tw = min(TOAST_WIDTH, flyout_size(TOAST_WIDTH, TOAST_HEIGHT)[0])
            th = TOAST_HEIGHT
            x, y = flyout_anchor(tw, th)
            # Stack above Status corner with a small gap.
            try:
                win.resize(tw, th)
            except Exception:
                pass
            win.move(x, max(0, y - th - 8))
            win.show()
            with self._lock:
                self._toast_visible = True
        except Exception as exc:
            logger.debug("toast show failed: %s", exc)

    # hide the toast window
    def hide_toast(self) -> None:
        with self._lock:
            win = self._toast_window
            self._toast_visible = False
        if win is None:
            return
        try:
            win.hide()
        except Exception as exc:  # pragma: no cover
            logger.debug("toast hide: %s", exc)

    # js blur → hide after a short delay (ignore tray focus steal)
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

    # quit path — really destroy windows so pump can end
    def shutdown(self) -> None:
        """Allow the flyout window to destroy (tray Quit) and end ``pump()``."""
        with self._lock:
            self._allow_destroy = True
            self._cancel_hide_timer()
            win = self._window
            toast = self._toast_window
            self._visible = False
            self._toast_visible = False
        for w in (toast, win):
            if w is None:
                continue
            try:
                w.destroy()
            except Exception as exc:  # pragma: no cover
                logger.debug("flyout destroy: %s", exc)

    # timer callback that actually hides after blur
    def _blur_hide_fire(self) -> None:
        with self._lock:
            self._hide_timer = None
            if self._visible:
                self._hide_unlocked()

    # cancel a pending blur-hide timer
    def _cancel_hide_timer(self) -> None:
        if self._hide_timer is not None:
            self._hide_timer.cancel()
            self._hide_timer = None

    # open in browser if flyout is dead
    def _fallback(self, url: str, open_fn: Callable[[str], None] | None) -> None:
        if open_fn is not None:
            open_fn(url)
            return
        import webbrowser

        webbrowser.open(url)

    # show path (caller holds lock)
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
            # Re-size + re-anchor every show (laptop vs big monitor / dock change).
            fw, fh = flyout_size()
            x, y = flyout_anchor(fw, fh)
            try:
                win.resize(fw, fh)
            except Exception:
                pass
            win.move(x, y)
            self._ignore_blur_until = time.monotonic() + _SHOW_GRACE_S
            win.show()
            self._visible = True
        except Exception as exc:
            logger.warning("flyout show failed (%s); browser fallback", exc)
            self._failed = True
            self._fallback(url, self._open_fn)

    # hide path (caller holds lock)
    def _hide_unlocked(self) -> None:
        win = self._window
        self._visible = False
        if win is None:
            return
        try:
            win.hide()
        except Exception as exc:  # pragma: no cover
            logger.debug("flyout hide: %s", exc)

    # closing X → hide instead of destroy unless quitting
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

    # same for toast window
    def _on_toast_closing(self) -> bool:
        with self._lock:
            if self._allow_destroy:
                return True
            self._toast_visible = False
            win = self._toast_window
        if win is not None:
            try:
                win.hide()
            except Exception:
                pass
        return False

    # inject blur handler js (kept around if we need it)
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


# singleton flyout host for the process
def get_flyout_host() -> FlyoutHost:
    return _HOST


# swap host for unit tests
def reset_flyout_host_for_tests() -> FlyoutHost:
    """Replace process-wide host (unit tests only)."""
    global _HOST
    _HOST = FlyoutHost()
    return _HOST


# tray menu helper to toggle status
def toggle_status_flyout(
    url: str,
    *,
    open_fn: Callable[[str], None] | None = None,
) -> None:
    get_flyout_host().toggle(url, open_fn=open_fn)


# open a bigger review panel window (or browser)
def open_panel(
    url: str,
    *,
    title: str = "LakanVault",
    width: int = 960,
    height: int = 720,
    open_fn: Callable[[str], None] | None = None,
) -> None:
    """Open Prompt Review: extra webview window if GUI ready, else browser."""

    # browser fallback if gui isnt ready
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
