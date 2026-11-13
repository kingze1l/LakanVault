@echo off
setlocal
cd /d "%~dp0"
echo.
echo  LakanVault MVP
echo  Starting tray + local daemon on http://127.0.0.1:8080 ...
echo.
if not exist "LakanVault.exe" (
  echo ERROR: LakanVault.exe missing. Unzip the full LakanVault-MVP folder.
  pause
  exit /b 1
)
start "" "%~dp0LakanVault.exe"
timeout /t 2 /nobreak >nul
start "" notepad "%~dp0DEMO_GUIDE.md"
echo.
echo  Dashboard: http://127.0.0.1:8080/dashboard
echo  Next: In Cursor, File - Open Folder - select demo-workspace
echo  Then follow DEMO_GUIDE.md
echo.
pause
