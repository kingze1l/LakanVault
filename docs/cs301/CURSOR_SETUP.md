# Cursor MCP setup (development path)

**Status:** Verified via SDK client + subprocess stdio tests (Oct 2026).  
**Does not claim:** MCP sees Cursor’s final assembled cloud prompt.

## What you get

| Process | Entry | Role |
|---------|-------|------|
| Native tools | `lakanvault-mcp-server` / `python -m lakanvault.mcp.stdio_server` | Exposes `lakanvault_classify` and `lakanvault_audit_recent` |
| Sanitize shim | `lakanvault-mcp` | Wraps a **child** MCP server; sanitizes `tools/call` **results** only |

Neither path intercepts Chat / Agent / Tab traffic that bypasses MCP tools.

## Prerequisites

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
```

Optional: start the daemon if you also use the sanitize shim or OpenAI proxy:

```powershell
python -m lakanvault.launcher --tray --no-runtime
```

## Enable in Cursor (template — not auto-activated)

1. Copy [`examples/cursor-mcp.json`](./examples/cursor-mcp.json) into either:
   - Project: `.cursor/mcp.json`, or
   - User: `%USERPROFILE%\.cursor\mcp.json`
2. Adjust the Python path if your venv lives elsewhere.
3. Restart Cursor or reload MCP servers (**Customize → MCPs**).
4. Confirm **Available Tools** lists `lakanvault_classify` and `lakanvault_audit_recent`.
5. Prompt Cursor to call `lakanvault_classify` on a fake key such as `sk-abcdefghijklmnopqrstuvwxyz1234567890` and expect `action: block` without the key echoed.

Logs: **Ctrl+Shift+U → MCP Logs**. Stdout from the server must stay protocol-only; diagnostics go to stderr.

## Sanitize a third-party MCP (shim)

Daemon must be listening on `127.0.0.1:8080`. Example:

```json
{
  "mcpServers": {
    "lakanvault-fs": {
      "type": "stdio",
      "command": "lakanvault-mcp",
      "args": [
        "--daemon-url",
        "http://127.0.0.1:8080/internal/v1/sanitize",
        "--",
        "npx",
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "C:\\\\path\\\\to\\\\folder"
      ]
    }
  }
}
```

Tool **arguments** are forwarded unchanged. Only tool **results** are sanitized.

## Evidence recorded in-repo

- Unit/protocol: `tests/unit/test_mcp_stdio_server.py`
- Subprocess (Cursor-like launch): `tests/unit/test_mcp_stdio_server_subprocess.py`
- Shim NDJSON + sanitize: `tests/unit/test_mcp_stdio_proxy.py`

## Honest coverage note

MCP tools only run when the host chooses them. Builtin file reads, Tab completions, and cloud chat that never calls these tools remain residual paths. For OpenAI Chat Completions traffic that you explicitly point at `http://127.0.0.1:8080/v1`, use the reverse proxy (see [`../v2/CLIENT_COMPAT.md`](../v2/CLIENT_COMPAT.md)).
