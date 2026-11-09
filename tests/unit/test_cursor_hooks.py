"""Cursor hook scripts: stdin JSON → allow/deny without leaking secrets."""
from __future__ import annotations

import io
import json
import runpy
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO = Path(__file__).resolve().parents[2]
PROMPT_HOOK = REPO / ".cursor" / "hooks" / "lakanvault_prompt.py"
READ_HOOK = REPO / ".cursor" / "hooks" / "lakanvault_read.py"

SECRET = "SuperSecret99"


def _run_hook(script: Path, stdin_obj: dict, monkeypatch: pytest.MonkeyPatch) -> dict:
    buf_in = io.StringIO(json.dumps(stdin_obj))
    buf_out = io.StringIO()
    monkeypatch.setattr(sys, "stdin", buf_in)
    monkeypatch.setattr(sys, "stdout", buf_out)
    try:
        runpy.run_path(str(script), run_name="__main__")
    except SystemExit as exc:
        assert exc.code in (0, None)
    return json.loads(buf_out.getvalue())


def test_prompt_hook_denies_block(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_body = {
        "final_action": "block",
        "findings": [{"entity_type": "uri-credentials", "tier": "SECRET", "action": "block"}],
        "sanitized": "",
        "allow_send": False,
    }

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps(fake_body).encode()

    with patch("urllib.request.urlopen", return_value=Resp()):
        out = _run_hook(PROMPT_HOOK, {"prompt": f"pass {SECRET}"}, monkeypatch)
    assert out["permission"] == "deny"
    assert SECRET not in json.dumps(out)


def test_prompt_hook_allows_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps(
                {"final_action": "allow", "findings": [], "sanitized": "hello", "allow_send": True}
            ).encode()

    with patch("urllib.request.urlopen", return_value=Resp()):
        out = _run_hook(PROMPT_HOOK, {"prompt": "hello world"}, monkeypatch)
    assert out["permission"] == "allow"


def test_prompt_hook_daemon_down_denies(monkeypatch: pytest.MonkeyPatch) -> None:
    with patch("urllib.request.urlopen", side_effect=OSError("down")):
        out = _run_hook(PROMPT_HOOK, {"prompt": "hello"}, monkeypatch)
    assert out["permission"] == "deny"
    assert "unreachable" in out["user_message"].lower()


def test_read_hook_denies_env(monkeypatch: pytest.MonkeyPatch) -> None:
    out = _run_hook(READ_HOOK, {"file_path": "C:/proj/.env"}, monkeypatch)
    assert out["permission"] == "deny"


def test_read_hook_allows_normal(monkeypatch: pytest.MonkeyPatch) -> None:
    out = _run_hook(READ_HOOK, {"file_path": "src/lakanvault/app/server.py"}, monkeypatch)
    assert out["permission"] == "allow"


def test_read_hook_denies_pem(monkeypatch: pytest.MonkeyPatch) -> None:
    out = _run_hook(READ_HOOK, {"path": "certs/server.pem"}, monkeypatch)
    assert out["permission"] == "deny"
