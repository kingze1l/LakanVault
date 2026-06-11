# Download a small GGUF model into ./data/models for local pipeline testing
Set-Location $PSScriptRoot\..

$outDir = Join-Path (Get-Location) "data\models"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

# SmolLM2 360M Q4 — small enough for laptop demos (~220 MB)
$fileName = "SmolLM2-360M-Instruct.Q4_K_M.gguf"
$outFile = Join-Path $outDir $fileName
$url = "https://huggingface.co/QuantFactory/SmolLM2-360M-Instruct-GGUF/resolve/main/$fileName"

if (Test-Path $outFile) {
    Write-Host "Model already exists: $outFile"
    exit 0
}

Write-Host "Downloading $fileName to $outDir ..."
Write-Host "This is a one-time download (~220 MB)."

try {
    Invoke-WebRequest -Uri $url -OutFile $outFile -UseBasicParsing
    Write-Host "Done: $outFile"
    Write-Host "In the UI, pick it from the dropdown or use path: $outFile"
} catch {
    Write-Error "Download failed: $_"
    exit 1
}
