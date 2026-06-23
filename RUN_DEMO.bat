@echo off
REM LakanVault demo — double-click to start (no .exe required)
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\RUN_DEMO.ps1" %*
if errorlevel 1 pause
