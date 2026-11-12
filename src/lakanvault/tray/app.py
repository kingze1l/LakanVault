# pystray shell — tray menu + poll protect events + toasts
"""pystray UI shell — thin wrapper over TrayController (ADR-004)."""
from __future__ import annotations

import logging
import threading
from typing import Callable

from lakanvault.tray.icons import make_status_icon
from lakanvault.tray.panel import get_flyout_host, toggle_status_flyout
from lakanvault.tray.state import TrayController

logger = logging.getLogger(__name__)

_POLL_SECONDS = 2.0


# run the tray forever (flyout on main thread when we can)
def run_tray_loop(
    controller: TrayController,
    *,
    on_quit: Callable[[], None] | None = None,
) -> None:
    """Run tray + Teams-style Status flyout + protect toasts.

    pywebview must own the **main** thread on Windows. pystray runs on a
    background thread when the flyout GUI is available; otherwise the tray
    owns main and Status falls back to the browser.
    """
    import pystray
    from pystray import MenuItem as Item

    icon_holder: dict[str, pystray.Icon | None] = {"icon": None}
    stop = threading.Event()
    host = get_flyout_host()

    # left click / status menu → toggle the flyout
    def toggle_status(icon: pystray.Icon, item: object) -> None:
        toggle_status_flyout(controller.status_url, open_fn=_browser_open)

    # open prompt review inside the status flyout
    def open_review(icon: pystray.Icon, item: object) -> None:
        # Review lives inside the Status flyout (compact tray UI).
        host.show(
            f"{controller.status_url}?panel=review",
            open_fn=_browser_open,
        )

    # full browser dashboard
    def open_dashboard(icon: pystray.Icon, item: object) -> None:
        controller.open_dashboard(_browser_open)

    # quit tray n tear stuff down
    def quit_app(icon: pystray.Icon, item: object) -> None:
        stop.set()
        try:
            host.shutdown()
        except Exception as exc:  # pragma: no cover
            logger.debug("flyout shutdown: %s", exc)
        if on_quit is not None:
            on_quit()
        icon.stop()

    # os toast via pystray if the icon exists
    def _notify(title: str, body: str) -> None:
        icon = icon_holder["icon"]
        if icon is None:
            return
        try:
            icon.notify(body, title)
        except Exception as exc:  # pragma: no cover - OS toast quirks
            logger.debug("icon.notify failed: %s", exc)

    # refresh icon color / title from controller status
    def _refresh_icon() -> None:
        icon = icon_holder["icon"]
        if icon is None:
            return
        try:
            icon.icon = make_status_icon(controller.status)
            paused = " (paused)" if controller.paused else ""
            icon.title = f"LakanVault — {controller.status.value}{paused}"
        except Exception as exc:  # pragma: no cover
            logger.debug("icon refresh failed: %s", exc)

    # show our little custom toast for the latest event
    def _show_custom_toasts(events: list[dict]) -> None:
        # Show latest event toast (single slot).
        ev = events[-1]
        try:
            host.show_toast(
                event_id=ev.get("id", ""),
                action=str(ev.get("action") or "warn"),
                source=str(ev.get("source") or "protect"),
                entity_types=list(ev.get("entity_types") or []),
                open_fn=_browser_open,
            )
        except Exception as exc:  # pragma: no cover
            logger.debug("custom toast failed: %s", exc)

    # poll loop — check for new protect events every couple secs
    def _poll_loop() -> None:
        controller.poll_protect_events()
        while not stop.wait(_POLL_SECONDS):
            events = controller.poll_protect_events()
            if events:
                notified = controller.notify_for_events(events, _notify)
                # Warn/mask/block → small toast only (do not auto-open Status flyout).
                if notified:
                    _show_custom_toasts(notified)
            _refresh_icon()

    menu = pystray.Menu(
        # Left-click (default); hidden from right-click menu — Teams pattern.
        Item("Status", toggle_status, default=True, visible=False),
        Item("Open dashboard", open_dashboard),
        Item("Open Prompt Review", open_review),
        Item("Quit", quit_app),
    )
    icon = pystray.Icon(
        "LakanVault",
        make_status_icon(controller.status),
        f"LakanVault — {controller.status.value}",
        menu,
    )
    icon_holder["icon"] = icon
    poller = threading.Thread(target=_poll_loop, name="lv-tray-poll", daemon=True)
    poller.start()

    flyout_ok = host.prepare(controller.status_url)
    try:
        if flyout_ok:
            tray_thread = threading.Thread(
                target=icon.run,
                name="lv-pystray",
                daemon=True,
            )
            tray_thread.start()
            host.pump()
            stop.set()
            try:
                icon.stop()
            except Exception:
                pass
            tray_thread.join(timeout=3.0)
        else:
            logger.warning("Status flyout unavailable; tray on main thread, browser fallback")
            icon.run()
    finally:
        stop.set()
        try:
            host.shutdown()
        except Exception:
            pass


# open a url in the default browser
def _browser_open(url: str) -> None:
    import webbrowser

    webbrowser.open(url)


# old name kept for tests / older callers
def _default_open(url: str) -> None:
    """Legacy alias used by older call sites / tests."""
    _browser_open(url)
