<#
.SYNOPSIS
  Smoke-test frozen LakanVault.exe (--daemon-only) + MVP artifacts if present.
#>
[CmdletBinding()]
param(
    [string]$Root = "",
    [int]$Port = 8099,
    [int]$TimeoutSec = 120
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

if (-not $Root) {
    if (Test-Path "dist\LakanVault-MVP\LakanVault.exe") {
        $Root = "dist\LakanVault-MVP"
    } else {
        $Root = "dist\LakanVault"
    }
}
$Root = (Resolve-Path $Root).Path

$exe = Join-Path $Root "LakanVault.exe"
if (-not (Test-Path $exe)) { throw "Missing $exe" }

$mcpServer = @(
    (Join-Path $Root "mcp\lakanvault-mcp-server.exe"),
    (Join-Path $Root "..\lakanvault-mcp-server\lakanvault-mcp-server.exe")
) | Where-Object { Test-Path $_ } | Select-Object -First 1

$mcpShim = @(
    (Join-Path $Root "mcp\shim\lakanvault-mcp.exe"),
    (Join-Path $Root "mcp\lakanvault-mcp.exe"),
    (Join-Path $Root "..\lakanvault-mcp\lakanvault-mcp.exe")
) | Where-Object { Test-Path $_ } | Select-Object -First 1

$hookPrompt = Join-Path $Root "tools\hook-prompt\lakanvault-hook-prompt.exe"
$hookRead = Join-Path $Root "tools\hook-read\lakanvault-hook-read.exe"
$demoHooks = Join-Path $Root "demo-workspace\.cursor\hooks.json"

Write-Host "Root: $Root"
if ($mcpServer) { Write-Host "MCP server: $mcpServer" } else { Write-Host "WARN: mcp-server exe not found (ok for tray-only dist)" }
if ($mcpShim) { Write-Host "MCP shim: $mcpShim" }
if (Test-Path $hookPrompt) { Write-Host "Hook prompt: OK" }
if (Test-Path $hookRead) { Write-Host "Hook read: OK" }
if (Test-Path $demoHooks) { Write-Host "demo-workspace hooks: OK" }

Get-Process LakanVault -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

$log = Join-Path $Root "lakanvault-daemon.log"
Remove-Item $log -Force -ErrorAction SilentlyContinue

Write-Host "[..] Starting frozen daemon-only on :$Port ..."
$proc = Start-Process -FilePath $exe -ArgumentList "--daemon-only","--host","127.0.0.1","--port","$Port" `
    -WorkingDirectory $Root -PassThru

$ready = $false
$deadline = (Get-Date).AddSeconds($TimeoutSec)
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 1
    try {
        $r = Invoke-WebRequest "http://127.0.0.1:$Port/api/config" -UseBasicParsing -TimeoutSec 2
        if ($r.StatusCode -eq 200) { $ready = $true; break }
    } catch {}
}

if (-not $ready) {
    Write-Host "NOT READY. Log:"
    if (Test-Path $log) { Get-Content $log -Raw }
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    exit 1
}

Write-Host "GET /api/config => 200"
$rootResp = Invoke-WebRequest "http://127.0.0.1:$Port/" -UseBasicParsing
Write-Host "GET / => $($rootResp.StatusCode)"
$san = Invoke-WebRequest "http://127.0.0.1:$Port/internal/v1/sanitize" -Method POST `
    -Body '{"text":"hi","request_id":"smoke"}' -ContentType "application/json" -UseBasicParsing
Write-Host "sanitize => $($san.StatusCode)"

$status = Invoke-WebRequest "http://127.0.0.1:$Port/status" -UseBasicParsing
Write-Host "GET /status => $($status.StatusCode)"

$ok = $false
# Use a real-shaped key (alphabet sk-… strings are allowlisted by gitleaks).
try {
    Invoke-WebRequest "http://127.0.0.1:$Port/v1/chat/completions" -Method POST `
        -Body '{"messages":[{"role":"user","content":"My key is sk-9f8e7d6c5b4a3928170615243a4b5c6d7e8f90ab"}]}' `
        -ContentType "application/json" -UseBasicParsing | Out-Null
    Write-Host "proxy secret UNEXPECTED allow"
} catch {
    $code = $_.Exception.Response.StatusCode.value__
    if ($code -eq 403) {
        Write-Host "proxy secret => 403 OK"
        $ok = $true
    } else {
        Write-Host "proxy secret => $code / $($_.Exception.Message)"
    }
}

# Hook exe smoke: allow path when mode tag and no [[lv]]
if ((Test-Path $hookPrompt) -and (Test-Path (Join-Path $Root "demo-workspace\.cursor\hooks"))) {
    $env:LAKANVAULT_HOOKS_DIR = Join-Path $Root "demo-workspace\.cursor\hooks"
    $env:LAKANVAULT_REVIEW_URL = "http://127.0.0.1:$Port/api/review"
    $payload = '{"prompt":"hello safe"}'
    $out = $payload | & $hookPrompt 2>$null
    Write-Host "hook-prompt allow => $out"
    if ($out -notmatch '"continue"\s*:\s*true') {
        Write-Host "WARN: hook-prompt did not allow safe prompt"
    }
    $payload2 = '{"prompt":"[[lv]] connect with postgres://admin:SuperSecret99@db.example.com/app"}'
    $out2 = $payload2 | & $hookPrompt 2>$null
    Write-Host "hook-prompt block => $out2"
    if ($out2 -notmatch '"continue"\s*:\s*false') {
        Write-Host "hook-prompt block FAILED"
        $ok = $false
    } else {
        Write-Host "hook-prompt block OK"
    }
    Remove-Item Env:LAKANVAULT_HOOKS_DIR -ErrorAction SilentlyContinue
    Remove-Item Env:LAKANVAULT_REVIEW_URL -ErrorAction SilentlyContinue
}

Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
Get-Process LakanVault -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

if ($Root -match "LakanVault-MVP") {
    if (-not $mcpServer) { Write-Host "MVP missing mcp-server"; $ok = $false }
    if (-not (Test-Path $hookPrompt)) { Write-Host "MVP missing hook-prompt"; $ok = $false }
    if (-not (Test-Path $demoHooks)) { Write-Host "MVP missing demo-workspace"; $ok = $false }
    if (-not (Test-Path (Join-Path $Root "START.bat"))) { Write-Host "MVP missing START.bat"; $ok = $false }
    if (-not (Test-Path (Join-Path $Root "DEMO_GUIDE.md"))) { Write-Host "MVP missing DEMO_GUIDE.md"; $ok = $false }
}

if ($ok) {
    Write-Host "SMOKE OK"
    exit 0
}
exit 1
