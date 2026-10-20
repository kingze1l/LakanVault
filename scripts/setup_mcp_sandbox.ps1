<#
.SYNOPSIS
  Create a separate git worktree + venv for Cursor MCP testing.

  Opens as its own Cursor window so your daily Cursor user MCP config is untouched.
  Project MCP lives only in the sandbox `.cursor/mcp.json` (gitignored).
#>
[CmdletBinding()]
param(
    [string]$SandboxPath = (Join-Path (Split-Path $PSScriptRoot -Parent | Split-Path -Parent) "LakanVault-mcp-sandbox"),
    [string]$Branch = "CS301"
)

$ErrorActionPreference = "Stop"
$repo = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repo

if (Test-Path $SandboxPath) {
    Write-Host "[..] Sandbox already exists: $SandboxPath"
} else {
    Write-Host "[..] Creating worktree at $SandboxPath (branch $Branch) ..."
    git worktree add $SandboxPath $Branch
}

$python = $null
foreach ($candidate in @("python", "py")) {
    try {
        & $candidate --version | Out-Null
        $python = $candidate
        break
    } catch { continue }
}
if (-not $python) { throw "Python is required." }

$venv = Join-Path $SandboxPath ".venv"
if (-not (Test-Path $venv)) {
    Write-Host "[..] Creating venv ..."
    & $python -m venv $venv
}

$pip = Join-Path $venv "Scripts\pip.exe"
$py = Join-Path $venv "Scripts\python.exe"
Write-Host "[..] Installing package + MCP SDK ..."
& $pip install -e "$SandboxPath[dev]"

$cursorDir = Join-Path $SandboxPath ".cursor"
New-Item -ItemType Directory -Force -Path $cursorDir | Out-Null
$example = Join-Path $SandboxPath "docs\cs301\examples\cursor-mcp.json"
Copy-Item $example (Join-Path $cursorDir "mcp.json") -Force

Write-Host ""
Write-Host "Sandbox ready (does NOT edit %USERPROFILE%\.cursor\mcp.json)."
Write-Host "  Folder: $SandboxPath"
Write-Host "  MCP:    $SandboxPath\.cursor\mcp.json"
Write-Host ""
Write-Host "Next:"
Write-Host "  1. File → Open Folder → $SandboxPath   (second Cursor window)"
Write-Host "  2. Customize → MCPs → confirm lakanvault_classify / lakanvault_audit_recent"
Write-Host "  3. Optional smoke from sandbox:"
Write-Host "       & '$py' -m pytest tests/unit/test_mcp_stdio_server_subprocess.py -q"
Write-Host "  4. Keep your normal LakanVault / other projects open without this MCP."
