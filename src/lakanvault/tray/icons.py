"""Solid-color tray icons (green / amber / red). Requires Pillow at runtime."""
from __future__ import annotations

from lakanvault.tray.state import TrayStatus


def make_status_icon(status: TrayStatus, size: int = 64):
    """Return a PIL Image for the given tray status."""
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    margin = max(2, size // 8)
    color = (*status.color_rgb, 255)
    draw.ellipse((margin, margin, size - margin - 1, size - margin - 1), fill=color)
    return img
