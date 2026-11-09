#!/usr/bin/env python3
"""Cursor beforeReadFile: deny sensitive local files (.env, vault keys, certs)."""
from __future__ import annotations

import json
import os
import re
import sys

_DENY_NAMES = frozenset({
    ".env",
    ".env.local",
    ".env.production",
    "vault.key",
    "vault.db",
})
_DENY_SUFFIXES = (".pem", ".p12", ".pfx", ".key")
_DENY_BASENAME_RE = re.compile(r"^\.env(\..+)?$", re.IGNORECASE)


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


def _is_denied(path: str) -> bool:
    normalized = path.replace("\\", "/")
    base = os.path.basename(normalized)
    lower = base.lower()
    if lower in _DENY_NAMES or _DENY_BASENAME_RE.match(base):
        return True
    if any(lower.endswith(suf) for suf in _DENY_SUFFIXES):
        return True
    # Nested vault artifacts
    if "/data/vault.key" in normalized.lower() or normalized.lower().endswith("vault.key"):
        return True
    return False


def main() -> int:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        print(json.dumps({"permission": "deny", "user_message": "LakanVault: invalid read-hook input"}))
        return 0

    if not isinstance(payload, dict):
        print(json.dumps({"permission": "allow"}))
        return 0

    for path in _paths_from(payload):
        if _is_denied(path):
            msg = "LakanVault blocked read of a sensitive file (env/key/cert)."
            print(json.dumps({"permission": "deny", "user_message": msg, "agent_message": msg}))
            return 0

    print(json.dumps({"permission": "allow"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
