# cursor hook scripts allow/deny without leaking secrets
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
EMAIL = "jane.doe@example.com"
FAKE_EMAIL = "fleblanc@example.net"

# force hooks on even if mode.txt says off
@pytest.fixture(autouse=True)
def _hooks_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LAKANVAULT_HOOKS", "on")

# run hook script with fake stdin/out
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
    assert out["continue"] is False
    assert out["permission"] == "deny"
    assert SECRET not in json.dumps(out)


def test_prompt_hook_denies_mask_and_hands_sanitized(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    handoff = tmp_path / "handoff_allow.json"
    monkeypatch.setenv("LAKANVAULT_HANDOFF_FILE", str(handoff))
    sanitized = f"please email {FAKE_EMAIL}"
    fake_body = {
        "final_action": "mask",
        "findings": [{"entity_type": "EMAIL_ADDRESS", "tier": "PII_MODERATE", "action": "mask"}],
        "sanitized": sanitized,
        "allow_send": True,
    }

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps(fake_body).encode()

    with patch("urllib.request.urlopen", return_value=Resp()):
        out = _run_hook(PROMPT_HOOK, {"prompt": f"please email {EMAIL}"}, monkeypatch)
    assert out["continue"] is False
    assert FAKE_EMAIL in out["user_message"]
    assert EMAIL not in out["user_message"]
    stored = json.loads(handoff.read_text(encoding="utf-8"))
    assert stored[0]["text"] == sanitized

# one-shot handoff token after mask deny
def test_prompt_hook_trusts_exact_handoff_once(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """FR8: paste of prior MASK sanitized text is allowed once without remask."""
    import time

    handoff = tmp_path / "handoff_allow.json"
    monkeypatch.setenv("LAKANVAULT_HANDOFF_FILE", str(handoff))
    sanitized = f"my name is Trevor Hicks"
    handoff.write_text(
        json.dumps([{"text": sanitized, "expires_at": time.time() + 600}]),
        encoding="utf-8",
    )
    with patch("urllib.request.urlopen") as mock_open:
        out = _run_hook(PROMPT_HOOK, {"prompt": sanitized}, monkeypatch)
    mock_open.assert_not_called()
    assert out["continue"] is True
    assert "trusted" in out.get("user_message", "").lower()
    # One-shot: second paste must call the API again
    remaining = json.loads(handoff.read_text(encoding="utf-8"))
    assert remaining == []


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
    assert out["continue"] is True
    assert out["permission"] == "allow"


def test_prompt_hook_off_skips_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LAKANVAULT_HOOKS", "off")
    with patch("urllib.request.urlopen") as mock_open:
        out = _run_hook(PROMPT_HOOK, {"prompt": f"pass {SECRET}"}, monkeypatch)
    mock_open.assert_not_called()
    assert out["continue"] is True

# tag mode: no marker means skip the gate
def test_prompt_hook_tag_skips_without_marker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LAKANVAULT_HOOKS", "tag")
    with patch("urllib.request.urlopen") as mock_open:
        out = _run_hook(PROMPT_HOOK, {"prompt": f"pass {SECRET}"}, monkeypatch)
    mock_open.assert_not_called()
    assert out["continue"] is True


def test_prompt_hook_tag_gates_with_marker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LAKANVAULT_HOOKS", "tag")
    fake_body = {
        "final_action": "block",
        "findings": [{"entity_type": "openai-sk-generic", "tier": "SECRET", "action": "block"}],
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
        out = _run_hook(
            PROMPT_HOOK,
            {"prompt": f"[[lv]] pass {SECRET}"},
            monkeypatch,
        )
    assert out["continue"] is False
    assert SECRET not in json.dumps(out)


def test_prompt_hook_daemon_down_denies(monkeypatch: pytest.MonkeyPatch) -> None:
    with patch("urllib.request.urlopen", side_effect=OSError("down")):
        out = _run_hook(PROMPT_HOOK, {"prompt": "hello"}, monkeypatch)
    assert out["continue"] is False
    assert "unreachable" in out["user_message"].lower()


def test_prompt_hook_bad_json_allows_soft(monkeypatch: pytest.MonkeyPatch) -> None:
    buf_in = io.StringIO("not-json{{{")
    buf_out = io.StringIO()
    monkeypatch.setattr(sys, "stdin", buf_in)
    monkeypatch.setattr(sys, "stdout", buf_out)
    try:
        runpy.run_path(str(PROMPT_HOOK), run_name="__main__")
    except SystemExit as exc:
        assert exc.code in (0, None)
    out = json.loads(buf_out.getvalue())
    assert out["continue"] is True
    assert out["permission"] == "allow"
    assert "parse" in (out.get("user_message") or "").lower()


def test_read_hook_bad_json_allows_soft(monkeypatch: pytest.MonkeyPatch) -> None:
    buf_in = io.StringIO("<<<broken")
    buf_out = io.StringIO()
    monkeypatch.setattr(sys, "stdin", buf_in)
    monkeypatch.setattr(sys, "stdout", buf_out)
    try:
        runpy.run_path(str(READ_HOOK), run_name="__main__")
    except SystemExit as exc:
        assert exc.code in (0, None)
    out = json.loads(buf_out.getvalue())
    assert out["continue"] is True
    assert out["permission"] == "allow"


def test_read_hook_denies_env(monkeypatch: pytest.MonkeyPatch) -> None:
    out = _run_hook(READ_HOOK, {"file_path": "C:/proj/.env"}, monkeypatch)
    assert out["permission"] == "deny"


def test_read_hook_off_allows_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LAKANVAULT_HOOKS", "off")
    out = _run_hook(READ_HOOK, {"file_path": "C:/proj/.env"}, monkeypatch)
    assert out["continue"] is True


def test_read_hook_allows_normal(monkeypatch: pytest.MonkeyPatch) -> None:
    out = _run_hook(READ_HOOK, {"file_path": "src/lakanvault/app/server.py"}, monkeypatch)
    assert out["permission"] == "allow"


def test_read_hook_denies_pem(monkeypatch: pytest.MonkeyPatch) -> None:
    out = _run_hook(READ_HOOK, {"path": "certs/server.pem"}, monkeypatch)
    assert out["permission"] == "deny"
