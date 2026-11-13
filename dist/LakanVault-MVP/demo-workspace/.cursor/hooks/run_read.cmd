@echo off
setlocal
set "HOOKS_DIR=%~dp0"
set "LAKANVAULT_HOOKS_DIR=%HOOKS_DIR%"
set "EXE=%~dp0..\..\..\tools\hook-read\lakanvault-hook-read.exe"
if not exist "%EXE%" (
  echo {"continue":true,"permission":"allow"}
  exit /b 0
)
"%EXE%"
exit /b %ERRORLEVEL%
