<#
.SYNOPSIS
  Populate runtime/ with a llama.cpp server + a small GGUF so the standalone
  LakanVault build can serve a model on localhost with zero setup.

.DESCRIPTION
  Downloads:
    1. The latest llama.cpp Windows CPU server build -> runtime\ (llama-server.exe + DLLs)
    2. Qwen2.5-0.5B-Instruct Q4_K_M (~400 MB)        -> runtime\models\

  Re-running is safe: existing files are skipped. Drop additional *.gguf files
  into runtime\models to offer more models in the UI dropdown.

.PARAMETER ModelUrl
  Override the GGUF download URL (e.g. to bundle a different model).
#>
[CmdletBinding()]
param(
    [string]$ModelUrl  = "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf",
    [string]$ModelName = "qwen2.5-0.5b-instruct-q4_k_m.gguf"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"   # much faster Invoke-WebRequest downloads

$root      = Split-Path $PSScriptRoot -Parent
$runtime   = Join-Path $root "runtime"
$modelsDir = Join-Path $runtime "models"
New-Item -ItemType Directory -Force -Path $modelsDir | Out-Null

# ── 1. llama.cpp server ───────────────────────────────────────────────────────
$serverExe = Join-Path $runtime "llama-server.exe"
if (Test-Path $serverExe) {
    Write-Host "[ok] llama-server.exe already present" -ForegroundColor Green
}
else {
    Write-Host "[..] Finding latest llama.cpp Windows CPU build..." -ForegroundColor Cyan
    $api = "https://api.github.com/repos/ggml-org/llama.cpp/releases/latest"
    $headers = @{ "User-Agent" = "LakanVault-Setup" }
    $release = Invoke-RestMethod -Uri $api -Headers $headers
    $asset = $release.assets |
        Where-Object { $_.name -match "bin-win-cpu-x64\.zip$" } |
        Select-Object -First 1
    if (-not $asset) {
        $asset = $release.assets |
            Where-Object { $_.name -match "bin-win-avx2-x64\.zip$" } |
            Select-Object -First 1
    }
    if (-not $asset) {
        throw "Could not find a Windows CPU build in the latest llama.cpp release. Download llama-server.exe manually into $runtime."
    }

    $zip = Join-Path $env:TEMP $asset.name
    Write-Host "[..] Downloading $($asset.name) ..." -ForegroundColor Cyan
    Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $zip -Headers $headers
    Write-Host "[..] Extracting server + DLLs ..." -ForegroundColor Cyan
    $tmp = Join-Path $env:TEMP "llamacpp_extract"
    if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
    Expand-Archive -Path $zip -DestinationPath $tmp -Force
    # zips may nest files in a subfolder; copy everything (exe + dlls) flat into runtime\
    Get-ChildItem -Path $tmp -Recurse -File |
        Where-Object { $_.Extension -in ".exe", ".dll" } |
        ForEach-Object { Copy-Item $_.FullName -Destination $runtime -Force }
    Remove-Item $zip -Force
    Remove-Item $tmp -Recurse -Force

    if (-not (Test-Path $serverExe)) {
        throw "llama-server.exe not found after extraction. Check the archive layout in $runtime."
    }
    Write-Host "[ok] llama-server.exe ready" -ForegroundColor Green
}

# ── 2. GGUF model ─────────────────────────────────────────────────────────────
$modelPath = Join-Path $modelsDir $ModelName
if (Test-Path $modelPath) {
    Write-Host "[ok] $ModelName already present" -ForegroundColor Green
}
else {
    Write-Host "[..] Downloading $ModelName (~400 MB)..." -ForegroundColor Cyan
    Invoke-WebRequest -Uri $ModelUrl -OutFile $modelPath
    Write-Host "[ok] Model downloaded" -ForegroundColor Green
}

Write-Host ""
Write-Host "Runtime ready:" -ForegroundColor Green
Write-Host "  Server : $serverExe"
Get-ChildItem $modelsDir -Filter *.gguf | ForEach-Object { Write-Host "  Model  : $($_.Name)" }
Write-Host ""
Write-Host "Test now with:  .\scripts\run_ui.ps1   (then connect to http://127.0.0.1:8081)"
Write-Host "Or package for LMS with:  .\scripts\build_demo_package.ps1 -SkipFetch"
