<#
.SYNOPSIS
  Build dist/LakanVault_DEMO.zip for LMS submission - includes offline chat runtime.
#>
[CmdletBinding()]
param(
    [switch]$SkipFetch
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

$root = Get-Location
$distRoot = Join-Path $root "dist\LakanVault_DEMO"
$zipPath = Join-Path $root "dist\LakanVault_DEMO.zip"

Write-Host ""
Write-Host "Building LakanVault demo package" -ForegroundColor Green
Write-Host "================================" -ForegroundColor Green

if (-not $SkipFetch) {
    Write-Host "[..] Ensuring runtime (llama-server + model) ..."
    & (Join-Path $PSScriptRoot "fetch_demo_model.ps1")
} else {
    Write-Host "[skip] Runtime fetch skipped" -ForegroundColor Yellow
}

Write-Host "[..] Staging demo integrity models ..."
& (Join-Path $PSScriptRoot "setup_demo_integrity.ps1")

if (Test-Path $distRoot) {
    Remove-Item $distRoot -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $distRoot | Out-Null

$excludeDirs = @(
    ".git", ".venv", "venv", "dist", "build", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".cursor", "agent-transcripts",
    "ai_planning", "docs\submission", "docs\tutor"
)

Write-Host "[..] Copying project files ..."
Get-ChildItem $root -Force | ForEach-Object {
    $name = $_.Name
    if ($excludeDirs -contains $name) { return }
    if ($name -eq "dist") { return }
    $dest = Join-Path $distRoot $name
    if ($_.PSIsContainer) {
        Copy-Item $_.FullName $dest -Recurse -Force
    } else {
        Copy-Item $_.FullName $dest -Force
    }
}

foreach ($dir in $excludeDirs) {
    $p = Join-Path $distRoot $dir
    if (Test-Path $p) { Remove-Item $p -Recurse -Force -ErrorAction SilentlyContinue }
}

$prunePaths = @(
    "scripts\privacy_research",
    "scripts\download_test_model.ps1",
    "scripts\build_exe.ps1",
    "scripts\build_tutor_package.ps1",
    "scripts\RUN_TUTOR_DEMO.ps1",
    "lakanvault.spec",
    "RUN_TUTOR_DEMO.bat"
)
foreach ($rel in $prunePaths) {
    $p = Join-Path $distRoot $rel
    if (Test-Path $p) { Remove-Item $p -Recurse -Force -ErrorAction SilentlyContinue }
}
Get-ChildItem $distRoot -Recurse -Directory -Filter __pycache__ -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

$demoDocsDst = Join-Path $distRoot "docs\demo"
New-Item -ItemType Directory -Force -Path $demoDocsDst | Out-Null
foreach ($doc in @("GUIDE.md", "PROJECT_OVERVIEW.md", "BUILD_ZIP.md")) {
    $src = Join-Path $root "docs\demo\$doc"
    if (Test-Path $src) {
        Copy-Item -Force $src (Join-Path $demoDocsDst $doc)
        Write-Host "  Included docs\demo\$doc"
    }
}

if (-not (Test-Path (Join-Path $distRoot "runtime\llama-server.exe"))) {
    Write-Host "WARNING: runtime\llama-server.exe missing - chat will be security-only." -ForegroundColor Yellow
}

if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
Write-Host "[..] Creating zip (this may take a few minutes) ..."
Compress-Archive -Path $distRoot -DestinationPath $zipPath -CompressionLevel Optimal

$sizeMb = [math]::Round((Get-Item $zipPath).Length / 1MB, 1)
Write-Host ""
Write-Host "Done:" -ForegroundColor Green
Write-Host "  Folder: dist\LakanVault_DEMO\"
Write-Host "  Zip:    dist\LakanVault_DEMO.zip  ($sizeMb MB)"
Write-Host ""
Write-Host "Instructions: unzip, double-click RUN_DEMO.bat"
