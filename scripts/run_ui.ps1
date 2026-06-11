# Run LakanVault HTML dashboard (your UI style) + FastAPI backend
Set-Location $PSScriptRoot\..

$env:PYTHONPATH = "src"
python -m uvicorn lakanvault.app.server:app --reload --host 127.0.0.1 --port 8080
