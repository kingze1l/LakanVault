#!/usr/bin/env python3
# cursor beforeSubmitPrompt gate — hit the daemon so raw secrets dont leave
"""Cursor beforeSubmitPrompt gate (Joan via daemon).

Cursor cannot rewrite the prompt (only continue / user_message).
When ON: BLOCK and MASK stop the send so raw text never hits the cloud.
MASK hands back Joan's sanitized text for you to paste and resend.

FR1/FR8/FR9 remask fix: after a MASK handoff, the exact sanitized string is
trusted once (TTL) so pasting a fake name/email is not denied again.

Toggle (first match wins):
  1) env LAKANVAULT_HOOKS=on|off|tag
  2) daemon GET http://127.0.0.1:8080/api/hooks/mode  (Status UI Off/Tag/On)
  3) this folder's mode.txt first word: on | off | tag

  off  — never gate (chat stays normal)
  on   — gate every prompt in this workspace
  tag  — gate only when the prompt contains [[lv]]
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_URL = os.environ.get("LAKANVAULT_REVIEW_URL", "http://127.0.0.1:8080/api/review")


# where the hooks folder lives (or env override)
def _resolve_hook_dir() -> Path:
    override = (os.environ.get("LAKANVAULT_HOOKS_DIR") or "").strip()
    if override:
        return Path(override)
    return Path(__file__).resolve().parent


_HOOK_DIR = _resolve_hook_dir()
_MODE_FILE = _HOOK_DIR / "mode.txt"
_TAG = "[[lv]]"
_HANDOFF_TTL_SEC = float(os.environ.get("LAKANVAULT_HANDOFF_TTL", "600"))  # 10 min


# path for the one-shot mask handoff allowlist file
def _handoff_path() -> Path:
    override = (os.environ.get("LAKANVAULT_HANDOFF_FILE") or "").strip()
    return Path(override) if override else (_HOOK_DIR / "handoff_allow.json")


# ask the running daemon what the Status UI set (fast fail if down)
def _daemon_mode() -> str | None:
    url = os.environ.get("LAKANVAULT_HOOKS_MODE_URL", "http://127.0.0.1:8080/api/hooks/mode")
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=0.45) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        word = str((data or {}).get("mode") or "").strip().lower()
        if word in {"on", "off", "tag"}:
            return word
    except Exception:
        return None
    return None


# read on/off/tag from env, then daemon Status UI, then mode.txt
def _mode() -> str:
    env = (os.environ.get("LAKANVAULT_HOOKS") or "").strip().lower()
    if env in {"on", "1", "true", "yes", "enable", "enabled"}:
        return "on"
    if env in {"off", "0", "false", "no", "disable", "disabled"}:
        return "off"
    if env in {"tag", "opt-in", "optin", "test"}:
        return "tag"
    daemon = _daemon_mode()
    if daemon:
        return daemon
    try:
        for line in _MODE_FILE.read_text(encoding="utf-8").splitlines():
            word = line.strip().split("#", 1)[0].strip().lower()
            if not word:
                continue
            if word in {"on", "1", "true", "yes", "enable", "enabled"}:
                return "on"
            if word in {"tag", "opt-in", "optin", "test"}:
                return "tag"
            return "off"
    except OSError:
        pass
    return "off"


# should we gate this prompt based on mode
def _should_gate(prompt: str) -> bool:
    mode = _mode()
    if mode == "on":
        return True
    if mode == "tag":
        return _TAG in prompt
    return False


# load unexpired trusted handoff strings
def _load_handoffs() -> list[dict]:
    try:
        raw = json.loads(_handoff_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(raw, list):
        return []
    now = time.time()
    return [
        row
        for row in raw
        if isinstance(row, dict)
        and isinstance(row.get("text"), str)
        and isinstance(row.get("expires_at"), (int, float))
        and float(row["expires_at"]) >= now
        and row["text"].strip()
    ]


# write the handoff allowlist back to disk
def _save_handoffs(rows: list[dict]) -> None:
    try:
        path = _handoff_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    except OSError:
        pass


# remember a sanitized mask string so paste is trusted once
def _remember_handoff(sanitized: str) -> None:
    text = sanitized.strip()
    if not text:
        return
    rows = _load_handoffs()
    # Dedupe same text; refresh TTL
    rows = [r for r in rows if r.get("text") != text]
    rows.append({"text": text, "expires_at": time.time() + _HANDOFF_TTL_SEC})
    _save_handoffs(rows[-20:])  # cap


# if prompt matches a prior mask handoff allow once n clear it
def _consume_trusted_handoff(prompt: str) -> bool:
    """Exact match of a prior MASK sanitized string → allow once and clear."""
    text = prompt.strip()
    if not text:
        return False
    rows = _load_handoffs()
    kept: list[dict] = []
    matched = False
    for row in rows:
        if not matched and row.get("text") == text:
            matched = True
            continue
        kept.append(row)
    if matched:
        _save_handoffs(kept)
    return matched


# dig the prompt text out of whatever shape cursor sent
def _extract_prompt(payload: dict) -> str:
    for key in ("prompt", "text", "content", "user_prompt", "message"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    for nest in ("input", "data"):
        inner = payload.get(nest)
        if isinstance(inner, dict):
            found = _extract_prompt(inner)
            if found:
                return found
    return ""


# build a deny response for cursor
def _deny(message: str) -> dict:
    return {
        "continue": False,
        "permission": "deny",
        "user_message": message,
        "agent_message": message,
    }


# build an allow response (optional note)
def _allow(message: str = "") -> dict:
    out: dict = {"continue": True, "permission": "allow"}
    if message:
        out["user_message"] = message
    return out


# parse cursor stdin — empty/BOM/noise should not hard-block the chat
def _parse_hook_payload(raw: str) -> tuple[dict | None, str | None]:
    text = (raw or "").lstrip("\ufeff").strip()
    if not text:
        return {}, None
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data, None
        return {}, None
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            data = json.loads(text[start : end + 1])
            if isinstance(data, dict):
                return data, None
        except json.JSONDecodeError:
            pass
    return None, "invalid_json"


# main hook — read stdin call daemon decide allow/deny
def main() -> int:
    raw = sys.stdin.read()
    payload, err = _parse_hook_payload(raw)
    if err or payload is None:
        # Fail-open on bad stdin so demo PCs are not stuck ("invalid hook input").
        print(
            json.dumps(
                _allow(
                    "LakanVault: could not parse hook input — allowing send. "
                    "If this keeps happening, restart Cursor / reinstall MVP hooks."
                )
            )
        )
        return 0

    prompt = _extract_prompt(payload if isinstance(payload, dict) else {})
    if not prompt.strip() or not _should_gate(prompt):
        print(json.dumps(_allow()))
        return 0

    # Strip the opt-in tag before Joan / handoff match.
    scan_text = prompt.replace(_TAG, "").strip() or prompt

    # FR8 paste path: exact prior MASK handoff is already surrogate — allow once.
    if _consume_trusted_handoff(scan_text):
        print(
            json.dumps(
                _allow(
                    "LakanVault: accepted trusted sanitized handoff (one-shot). "
                    "Raw PII was never in this paste."
                )
            )
        )
        return 0

    body = json.dumps({"text": scan_text, "session_id": "", "llm": "never"}).encode("utf-8")
    req = urllib.request.Request(
        DEFAULT_URL,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        print(json.dumps(_deny(f"LakanVault: review HTTP {exc.code}")))
        return 0
    except Exception:
        print(json.dumps(_deny("LakanVault daemon unreachable — start the API on :8080")))
        return 0

    final = str(data.get("final_action") or "allow").lower()
    sanitized = data.get("sanitized") if isinstance(data.get("sanitized"), str) else ""
    findings = data.get("findings") or []
    meta_bits = []
    for f in findings[:5]:
        if not isinstance(f, dict):
            continue
        et = f.get("entity_type") or "finding"
        tier = f.get("tier") or ""
        act = f.get("action") or ""
        meta_bits.append(f"{et}/{tier}/{act}".strip("/"))
    meta = ", ".join(meta_bits) if meta_bits else "policy"

    if final == "block":
        print(
            json.dumps(
                _deny(
                    f"LakanVault blocked this prompt ({meta}). "
                    "Secret/credential must not leave the machine. "
                    "Toggle: set .cursor/hooks/mode.txt to off to disable the gate."
                )
            )
        )
        return 0

    if final == "mask":
        handoff = sanitized.strip() or "(empty sanitized — open http://127.0.0.1:8080/review)"
        if sanitized.strip():
            _remember_handoff(sanitized)
        print(
            json.dumps(
                _deny(
                    "LakanVault stopped this send so raw PII does not hit the cloud "
                    f"({meta}).\n\n"
                    "Cursor cannot rewrite the chat box. Paste the sanitized text below "
                    "as a new message (exact paste is trusted once — FR8 handoff):\n\n"
                    f"{handoff}\n\n"
                    "Gate toggle: .cursor/hooks/mode.txt → on|off|tag"
                )
            )
        )
        return 0

    if final == "warn":
        print(json.dumps(_allow(f"LakanVault warning ({meta}).")))
        return 0

    print(json.dumps(_allow()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
