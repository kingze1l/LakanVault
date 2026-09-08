<#
.SYNOPSIS
  Build separate onedir artifacts:
    dist/LakanVault/LakanVault.exe     — windowed tray + spawns --daemon-only child
    dist/lakanvault-mcp/lakanvault-mcp.exe — console MCP stdio shim

  Heavy optional ML stacks (spaCy/pandas/…) are excluded so the freeze stays lean.
  DLP still works via regex engines (LAKANVAULT_PRIVACY_ENGINE=regex in the child).
#>
[CmdletBinding()]
param(
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

$python = $null
foreach ($candidate in @("python", "py")) {
    try {
        & $candidate --version | Out-Null
        $python = $candidate
        break
    } catch {
        continue
    }
}
if (-not $python) {
    throw "Python is required to build onedir artifacts."
}

if (-not $SkipInstall) {
    Write-Host "[..] Installing packaging extra (pyinstaller) ..."
    & $python -m pip install -e ".[packaging]"
}

$exclude = @(
    "spacy", "thinc", "blis", "cymem", "preshed", "murmurhash", "srsly", "wasabi",
    "pandas", "pyarrow", "matplotlib", "scipy", "sklearn", "torch", "tensorflow",
    "pytest", "IPython", "notebook", "tkinter"
)
$excludeArgs = @()
foreach ($mod in $exclude) {
    $excludeArgs += @("--exclude-module", $mod)
}

Write-Host "[..] Building windowed daemon (onedir, not for MCP stdio) ..."
& $python -m PyInstaller --noconfirm --clean --onedir --windowed --name LakanVault `
    --add-data "config;config" `
    --add-data "src/lakanvault/app/static;lakanvault/app/static" `
    --hidden-import uvicorn.logging `
    --hidden-import uvicorn.protocols.http.auto `
    --hidden-import uvicorn.protocols.http.h11_impl `
    --hidden-import uvicorn.protocols.websockets.auto `
    --hidden-import uvicorn.lifespan.on `
    --hidden-import lakanvault.app.server `
    --hidden-import lakanvault.tray.app `
    --hidden-import pystray._win32 `
    --hidden-import PIL.Image `
    @excludeArgs `
    src/lakanvault/launcher/__main__.py

Write-Host "[..] Building console MCP shim (stdout reserved for JSON-RPC) ..."
& $python -m PyInstaller --noconfirm --clean --onedir --console --name lakanvault-mcp `
    @excludeArgs `
    src/lakanvault/mcp/stdio_proxy.py

Write-Host ""
Write-Host "Artifacts:"
Write-Host "  dist\LakanVault\LakanVault.exe"
Write-Host "  dist\lakanvault-mcp\lakanvault-mcp.exe"
Write-Host "Writable data must go next to the exe (never _MEIPASS)."
Write-Host "Smoke: .\\scripts\\smoke_frozen_exe.ps1"
