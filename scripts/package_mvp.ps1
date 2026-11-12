<#
.SYNOPSIS
  Assemble LakanVault-MVP/ (product demo) and zip to dist/LakanVault-MVP.zip.

  Prerequisites: .\scripts\build_tray_exe.ps1
#>
[CmdletBinding()]
param(
    [switch]$SkipBuild,
    [switch]$SkipZip
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

if (-not $SkipBuild) {
    Write-Host "[..] Building frozen artifacts ..."
    & "$PSScriptRoot\build_tray_exe.ps1" -SkipInstall:$false
}

$required = @(
    "dist\LakanVault\LakanVault.exe",
    "dist\lakanvault-mcp\lakanvault-mcp.exe",
    "dist\lakanvault-mcp-server\lakanvault-mcp-server.exe",
    "dist\lakanvault-hook-prompt\lakanvault-hook-prompt.exe",
    "dist\lakanvault-hook-read\lakanvault-hook-read.exe"
)
foreach ($rel in $required) {
    if (-not (Test-Path $rel)) {
        throw "Missing $rel - run scripts\build_tray_exe.ps1 first"
    }
}

$root = Join-Path (Get-Location) "dist\LakanVault-MVP"
if (Test-Path $root) {
    Remove-Item -Recurse -Force $root
}
New-Item -ItemType Directory -Path $root | Out-Null

function Copy-Onedir {
    param([string]$SrcDir, [string]$DestDir)
    New-Item -ItemType Directory -Path $DestDir -Force | Out-Null
    Copy-Item -Path (Join-Path $SrcDir "*") -Destination $DestDir -Recurse -Force
}

Write-Host "[..] Copying tray onedir to MVP root ..."
Copy-Onedir "dist\LakanVault" $root

Write-Host "[..] Copying MCP + hook tools ..."
Copy-Onedir "dist\lakanvault-mcp-server" (Join-Path $root "mcp")
Copy-Onedir "dist\lakanvault-mcp" (Join-Path $root "mcp\shim")
Copy-Onedir "dist\lakanvault-hook-prompt" (Join-Path $root "tools\hook-prompt")
Copy-Onedir "dist\lakanvault-hook-read" (Join-Path $root "tools\hook-read")

# MCP cwd is often demo-workspace; also ship config at MVP root for the cmd launcher.
Write-Host "[..] Copying config/ for MCP cwd ..."
$configDest = Join-Path $root "config"
New-Item -ItemType Directory -Path $configDest -Force | Out-Null
Copy-Item -Path "config\default.yaml" -Destination $configDest -Force
if (Test-Path "config\cloud.example.yaml") {
    Copy-Item -Path "config\cloud.example.yaml" -Destination $configDest -Force
}

$demo = Join-Path $root "demo-workspace"
New-Item -ItemType Directory -Path (Join-Path $demo ".cursor\hooks") -Force | Out-Null

@'
LakanVault MVP - open THIS folder in Cursor (File -> Open Folder).

1. Run ..\START.bat first (tray + daemon on http://127.0.0.1:8080).
2. Open the product demo UI: http://127.0.0.1:8080/dashboard
   (tray menu: Open dashboard — or Status flyout -> Dashboard)
3. Reload MCP servers in Cursor (Customize -> MCPs).
4. Follow ..\DEMO_GUIDE.md

Hooks use tag mode: only prompts containing [[lv]] are gated.
Cursor stays on this demo-workspace for MCP/hooks; the browser dashboard
is the first-class product demo surface beside it.
'@ | Set-Content -Path (Join-Path $demo "README.txt") -Encoding UTF8

@'
{
  "version": 1,
  "hooks": {
    "beforeSubmitPrompt": [
      {
        "command": ".cursor/hooks/run_prompt.cmd",
        "failClosed": true
      }
    ],
    "beforeReadFile": [
      {
        "command": ".cursor/hooks/run_read.cmd",
        "failClosed": true
      }
    ]
  }
}
'@ | Set-Content -Path (Join-Path $demo ".cursor\hooks.json") -Encoding UTF8

"tag" | Set-Content -Path (Join-Path $demo ".cursor\hooks\mode.txt") -Encoding ASCII

@'
@echo off
setlocal
set "HOOKS_DIR=%~dp0"
set "LAKANVAULT_HOOKS_DIR=%HOOKS_DIR%"
set "EXE=%~dp0..\..\..\tools\hook-prompt\lakanvault-hook-prompt.exe"
if not exist "%EXE%" (
  echo {"continue":false,"permission":"deny","user_message":"LakanVault: missing hook-prompt.exe - re-unzip MVP package"}
  exit /b 0
)
"%EXE%"
exit /b %ERRORLEVEL%
'@ | Set-Content -Path (Join-Path $demo ".cursor\hooks\run_prompt.cmd") -Encoding ASCII

@'
@echo off
setlocal
set "HOOKS_DIR=%~dp0"
set "LAKANVAULT_HOOKS_DIR=%HOOKS_DIR%"
set "EXE=%~dp0..\..\..\tools\hook-read\lakanvault-hook-read.exe"
if not exist "%EXE%" (
  echo {"continue":true,"permission":"allow"}
  exit /b 0
)
"%EXE%"
exit /b %ERRORLEVEL%
'@ | Set-Content -Path (Join-Path $demo ".cursor\hooks\run_read.cmd") -Encoding ASCII

$demoGuide = @'
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
'@
Set-Content -Path (Join-Path $root "DEMO_GUIDE.md") -Value $demoGuide -Encoding UTF8

$startBat = @'
@echo off
setlocal
cd /d "%~dp0"
echo.
echo  LakanVault MVP
echo  Starting tray + local daemon on http://127.0.0.1:8080 ...
echo.
if not exist "LakanVault.exe" (
  echo ERROR: LakanVault.exe missing. Unzip the full LakanVault-MVP folder.
  pause
  exit /b 1
)
start "" "%~dp0LakanVault.exe"
timeout /t 2 /nobreak >nul
start "" notepad "%~dp0DEMO_GUIDE.md"
echo.
echo  Dashboard: http://127.0.0.1:8080/dashboard
echo  Next: In Cursor, File - Open Folder - select demo-workspace
echo  Then follow DEMO_GUIDE.md
echo.
pause
'@
Set-Content -Path (Join-Path $root "START.bat") -Value $startBat -Encoding ASCII

# Fix MCP path: Cursor on Windows often needs backslash or a .cmd launcher
@'
@echo off
setlocal
REM Cursor cwd is often demo-workspace. Switch to MVP root, then run MCP.
cd /d "%~dp0.."
if not exist "mcp\lakanvault-mcp-server.exe" (
  echo LakanVault MCP missing: mcp\lakanvault-mcp-server.exe 1>&2
  exit /b 1
)
"mcp\lakanvault-mcp-server.exe" %*
exit /b %ERRORLEVEL%
'@ | Set-Content -Path (Join-Path $demo "run-mcp-server.cmd") -Encoding ASCII
# Cursor on Windows: ../ in "command" gives ENOENT. Use cmd.exe + launcher .cmd.
@'
{
  "mcpServers": {
    "lakanvault": {
      "type": "stdio",
      "command": "cmd.exe",
      "args": ["/c", "${workspaceFolder}\\run-mcp-server.cmd"]
    }
  }
}
'@ | Set-Content -Path (Join-Path $demo ".cursor\mcp.json") -Encoding UTF8

if (-not $SkipZip) {
    $zip = Join-Path (Get-Location) "dist\LakanVault-MVP.zip"
    if (Test-Path $zip) { Remove-Item $zip -Force }
    Write-Host "[..] Zipping $zip ..."
    # tar avoids Compress-Archive locks on PyInstaller base_library.zip
    & tar -a -c -f $zip -C (Split-Path $root -Parent) (Split-Path $root -Leaf)
    if (-not (Test-Path $zip)) { throw "Failed to create $zip" }
    Write-Host "Created $zip ($((Get-Item $zip).Length) bytes)"
}

Write-Host ""
Write-Host "MVP tree: $root"
Write-Host "Share:    dist\LakanVault-MVP.zip"
Write-Host "Smoke:    .\scripts\smoke_frozen_exe.ps1 -Root dist\LakanVault-MVP"
