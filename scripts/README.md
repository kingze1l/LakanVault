# Scripts index

Run from repo root after `pip install -e .`.

## Development

| Script / command | Purpose |
|------------------|---------|
| `python -m uvicorn lakanvault.app.server:app --reload --host 127.0.0.1 --port 8080` | Dev daemon with hot reload |
| [`INSTALL_RECOMMENDED.bat`](INSTALL_RECOMMENDED.bat) | Recommended: `pip install -e ".[ner]"` + spaCy `en_core_web_lg` (dev/source; not for MVP zip) |
| [`smoke_test.py`](smoke_test.py) | Hit key endpoints + pipeline scan + proxy block |
| [`verify_boundaries.py`](verify_boundaries.py) | ADR-001 import boundary checker |
| [`setup_mcp_sandbox.ps1`](setup_mcp_sandbox.ps1) | Wire Cursor MCP sandbox against a running daemon |

## v2 packaging /  MVP

| Script | Purpose |
|--------|---------|
| [`build_tray_exe.ps1`](build_tray_exe.ps1) | PyInstaller: `LakanVault.exe`, mcp-server, mcp shim, hook-prompt, hook-read |
| [`package_mvp.ps1`](package_mvp.ps1) | Assemble `dist/LakanVault-MVP/` + zip for demo (START.bat, demo-workspace) |
| [`smoke_frozen_exe.ps1`](smoke_frozen_exe.ps1) | Frozen/MVP API smoke (`-Root dist\LakanVault-MVP`) |

## Quality gate (before commit)

```powershell
python scripts/verify_boundaries.py
python -m pytest tests/ -q
python scripts/smoke_test.py   # optional
```
