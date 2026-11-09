#!/usr/bin/env python3
"""Cursor beforeSubmitPrompt: deny when Joan final_action is block (daemon /api/review)."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_URL = os.environ.get("LAKANVAULT_REVIEW_URL", "http://127.0.0.1:8080/api/review")


def _extract_prompt(payload: dict) -> str:
    for key in ("prompt", "text", "content", "user_prompt", "message"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    # Nested shapes seen in some Cursor builds
    for nest in ("input", "data"):
        inner = payload.get(nest)
        if isinstance(inner, dict):
            found = _extract_prompt(inner)
            if found:
                return found
    return ""


def _deny(message: str) -> dict:
    return {
        "permission": "deny",
        "user_message": message,
        "agent_message": message,
    }


def _allow(message: str = "") -> dict:
    out: dict = {"permission": "allow"}
    if message:
        out["user_message"] = message
    return out


def main() -> int:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        print(json.dumps(_deny("LakanVault: invalid hook input")))
        return 0

    prompt = _extract_prompt(payload if isinstance(payload, dict) else {})
    if not prompt.strip():
        print(json.dumps(_allow()))
        return 0

    body = json.dumps({"text": prompt, "session_id": "", "llm": "never"}).encode("utf-8")
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
        # failClosed in hooks.json blocks when we exit non-zero; still return deny JSON.
        print(json.dumps(_deny("LakanVault daemon unreachable — start the API on :8080")))
        return 0

    final = str(data.get("final_action") or "allow").lower()
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
        print(json.dumps(_deny(f"LakanVault blocked prompt ({meta}). No raw values shown.")))
        return 0

    if final == "mask":
        print(
            json.dumps(
                _allow(
                    "LakanVault: PII would be masked on the proxy/Review path; "
                    "this Cursor hook cannot rewrite the prompt. Use /review or MCP protect."
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
