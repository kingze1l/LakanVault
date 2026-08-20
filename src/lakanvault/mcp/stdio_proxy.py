"""MCP stdio shim — wrap a child MCP server and sanitize tools/call results via the daemon.

Stdout is JSON-RPC only. Logs go to stderr. Does not import local_core or infrastructure.
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import urllib.error
import urllib.request
from subprocess import PIPE, Popen
from typing import Any, BinaryIO, TextIO

_SANITIZE_URL_DEFAULT = "http://127.0.0.1:8080/internal/v1/sanitize"
_MAX_MESSAGE = 2_000_000


def _read_message(stream: BinaryIO) -> dict[str, Any] | None:
    headers: dict[str, str] = {}
    while True:
        line = stream.readline()
        if not line:
            return None
        if line in (b"\r\n", b"\n"):
            break
        decoded = line.decode("utf-8", errors="replace")
        if ":" in decoded:
            key, value = decoded.split(":", 1)
            headers[key.strip().lower()] = value.strip()
    try:
        length = int(headers.get("content-length") or 0)
    except ValueError:
        return None
    if length <= 0 or length > _MAX_MESSAGE:
        return None
    body = stream.read(length)
    if not body:
        return None
    try:
        return json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        return None


def _write_message(stream: BinaryIO, payload: dict[str, Any]) -> None:
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    header = f"Content-Length: {len(raw)}\r\n\r\n".encode("ascii")
    stream.write(header + raw)
    stream.flush()


def _pipe_stderr(src: BinaryIO, dest: TextIO) -> None:
    try:
        while True:
            chunk = src.readline()
            if not chunk:
                return
            dest.write(chunk.decode("utf-8", errors="replace"))
            dest.flush()
    except OSError:
        return


def sanitize_tool_result(result: dict[str, Any], daemon_url: str, request_id: str) -> dict[str, Any]:
    """Rewrite text / embedded text resource contents. Block binary in strict mode."""
    content = result.get("content")
    if not isinstance(content, list):
        return result
    new_content = []
    for item in content:
        if not isinstance(item, dict):
            new_content.append(item)
            continue
        kind = item.get("type")
        if kind == "text" and isinstance(item.get("text"), str):
            clone = dict(item)
            clone["text"] = _sanitize_text(clone["text"], daemon_url, request_id)
            new_content.append(clone)
        elif kind == "resource" and isinstance(item.get("resource"), dict):
            resource = dict(item["resource"])
            if isinstance(resource.get("text"), str):
                resource["text"] = _sanitize_text(resource["text"], daemon_url, request_id)
                clone = dict(item)
                clone["resource"] = resource
                new_content.append(clone)
            elif resource.get("blob"):
                new_content.append({
                    "type": "text",
                    "text": "binary resource blocked by LakanVault",
                })
                result["isError"] = True
            else:
                new_content.append(item)
        elif kind in {"image", "audio"}:
            new_content.append({"type": "text", "text": f"{kind} content blocked by LakanVault"})
            result["isError"] = True
        else:
            new_content.append(item)
    out = dict(result)
    out["content"] = new_content
    return out


def _sanitize_text(text: str, daemon_url: str, request_id: str) -> str:
    payload = json.dumps({"text": text, "request_id": request_id, "source": "mcp"}).encode()
    req = urllib.request.Request(
        daemon_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return ""  # fail closed: empty text rather than leaking
    if data.get("blocked"):
        return ""
    return str(data.get("text") or "")


def pump(child: Popen, daemon_url: str) -> None:
    pending_calls: dict[Any, str] = {}
    lock = threading.Lock()
    assert child.stdout is not None
    assert child.stdin is not None

    def client_to_child() -> None:
        try:
            while True:
                msg = _read_message(sys.stdin.buffer)
                if msg is None:
                    break
                if msg.get("method") == "tools/call" and "id" in msg:
                    with lock:
                        pending_calls[msg["id"]] = str(msg["id"])
                _write_message(child.stdin, msg)
        finally:
            try:
                child.stdin.close()
            except OSError:
                pass

    def child_to_client() -> None:
        while True:
            msg = _read_message(child.stdout)
            if msg is None:
                return
            mid = msg.get("id")
            with lock:
                is_tool = mid in pending_calls
                pending_calls.pop(mid, None)
            if is_tool and isinstance(msg.get("result"), dict):
                msg = dict(msg)
                msg["result"] = sanitize_tool_result(msg["result"], daemon_url, str(mid))
            _write_message(sys.stdout.buffer, msg)

    inbound = threading.Thread(target=client_to_child, daemon=True)
    outbound = threading.Thread(target=child_to_client, daemon=True)
    inbound.start()
    outbound.start()
    inbound.join()
    outbound.join(timeout=5)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LakanVault MCP stdio sanitizing shim")
    parser.add_argument("--daemon-url", default=_SANITIZE_URL_DEFAULT)
    parser.add_argument("child", nargs=argparse.REMAINDER, help="child MCP command after --")
    args = parser.parse_args(argv)
    child_cmd = list(args.child)
    if child_cmd and child_cmd[0] == "--":
        child_cmd = child_cmd[1:]
    if not child_cmd:
        print("lakanvault-mcp: child command required", file=sys.stderr)
        return 2
    proc = Popen(
        child_cmd,
        stdin=PIPE,
        stdout=PIPE,
        stderr=PIPE,
        shell=False,
    )
    assert proc.stderr is not None
    threading.Thread(target=_pipe_stderr, args=(proc.stderr, sys.stderr), daemon=True).start()
    try:
        pump(proc, args.daemon_url)
    finally:
        if proc.poll() is None:
            proc.terminate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
