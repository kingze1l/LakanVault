"""pystray UI shell — thin wrapper over TrayController (ADR-004)."""
from __future__ import annotations

from typing import Callable

from lakanvault.tray.icons import make_status_icon
from lakanvault.tray.state import TrayController


def run_tray_loop(
    controller: TrayController,
    *,
    on_quit: Callable[[], None] | None = None,
) -> None:
    """Block on the system tray until Quit. Requires pystray + Pillow."""
    import pystray
    from pystray import MenuItem as Item

    def open_dashboard(icon: pystray.Icon, item: object) -> None:
        controller.open_dashboard(_default_open)

    def quit_app(icon: pystray.Icon, item: object) -> None:
        if on_quit is not None:
            on_quit()
        icon.stop()

    menu = pystray.Menu(
        Item("Open Dashboard", open_dashboard, default=True),
        Item("Quit", quit_app),
    )
    icon = pystray.Icon(
        "LakanVault",
        make_status_icon(controller.status),
        f"LakanVault — {controller.status.value}",
        menu,
    )
    icon.run()


def _default_open(url: str) -> None:
    import webbrowser

    webbrowser.open(url)
