<#
.SYNOPSIS
  Build onedir artifacts for LakanVault MVP:
    dist/LakanVault/LakanVault.exe
    dist/lakanvault-mcp/lakanvault-mcp.exe              — sanitize shim
    dist/lakanvault-mcp-server/lakanvault-mcp-server.exe — classify/protect tools
    dist/lakanvault-hook-prompt/lakanvault-hook-prompt.exe
    dist/lakanvault-hook-read/lakanvault-hook-read.exe

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
    & $python -m pip install -e ".[tray]" -q
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
    --add-data "src/lakanvault/local_core/secrets/gitleaks.toml;lakanvault/local_core/secrets" `
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

Write-Host "[..] Building console MCP sanitize shim ..."
& $python -m PyInstaller --noconfirm --clean --onedir --console --name lakanvault-mcp `
    @excludeArgs `
    src/lakanvault/mcp/stdio_proxy.py

Write-Host "[..] Building console MCP tools server (classify/protect) ..."
& $python -m PyInstaller --noconfirm --clean --onedir --console --name lakanvault-mcp-server `
    --add-data "config;config" `
    --add-data "src/lakanvault/local_core/secrets/gitleaks.toml;lakanvault/local_core/secrets" `
    --hidden-import lakanvault.mcp.stdio_server `
    --hidden-import lakanvault.mcp.server `
    --hidden-import lakanvault.orchestration.gateway `
    --hidden-import mcp.server `
    @excludeArgs `
    src/lakanvault/mcp/stdio_server.py

Write-Host "[..] Building Cursor hook exes (no system Python on demo PC) ..."
& $python -m PyInstaller --noconfirm --clean --onedir --console --name lakanvault-hook-prompt `
    @excludeArgs `
    .cursor/hooks/lakanvault_prompt.py

& $python -m PyInstaller --noconfirm --clean --onedir --console --name lakanvault-hook-read `
    @excludeArgs `
    .cursor/hooks/lakanvault_read.py

Write-Host ""
Write-Host "Artifacts:"
Write-Host "  dist\LakanVault\LakanVault.exe"
Write-Host "  dist\lakanvault-mcp\lakanvault-mcp.exe"
Write-Host "  dist\lakanvault-mcp-server\lakanvault-mcp-server.exe"
Write-Host "  dist\lakanvault-hook-prompt\lakanvault-hook-prompt.exe"
Write-Host "  dist\lakanvault-hook-read\lakanvault-hook-read.exe"
Write-Host "Writable data must go next to the exe (never _MEIPASS)."
Write-Host "Package: .\\scripts\\package_mvp.ps1"
Write-Host "Smoke: .\\scripts\\smoke_frozen_exe.ps1"
