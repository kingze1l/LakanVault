# LakanVault

Hybrid, locally deployable AI security gateway. Air-gapped by default.

## Quick start — HTML dashboard (your UI)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
.\scripts\run_ui.ps1
```

Open **http://127.0.0.1:8080**

- UI: `src/lakanvault/app/static/index.html` (based on `lakanvault_dashboard.html`)
- API: `src/lakanvault/app/server.py` → `Gateway.receive()`

## Alternative — Streamlit

```powershell
$env:PYTHONPATH="src"
python -m streamlit run src/lakanvault/app/dashboard.py
```

## Architecture

- `contracts/` — DTOs, events, ports, policies
- `local_core/` — integrity hashing, threat scanner, privacy (PII), audit
- `orchestration/` — pipeline runner, gateway (pure Python), event bus
- `app/` — HTML UI + FastAPI shell only; zero business logic
- `cloud_intelligence/` — optional cloud enrichment (disabled by default)

Cloud is **off by default**. Nothing leaves the machine unless `config/default.yaml` sets `cloud.enabled: true`.

## Boundary check

```powershell
python scripts/verify_boundaries.py
python -m pytest tests/ -q
```

## Pipeline order

`integrity → threat_scanner → privacy → audit`

Fail-closed: any FAIL or ERROR halts the pipeline immediately.
