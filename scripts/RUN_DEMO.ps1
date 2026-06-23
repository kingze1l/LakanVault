<#
.SYNOPSIS
  One-click LakanVault demo - Python + venv + demo data + bundled offline model + UI.
.PARAMETER FetchRuntime
  Download llama.cpp server + Qwen 0.5B into runtime\ if missing (~450 MB, needs network).
.PARAMETER NoBrowser
  Do not open the browser automatically.
#>
[CmdletBinding()]
param(
    [switch]$FetchRuntime,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

function Write-Step([string]$msg) {
    Write-Host ""
    Write-Host "==> $msg" -ForegroundColor Cyan
}

function Test-Python312 {
    try {
        $ver = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
        if (-not $ver) { return $false }
        $parts = $ver.Trim().Split('.')
        $major = [int]$parts[0]
        $minor = [int]$parts[1]
        return ($major -gt 3) -or ($major -eq 3 -and $minor -ge 12)
    } catch {
        return $false
    }
}

Write-Host ""
Write-Host "LakanVault - Demo" -ForegroundColor Green
Write-Host "=================" -ForegroundColor Green

Write-Step "Checking Python 3.12+"
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Python not found. Install Python 3.12 or newer from python.org" -ForegroundColor Red
    Write-Host "Or use the LMS zip (LakanVault_DEMO.zip) on a machine with Python." -ForegroundColor Yellow
    exit 1
}
if (-not (Test-Python312)) {
    $v = python --version 2>&1
    Write-Host "Need Python 3.12 or newer, found: $v" -ForegroundColor Red
    exit 1
}
Write-Host "  OK: $(python --version 2>&1)" -ForegroundColor Green

Write-Step "Virtual environment + dependencies"
$venvPython = Join-Path (Get-Location) ".venv\Scripts\python.exe"
$pipExe = Join-Path (Get-Location) ".venv\Scripts\pip.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "  Creating .venv ..."
    python -m venv .venv
}
if (-not (Test-Path $pipExe)) {
    Write-Host "  Bootstrapping pip in .venv ..."
    & $venvPython -m ensurepip --upgrade
}
Write-Host "  Installing LakanVault (editable) ..."
& $venvPython -m pip install -q -e .

Write-Step "Demo integrity models (TRUSTED / POISONED / UNVERIFIED)"
& (Join-Path $PSScriptRoot "setup_demo_integrity.ps1")

Write-Step "Offline chat runtime (optional)"
$runtimeExe = Join-Path (Get-Location) "runtime\llama-server.exe"
$runtimeModels = Join-Path (Get-Location) "runtime\models"
$hasRuntime = (Test-Path $runtimeExe) -and ((Get-ChildItem $runtimeModels -Filter *.gguf -ErrorAction SilentlyContinue).Count -gt 0)

if (-not $hasRuntime -and $FetchRuntime) {
    Write-Host "  Fetching llama.cpp + Qwen 0.5B (~450 MB) ..."
    & (Join-Path $PSScriptRoot "fetch_demo_model.ps1")
    $hasRuntime = (Test-Path $runtimeExe) -and ((Get-ChildItem $runtimeModels -Filter *.gguf -ErrorAction SilentlyContinue).Count -gt 0)
}

if ($hasRuntime) {
    Write-Host "  Bundled runtime found - chat will auto-connect." -ForegroundColor Green
} else {
    Write-Host "  No bundled runtime - security-only demo (Integrity, Pipeline, Audit)." -ForegroundColor Yellow
    Write-Host "  For full chat: use LakanVault_DEMO.zip from LMS, or re-run with -FetchRuntime" -ForegroundColor Yellow
}

Write-Step "Starting LakanVault"
$bootstrapArgs = @("-m", "lakanvault.launcher.bootstrap")
if ($NoBrowser) { $bootstrapArgs += "--no-browser" }

Write-Host ""
Write-Host "  UI: http://127.0.0.1:8080" -ForegroundColor Green
Write-Host "  Press Ctrl+C to stop." -ForegroundColor DarkGray
Write-Host ""

& $venvPython @bootstrapArgs
