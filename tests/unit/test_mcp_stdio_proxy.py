"""MCP stdio shim — sanitize via daemon HTTP; stdout stays protocol-only."""
from __future__ import annotations

import io
import json
from unittest.mock import patch

from lakanvault.mcp.stdio_proxy import (
    _MAX_MESSAGE,
    _read_message,
    _write_message,
    sanitize_tool_result,
)


def _frame(payload: dict) -> bytes:
    buf = io.BytesIO()
    _write_message(buf, payload)
    return buf.getvalue()


def test_content_length_round_trip() -> None:
    raw = _frame({"jsonrpc": "2.0", "id": 1, "method": "ping"})
    msg = _read_message(io.BytesIO(raw))
    assert msg == {"jsonrpc": "2.0", "id": 1, "method": "ping"}


def test_malformed_json_returns_none() -> None:
    body = b"{not-json"
    raw = f"Content-Length: {len(body)}\r\n\r\n".encode() + body
    assert _read_message(io.BytesIO(raw)) is None


def test_oversized_message_dropped() -> None:
    raw = f"Content-Length: {_MAX_MESSAGE + 1}\r\n\r\n".encode() + b"x"
    assert _read_message(io.BytesIO(raw)) is None


def test_sanitize_rewrites_text_and_blocks_binary() -> None:
    def fake_open(req, timeout=30):  # noqa: ARG001
        class Resp:
            def read(self) -> bytes:
                return json.dumps({"text": "cleaned", "blocked": False}).encode()

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        return Resp()

    result = {
        "content": [
            {"type": "text", "text": "secret jane.doe@example.com"},
            {"type": "resource", "resource": {"blob": "AAAA"}},
            {"type": "image", "data": "xxxx"},
        ]
    }
    with patch("lakanvault.mcp.stdio_proxy.urllib.request.urlopen", fake_open):
        out = sanitize_tool_result(result, "http://127.0.0.1:8080/internal/v1/sanitize", "1")
    assert out["content"][0]["text"] == "cleaned"
    assert "blocked by LakanVault" in out["content"][1]["text"]
    assert out["isError"] is True


def test_daemon_unavailable_fail_closed() -> None:
    def boom(*args, **kwargs):
        raise TimeoutError("down")

    result = {"content": [{"type": "text", "text": "secret"}]}
    with patch("lakanvault.mcp.stdio_proxy.urllib.request.urlopen", boom):
        out = sanitize_tool_result(result, "http://127.0.0.1:9/internal/v1/sanitize", "1")
    assert out["content"][0]["text"] == ""


def test_stdout_helpers_emit_only_framed_json() -> None:
    buf = io.BytesIO()
    _write_message(buf, {"jsonrpc": "2.0", "id": 1, "result": {"ok": True}})
    text = buf.getvalue().decode("utf-8")
    assert text.startswith("Content-Length:")
    assert "INFO" not in text
    assert "error" not in text.lower() or '"ok"' in text
    assert text.count("\r\n\r\n") == 1
