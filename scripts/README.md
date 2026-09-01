# Scripts index

All runnable scripts for LakanVault. Run from repo root unless noted.

## Development

| Script | Purpose |
|--------|---------|
| [`run_ui.ps1`](run_ui.ps1) | Start FastAPI daemon with hot reload on `:8080` |
| [`smoke_test.py`](smoke_test.py) | Hit key endpoints + pipeline scan + proxy block |
| [`verify_boundaries.py`](verify_boundaries.py) | ADR-001 import boundary checker |

## CS301 / packaging

| Script | Purpose |
|--------|---------|
| [`build_tray_exe.ps1`](build_tray_exe.ps1) | PyInstaller onedir: windowed daemon + console `lakanvault-mcp` |

## Quality gate (run before commit)

```powershell
python scripts/verify_boundaries.py
python -m pytest tests/ -q
python scripts/smoke_test.py   # optional; starts server briefly
```
