@echo off
setlocal
REM Cursor cwd is often demo-workspace. Switch to MVP root, then run MCP.
cd /d "%~dp0.."
if not exist "mcp\lakanvault-mcp-server.exe" (
  echo LakanVault MCP missing: mcp\lakanvault-mcp-server.exe 1>&2
  exit /b 1
)
"mcp\lakanvault-mcp-server.exe" %*
exit /b %ERRORLEVEL%
