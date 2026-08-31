# Scripts index

All runnable scripts for LakanVault. Run from repo root unless noted.

## Demo / LMS (markers)

| Script | Purpose |
|--------|---------|
| [`RUN_DEMO.ps1`](RUN_DEMO.ps1) | Full demo: venv, install, models, start UI on `:8080` |
| [`setup_demo_integrity.ps1`](setup_demo_integrity.ps1) | Copy demo TRUSTED/POISONED stubs → `data/models/` |
| [`fetch_demo_model.ps1`](fetch_demo_model.ps1) | Download llama-server + small GGUF → `runtime/` |
| [`build_demo_package.ps1`](build_demo_package.ps1) | Build `dist/LakanVault_DEMO.zip` for LMS upload |

**Entry point:** `RUN_DEMO.bat` at repo root → calls `RUN_DEMO.ps1`.

## Development

| Script | Purpose |
|--------|---------|
| [`run_ui.ps1`](run_ui.ps1) | Start FastAPI dashboard with hot reload |
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
