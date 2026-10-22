# What changed

LakanVault now runs as a local Windows gateway. It can block a secret in an OpenAI-style chat request, and Cursor can call two local tools: classify text, and list recent audit metadata.

This is a working slice, not full coverage of every Cursor or Claude request.

## You can use this now

- Start the API on `http://127.0.0.1:8080`.
- A fake API key sent to `/v1/chat/completions` is blocked before it leaves the machine.
- Cursor can call `lakanvault_classify` and `lakanvault_audit_recent` through a local MCP server.
- A tray app and a frozen `.exe` build exist for Windows.

## Not done yet

- Cursor Chat, Agent, and Tab do not automatically send every prompt through LakanVault.
- Claude Code is not connected.
- There is no dashboard UI. Use the API, the MCP tools, or the paste-check page at `http://127.0.0.1:8080/static/shim.html`.

## Check that it works

1. Open PowerShell in this folder.
2. Create and activate a virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

3. Start the API:

```powershell
python -m uvicorn lakanvault.app.server:app --host 127.0.0.1 --port 8080
```

4. In a second PowerShell window, confirm the API answers:

```powershell
Invoke-RestMethod http://127.0.0.1:8080/
```

You should see `status: api-only`.

5. Send a fake key. This should fail with HTTP 403 and must not call OpenAI:

```powershell
try {
  Invoke-WebRequest http://127.0.0.1:8080/v1/chat/completions -Method POST `
    -ContentType "application/json" `
    -Body '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"key sk-abcdefghijklmnopqrstuvwxyz1234567890"}]}'
} catch {
  $_.Exception.Response.StatusCode.value__
}
```

`403` means the block worked.

6. Optional: test Cursor without changing your everyday Cursor setup.

```powershell
.\scripts\setup_mcp_sandbox.ps1
```

Open the new `..\LakanVault-mcp-sandbox` folder (next to this repo) in a second Cursor window. Under MCP, look for `lakanvault_classify` and `lakanvault_audit_recent`. Ask that window to classify the same fake key. Expect `action: block`.

Stop the API with Ctrl+C in the first window.
