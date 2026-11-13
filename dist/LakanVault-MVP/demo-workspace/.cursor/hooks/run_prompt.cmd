@echo off
setlocal
set "HOOKS_DIR=%~dp0"
set "LAKANVAULT_HOOKS_DIR=%HOOKS_DIR%"
set "EXE=%~dp0..\..\..\tools\hook-prompt\lakanvault-hook-prompt.exe"
if not exist "%EXE%" (
  echo {"continue":false,"permission":"deny","user_message":"LakanVault: missing hook-prompt.exe - re-unzip MVP package"}
  exit /b 0
)
"%EXE%"
exit /b %ERRORLEVEL%
