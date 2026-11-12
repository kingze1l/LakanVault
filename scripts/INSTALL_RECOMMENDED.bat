@echo off
setlocal
REM Recommended stronger PII: spaCy NER + en_core_web_lg (dev/source installs only).
REM Frozen LakanVault-MVP.zip does not need this — it uses regex PII.
REM Run from anywhere; cwd switches to repo root (parent of scripts\).

cd /d "%~dp0.."
where python >nul 2>&1
if errorlevel 1 (
  echo ERROR: Python not found on PATH. Install Python 3.12+ then retry.
  exit /b 1
)
where pip >nul 2>&1
if errorlevel 1 (
  echo ERROR: pip not found on PATH.
  exit /b 1
)

echo Installing spaCy via pyproject [ner] extra...
pip install -e ".[ner]"
if errorlevel 1 (
  echo ERROR: pip install -e ".[ner]" failed.
  exit /b 1
)

echo Downloading spaCy model en_core_web_lg...
python -m spacy download en_core_web_lg
if errorlevel 1 (
  echo ERROR: spaCy model download failed.
  exit /b 1
)

echo.
echo Recommended NER install complete.
echo Restart the daemon without LAKANVAULT_PRIVACY_ENGINE=regex to use Presidio+spaCy.
exit /b 0
