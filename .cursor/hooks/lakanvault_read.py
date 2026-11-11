#!/usr/bin/env python3
# cursor beforeReadFile — block .env / vault keys / certs when hooks are on
"""Cursor beforeReadFile: deny sensitive local files (.env, vault keys, certs).

Respects the same toggle as the prompt hook:
  env LAKANVAULT_HOOKS=on|off|tag  OR  .cursor/hooks/mode.txt
  Read gate is active only when mode is on (tag does not block file reads).
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

# where the hooks folder lives
def _resolve_hook_dir() -> Path:
    override = (os.environ.get("LAKANVAULT_HOOKS_DIR") or "").strip()
    if override:
        return Path(override)
    return Path(__file__).resolve().parent


_MODE_FILE = _resolve_hook_dir() / "mode.txt"
_DENY_NAMES = frozenset({
    ".env",
    ".env.local",
    ".env.production",
    "vault.key",
    "vault.db",
})
_DENY_SUFFIXES = (".pem", ".p12", ".pfx", ".key")
_DENY_BASENAME_RE = re.compile(r"^\.env(\..+)?$", re.IGNORECASE)


# file-read deny only when mode is fully on (not tag)
def _hooks_enabled() -> bool:
    """File-read deny only in full on mode (not tag — keep this chat usable)."""
    env = (os.environ.get("LAKANVAULT_HOOKS") or "").strip().lower()
    if env in {"on", "1", "true", "yes", "enable", "enabled"}:
        return True
    if env in {"off", "0", "false", "no", "disable", "disabled", "tag", "opt-in", "optin", "test"}:
        return False
    try:
        for line in _MODE_FILE.read_text(encoding="utf-8").splitlines():
            word = line.strip().split("#", 1)[0].strip().lower()
            if not word:
                continue
            return word in {"on", "1", "true", "yes", "enable", "enabled"}
    except OSError:
        pass
    return False


# pull file paths out of the hook payload
def _paths_from(payload: dict) -> list[str]:
    out: list[str] = []
    for key in ("file_path", "path", "filePath", "uri", "file"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            out.append(value)
    for nest in ("input", "data"):
        inner = payload.get(nest)
        if isinstance(inner, dict):
            out.extend(_paths_from(inner))
    return out


# is this path one of the sensitive ones we block
def _is_denied(path: str) -> bool:
    normalized = path.replace("\\", "/")
    base = os.path.basename(normalized)
    lower = base.lower()
    if lower in _DENY_NAMES or _DENY_BASENAME_RE.match(base):
        return True
    if any(lower.endswith(suf) for suf in _DENY_SUFFIXES):
        return True
    if normalized.lower().endswith("vault.key") or "/data/vault.key" in normalized.lower():
        return True
    return False


# main read hook — deny sensitive files when gate is on
def main() -> int:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        print(json.dumps({"continue": False, "permission": "deny", "user_message": "LakanVault: invalid read-hook input"}))
        return 0

    if not _hooks_enabled():
        print(json.dumps({"continue": True, "permission": "allow"}))
        return 0

    if not isinstance(payload, dict):
        print(json.dumps({"continue": True, "permission": "allow"}))
        return 0

    for path in _paths_from(payload):
        if _is_denied(path):
            msg = (
                "LakanVault blocked read of a sensitive file (env/key/cert). "
                "Gate toggle: .cursor/hooks/mode.txt → on|off"
            )
            print(json.dumps({"continue": False, "permission": "deny", "user_message": msg, "agent_message": msg}))
            return 0

    print(json.dumps({"continue": True, "permission": "allow"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
