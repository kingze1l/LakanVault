"""Tray icon generation — requires Pillow."""
from __future__ import annotations

import pytest

pytest.importorskip("PIL")

from lakanvault.tray.icons import make_status_icon
from lakanvault.tray.state import TrayStatus


def test_make_status_icon_size_and_mode() -> None:
    img = make_status_icon(TrayStatus.RUNNING, size=32)
    assert img.size == (32, 32)
    assert img.mode == "RGBA"


def test_error_icon_differs_from_running() -> None:
    green = list(make_status_icon(TrayStatus.RUNNING, size=16).getdata())
    red = list(make_status_icon(TrayStatus.ERROR, size=16).getdata())
    assert green != red
