# Copy committed demo integrity stubs into data/models (TRUSTED / POISONED / UNVERIFIED)
Set-Location $PSScriptRoot\..

$assetDir = Join-Path (Get-Location) "demo_assets\models"
$outDir = Join-Path (Get-Location) "data\models"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

if (-not (Test-Path $assetDir)) {
    Write-Host "demo_assets\models not found - generating stubs (dev fallback)..." -ForegroundColor Yellow
    $stubContent = New-Object byte[] 512
    $stubContent[0] = 0x47; $stubContent[1] = 0x47; $stubContent[2] = 0x55; $stubContent[3] = 0x46
    for ($i = 4; $i -lt 512; $i++) { $stubContent[$i] = [byte]($i % 256) }
    New-Item -ItemType Directory -Force -Path $assetDir | Out-Null
    foreach ($name in @("demo-trusted.gguf", "demo-poisoned-alpha.gguf", "demo-poisoned-beta.gguf", "demo-unverified.gguf")) {
        [System.IO.File]::WriteAllBytes((Join-Path $assetDir $name), $stubContent)
    }
    function Get-Sha256Hex([string]$path) {
        $sha = [System.Security.Cryptography.SHA256]::Create()
        $stream = [System.IO.File]::OpenRead($path)
        try { $bytes = $sha.ComputeHash($stream) } finally { $stream.Close(); $sha.Dispose() }
        return ([BitConverter]::ToString($bytes) -replace '-', '').ToLower()
    }
    $trustedHash = Get-Sha256Hex (Join-Path $assetDir "demo-trusted.gguf")
    @{
        "demo-trusted.gguf" = $trustedHash
        "demo-poisoned-alpha.gguf" = "0" * 64
        "demo-poisoned-beta.gguf" = "0" * 64
    } | ConvertTo-Json | Set-Content -Path (Join-Path $assetDir "baselines.json") -Encoding UTF8
}

Write-Host "Copying demo models to $outDir ..."
Get-ChildItem $assetDir -File | ForEach-Object {
    Copy-Item -Force $_.FullName (Join-Path $outDir $_.Name)
    Write-Host "  $($_.Name)"
}

Write-Host ""
Write-Host "Demo integrity data ready:"
Write-Host "  demo-trusted.gguf        -> TRUSTED   (correct baseline hash)"
Write-Host "  demo-poisoned-alpha.gguf -> POISONED  (wrong baseline)"
Write-Host "  demo-poisoned-beta.gguf  -> POISONED  (wrong baseline)"
Write-Host "  demo-unverified.gguf     -> UNVERIFIED (no baseline entry)"
Write-Host ""
Write-Host "Open Model Integrity in the UI and click Scan models."
