# Install local NER model for stronger PII/name detection (air-gapped after download)
Set-Location $PSScriptRoot\..

Write-Host "Installing spaCy..."
pip install "spacy>=3.7.0"

Write-Host "Downloading en_core_web_sm (~12 MB) — runs fully offline after this..."
python -m spacy download en_core_web_sm

Write-Host ""
Write-Host "Done. Restart the UI and set privacy.engine: auto in config (default)." -ForegroundColor Green
Write-Host "Test: send 'write an email for samiullah' in Sanitized Chat — name should become NAME_001."
