<#
.SYNOPSIS
  Smoke-test frozen LakanVault.exe (--daemon-only) + check MCP artifact exists.
#>
[CmdletBinding()]
param(
    [int]$Port = 8099,
    [int]$TimeoutSec = 90
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

$exe = Join-Path (Get-Location) "dist\LakanVault\LakanVault.exe"
$mcp = Join-Path (Get-Location) "dist\lakanvault-mcp\lakanvault-mcp.exe"
if (-not (Test-Path $exe)) { throw "Missing $exe - run scripts/build_tray_exe.ps1 first" }
if (-not (Test-Path $mcp)) { throw "Missing $mcp - run scripts/build_tray_exe.ps1 first" }

Get-Process LakanVault -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

$work = Split-Path $exe -Parent
$log = Join-Path $work "lakanvault-daemon.log"
Remove-Item $log -Force -ErrorAction SilentlyContinue

Write-Host "[..] Starting frozen daemon-only on :$Port ..."
$proc = Start-Process -FilePath $exe -ArgumentList "--daemon-only","--host","127.0.0.1","--port","$Port" `
    -WorkingDirectory $work -PassThru

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
$root = Invoke-WebRequest "http://127.0.0.1:$Port/" -UseBasicParsing
Write-Host "GET / => $($root.StatusCode)"
$san = Invoke-WebRequest "http://127.0.0.1:$Port/internal/v1/sanitize" -Method POST `
    -Body '{"text":"hi","request_id":"smoke"}' -ContentType "application/json" -UseBasicParsing
Write-Host "sanitize => $($san.StatusCode)"

$ok = $false
try {
    Invoke-WebRequest "http://127.0.0.1:$Port/v1/chat/completions" -Method POST `
        -Body '{"messages":[{"role":"user","content":"My key is sk-abcdefghijklmnopqrstuvwxyz1234567890"}]}' `
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

Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
Get-Process LakanVault -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

if ($ok) {
    Write-Host "SMOKE OK"
    exit 0
}
exit 1
