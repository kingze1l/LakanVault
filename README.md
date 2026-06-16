# LakanVault

Hybrid, locally deployable AI security gateway. Air-gapped by default.

## Quick start

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
streamlit run src/lakanvault/app/dashboard.py
```

## Architecture

- `contracts/` — DTOs, events, ports, policies (no business logic)
- `local_core/` — integrity hashing, threat scanner, privacy (PII), audit
- `orchestration/` — pipeline runner, gateway (pure Python), event bus
- `app/` — Streamlit UI shell only; zero business logic
- `cloud_intelligence/` — optional cloud enrichment (disabled by default)

Cloud is **off by default**. Nothing leaves the machine unless `config/default.yaml` sets `cloud.enabled: true`.

## Boundary check

```powershell
python scripts/verify_boundaries.py
```

## Pipeline order

`integrity → threat_scanner → privacy → audit`

Fail-closed: any FAIL or ERROR halts the pipeline immediately.
