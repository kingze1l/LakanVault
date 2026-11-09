@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
if exist "%CD%\.venv\Scripts\python.exe" (
  "%CD%\.venv\Scripts\python.exe" "%SCRIPT_DIR%lakanvault_prompt.py"
) else if exist "%SCRIPT_DIR%..\..\..\.venv\Scripts\python.exe" (
  "%SCRIPT_DIR%..\..\..\.venv\Scripts\python.exe" "%SCRIPT_DIR%lakanvault_prompt.py"
) else (
  python "%SCRIPT_DIR%lakanvault_prompt.py"
)
exit /b %ERRORLEVEL%
