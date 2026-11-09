# What changed

LakanVault now runs as a local Windows gateway. It can block a secret in an OpenAI-style chat request, and Cursor can call two local tools: classify text, and list recent audit metadata.

**Slice 1 (one sanitizer on main doors):** `/v1/chat/completions`, `/internal/v1/sanitize`, and `/api/chat` now use Joan’s `process_input` / Vault (Presidio PII + format-preserving fakes). Secrets still **block** (HTTP 403 / no upstream). Emails and other MASK findings go out as surrogates and are restored on the way back. MCP `lakanvault_protect` uses the same `decide()` rule (SECRET → empty sanitized; PII → mask + restore).

**Slice 2 (hooks + Prompt Review):** `GET /review` UI plus loopback `POST /api/review` / `/api/review/send`. Cursor project hooks (`beforeSubmitPrompt` / `beforeReadFile`) call the daemon — secrets are denied in this workspace; sensitive files are blocked from reads.

This is a working slice, not full coverage of every Cursor or Claude request.

## You can use this now

- Start the API on `http://127.0.0.1:8080`.
- Open Prompt Review at `http://127.0.0.1:8080/review`.
- A fake API key sent to `/v1/chat/completions` is blocked before it leaves the machine.
- Cursor can call `lakanvault_classify`, `lakanvault_protect` / `restore`, and `lakanvault_audit_recent` through a local MCP server.
- Project Cursor hooks deny blocked prompts when the daemon is up (this workspace only).
- A tray app and a frozen `.exe` build exist for Windows.

## Not done yet

- Cursor Tab / Copilot / browser ChatGPT are not covered by these hooks.
- Claude Code is not connected.
- Cursor hooks cannot rewrite a MASK’d prompt in place — use `/review` or MCP protect for surrogates.

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

Open `C:\Users\1Admin\source\repos\LakanVault-mcp-sandbox` in a second Cursor window. Under MCP, look for `lakanvault_classify` and `lakanvault_audit_recent`. Ask that window to classify the same fake key. Expect `action: block`.

Stop the API with Ctrl+C in the first window.
