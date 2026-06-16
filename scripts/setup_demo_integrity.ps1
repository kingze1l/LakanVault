# Setup demo model integrity states (TRUSTED / POISONED / UNVERIFIED)
Set-Location $PSScriptRoot\..

$outDir = Join-Path (Get-Location) "data\models"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$stubContent = New-Object byte[] 512
$stubContent[0] = 0x47; $stubContent[1] = 0x47; $stubContent[2] = 0x55; $stubContent[3] = 0x46
for ($i = 4; $i -lt 512; $i++) { $stubContent[$i] = [byte]($i % 256) }

$files = @(
    "demo-trusted.gguf",
    "demo-poisoned-alpha.gguf",
    "demo-poisoned-beta.gguf",
    "demo-unverified.gguf"
)

function Get-Sha256Hex([string]$path) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $stream = [System.IO.File]::OpenRead($path)
    try {
        $bytes = $sha.ComputeHash($stream)
    } finally {
        $stream.Close()
        $sha.Dispose()
    }
    return ([BitConverter]::ToString($bytes) -replace '-', '').ToLower()
}

Write-Host "Creating demo stub models in $outDir ..."
foreach ($name in $files) {
    $path = Join-Path $outDir $name
    [System.IO.File]::WriteAllBytes($path, $stubContent)
    Write-Host "  $name"
}

$trustedHash = Get-Sha256Hex (Join-Path $outDir "demo-trusted.gguf")
$wrongHash = "0" * 64  # deliberate mismatch for poisoned demos

$baselines = @{
    "demo-trusted.gguf"         = $trustedHash
    "demo-poisoned-alpha.gguf"  = $wrongHash
    "demo-poisoned-beta.gguf"   = $wrongHash
}

$baselinePath = Join-Path $outDir "baselines.json"
$baselines | ConvertTo-Json | Set-Content -Path $baselinePath -Encoding UTF8

Write-Host ""
Write-Host "baselines.json written:"
Write-Host "  demo-trusted.gguf        -> TRUSTED   (correct hash)"
Write-Host "  demo-poisoned-alpha.gguf -> POISONED  (wrong baseline)"
Write-Host "  demo-poisoned-beta.gguf  -> POISONED  (wrong baseline)"
Write-Host "  demo-unverified.gguf     -> UNVERIFIED (no baseline entry)"
Write-Host ""
Write-Host "Open Model Integrity in the UI and click Eject on poisoned models."
