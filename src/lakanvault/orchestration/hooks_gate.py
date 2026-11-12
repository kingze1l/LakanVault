# cursor hooks on/off/tag — tray ui flips this so chat can stay usable
# hooks ask the daemon first (unless LAKANVAULT_HOOKS env is set)
"""Daemon-side Cursor hooks gate (off / tag / on)."""
from __future__ import annotations

import logging
import os
import threading
from pathlib import Path

from lakanvault.shared.paths import writable_data_root

logger = logging.getLogger(__name__)

VALID = frozenset({"off", "tag", "on"})
_DEFAULT = "tag"
_lock = threading.Lock()
_mode = _DEFAULT
_loaded = False


# path we persist the mode so restart remembers
def _persist_path() -> Path:
    return writable_data_root() / "hooks_mode.txt"


# normalize raw string to off|tag|on or None
def _normalize(raw: str | None) -> str | None:
    if not raw:
        return None
    word = raw.strip().split("#", 1)[0].strip().lower()
    if word in {"1", "true", "yes", "enable", "enabled"}:
        return "on"
    if word in {"0", "false", "no", "disable", "disabled"}:
        return "off"
    if word in {"opt-in", "optin", "test"}:
        return "tag"
    if word in VALID:
        return word
    return None


# load once from disk (or keep default tag)
def _ensure_loaded() -> None:
    global _mode, _loaded
    with _lock:
        if _loaded:
            return
        _loaded = True
        try:
            text = _persist_path().read_text(encoding="utf-8")
            parsed = _normalize(text.splitlines()[0] if text else "")
            if parsed:
                _mode = parsed
        except OSError:
            pass


# hook folders we know about (repo + frozen demo + env)
def _hook_dir_candidates() -> list[Path]:
    candidates: list[Path] = []
    env_files = (os.environ.get("LAKANVAULT_MODE_FILES") or "").strip()
    if env_files:
        for part in env_files.replace(";", os.pathsep).split(os.pathsep):
            p = part.strip().strip('"')
            if p:
                candidates.append(Path(p).parent if p.lower().endswith("mode.txt") else Path(p))
    hooks_dir = (os.environ.get("LAKANVAULT_HOOKS_DIR") or "").strip()
    if hooks_dir:
        candidates.append(Path(hooks_dir))
    here = Path(__file__).resolve()
    candidates.append(here.parents[3] / ".cursor" / "hooks")
    try:
        import sys

        if getattr(sys, "frozen", False):
            exe_dir = Path(sys.executable).resolve().parent
            candidates.append(exe_dir / "demo-workspace" / ".cursor" / "hooks")
        # Desktop / unzipped MVP next to common paths
        desk = Path.home() / "Desktop" / "LakanVault-MVP" / "demo-workspace" / ".cursor" / "hooks"
        candidates.append(desk)
    except Exception:
        pass
    return candidates


# write mode.txt copies so workspaces stay in sync when we know the paths
def _sync_mode_files(mode: str) -> list[str]:
    updated: list[str] = []
    body = f"{mode}\n# set by LakanVault Status UI — off=chat free, tag=[[lv]] only, on=all prompts\n"
    seen: set[str] = set()
    for hooks in _hook_dir_candidates():
        path = hooks / "mode.txt"
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
            updated.append(str(path))
        except OSError as exc:
            logger.debug("hooks mode sync skip %s: %s", path, exc)
    return updated


# one-shot FR8-style trust so Cursor paste of original is allowed once after Override
def remember_trusted_paste(text: str, *, ttl_sec: float = 600.0) -> list[str]:
    """Append exact text to handoff_allow.json under known hook dirs (TTL)."""
    import json
    import time

    cleaned = (text or "").strip()
    if not cleaned:
        return []
    row = {"text": cleaned, "expires_at": time.time() + float(ttl_sec)}
    updated: list[str] = []
    seen: set[str] = set()
    for hooks in _hook_dir_candidates():
        path = hooks / "handoff_allow.json"
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            rows: list = []
            if path.is_file():
                try:
                    raw = json.loads(path.read_text(encoding="utf-8"))
                    if isinstance(raw, list):
                        rows = [r for r in raw if isinstance(r, dict)]
                except (OSError, json.JSONDecodeError):
                    rows = []
            now = time.time()
            rows = [
                r
                for r in rows
                if isinstance(r.get("text"), str)
                and isinstance(r.get("expires_at"), (int, float))
                and float(r["expires_at"]) >= now
                and r.get("text") != cleaned
            ]
            rows.append(row)
            path.write_text(json.dumps(rows[-20:], indent=2), encoding="utf-8")
            updated.append(str(path))
        except OSError as exc:
            logger.debug("handoff write skip %s: %s", path, exc)
    return updated


# current gate mode
def get_hooks_mode() -> str:
    _ensure_loaded()
    with _lock:
        return _mode


# flip gate + persist + best-effort sync mode.txt copies
def set_hooks_mode(mode: str) -> dict:
    global _mode, _loaded
    parsed = _normalize(mode)
    if parsed is None:
        raise ValueError("mode must be off, tag, or on")
    with _lock:
        _mode = parsed
        _loaded = True
    persist = _persist_path()
    try:
        persist.parent.mkdir(parents=True, exist_ok=True)
        persist.write_text(f"{parsed}\n", encoding="utf-8")
    except OSError as exc:
        logger.warning("could not persist hooks mode: %s", exc)
    synced = _sync_mode_files(parsed)
    return {
        "mode": parsed,
        "synced_files": synced,
        "hint": (
            "Hooks gate updated. Cursor cannot auto-reload MCP from outside — "
            "if tools missing: Settings → MCP → refresh lakanvault, or Command Palette → Developer: Reload Window."
        ),
    }
