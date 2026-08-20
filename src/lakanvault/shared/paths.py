"""Dev vs frozen resource and writable data paths."""
from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def bundle_root() -> Path:
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)).resolve()
    return Path(__file__).resolve().parents[3]


def resource_path(*parts: str | Path) -> Path:
    """Read-only assets: config templates, static files, bundled OCR models."""
    return bundle_root().joinpath(*parts)


def writable_data_root() -> Path:
    """Never write into _MEIPASS. Next to the exe when frozen."""
    if is_frozen():
        return Path(sys.executable).resolve().parent / "data"
    return bundle_root() / "data"
