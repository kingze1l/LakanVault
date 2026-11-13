# LakanVault MVP - Demo guide

**PC needs:** Windows 10/11, Cursor, unzip. **No Python / Git / pip required.**

## Setup (once)

1. Unzip `LakanVault-MVP.zip` anywhere (Desktop is fine).
2. Double-click **`START.bat`** - tray icon should appear; daemon listens on `http://127.0.0.1:8080`.
3. Open the **dashboard** (product demo UI): `http://127.0.0.1:8080/dashboard`
   - Tray right-click -> **Open dashboard**, or Status flyout -> **Dashboard**.
4. In Cursor: **File -> Open Folder** -> select the **`demo-workspace`** folder inside this unzip (MCP + hooks).
5. Reload MCP (**Customize -> MCPs**). Tools should list `lakanvault_classify`, `lakanvault_protect`, `lakanvault_restore`, `lakanvault_audit_recent`.

If the Status flyout is blank, install [Edge WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/) or open `http://127.0.0.1:8080/status` in a browser. The full dashboard always works in a normal browser.

## Checklist

### 1. Dashboard + Tray / Status
- [ ] Browser opens `/dashboard` — brand, gate, metrics, dictionary, Prompt Review.
- [ ] Left-click tray icon -> compact Status flyout (or browser Status page).
- [ ] Flyout **Dashboard** / tray **Open dashboard** opens `/dashboard`.
- [ ] Click **Minimize (-)** or press Esc -> flyout hides.
- [ ] Left-click tray again -> Status returns.
- [ ] **Cursor chat gate** Off / Tag / On - use **Off** if chat feels stuck; **Tag** for `[[lv]]` tests; **On** gates every prompt. (Cursor MCP does **not** auto-reload - Settings -> MCP -> refresh if tools missing.)
- [ ] Dictionary: add an Overlook / Flag term on the dashboard and re-scan a prompt.

### 2. Toast only (no big panel auto-open)
Trigger a protect hit, e.g. in PowerShell:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8080/api/review -Method POST -ContentType application/json -Body '{"text":"email me at jane.doe@example.com","session_id":"demo1","llm":"never"}'
```

- [ ] Small toast appears (View / Dismiss).
- [ ] Full Status flyout does **not** pop open by itself.

### 3. Prompt Review
- [ ] Toast **View** (or Status activity row) opens Review inside the flyout.
- [ ] **Send filtered** / **Override** show a clear error if no local LLM on `:1234` (expected).

### 4. Proxy block
```powershell
try {
  Invoke-WebRequest http://127.0.0.1:8080/v1/chat/completions -Method POST -ContentType application/json -Body '{"messages":[{"role":"user","content":"My key is sk-9f8e7d6c5b4a3928170615243a4b5c6d7e8f90ab"}]}'
} catch { $_.Exception.Response.StatusCode.value__ }
```
- [ ] Result is **403**.

### 5. MCP classify (in the demo-workspace Cursor window)
Ask the agent: call `lakanvault_classify` on `sk-9f8e7d6c5b4a3928170615243a4b5c6d7e8f90ab`
- [ ] Result `action: block` (key not echoed).

### 6. Hooks (`mode.txt` = tag)
- [ ] Normal chat without `[[lv]]` works as usual.
- [ ] Send a prompt containing `[[lv]]` and a secret, e.g.
  `[[lv]] connect with postgres://admin:SuperSecret99@db.example.com/app`
  -> send is **denied** / blocked by LakanVault.

## Coverage note

This demo protects **this Cursor folder** while the daemon is running. It does not claim Tab, Copilot, or every project on the PC.

**PII engine:** this zip uses lean **regex** PII (no Python/spaCy). Stronger Presidio + spaCy NER is optional on a **Python source** checkout via `scripts\INSTALL_RECOMMENDED.bat` / README - not required for this unzip demo.
