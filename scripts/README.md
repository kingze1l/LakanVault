# Scripts index

Run from repo root after `pip install -e .`.

## Development

| Script / command | Purpose |
|------------------|---------|
| `python -m uvicorn lakanvault.app.server:app --reload --host 127.0.0.1 --port 8080` | Dev daemon with hot reload |
| [`smoke_test.py`](smoke_test.py) | Hit key endpoints + pipeline scan + proxy block |
| [`verify_boundaries.py`](verify_boundaries.py) | ADR-001 import boundary checker |

## v2 packaging

| Script | Purpose |
|--------|---------|
| [`build_tray_exe.ps1`](build_tray_exe.ps1) | PyInstaller onedir: windowed `LakanVault.exe` + console `lakanvault-mcp.exe` |

## Quality gate (before commit)

```powershell
python scripts/verify_boundaries.py
python -m pytest tests/ -q
python scripts/smoke_test.py   # optional
```
