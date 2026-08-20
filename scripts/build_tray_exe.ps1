<#
.SYNOPSIS
  Build separate onedir artifacts:
    dist/LakanVault/LakanVault.exe     — windowed daemon/tray launcher (stdout not for MCP)
    dist/lakanvault-mcp/lakanvault-mcp.exe — console MCP stdio shim

  One windowed executable cannot host MCP stdio (stdout is not a protocol stream).
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

Write-Host "[..] Building windowed daemon (onedir, not for MCP stdio) ..."
& $python -m PyInstaller --noconfirm --clean --onedir --windowed --name LakanVault `
    --add-data "config;config" `
    --add-data "src/lakanvault/app/static;lakanvault/app/static" `
    --hidden-import uvicorn.logging `
    --hidden-import uvicorn.protocols.http.auto `
    --hidden-import lakanvault.app.server `
    src/lakanvault/launcher/__main__.py

Write-Host "[..] Building console MCP shim (stdout reserved for JSON-RPC) ..."
& $python -m PyInstaller --noconfirm --clean --onedir --console --name lakanvault-mcp `
    src/lakanvault/mcp/stdio_proxy.py

Write-Host ""
Write-Host "Artifacts:"
Write-Host "  dist\LakanVault\LakanVault.exe"
Write-Host "  dist\lakanvault-mcp\lakanvault-mcp.exe"
Write-Host "Writable data must go next to the exe (never _MEIPASS)."
