# LakanVault

Hybrid, locally deployable AI security gateway. Air-gapped by default.

**Repository:** [GITHUB URL — placeholder]

## Quick start (developers)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
.\scripts\run_ui.ps1
```

Open **http://127.0.0.1:8080** — HTML dashboard (primary UI).

## Quick start (markers / LMS zip)

**Recommended** — no `.exe` required (works on company laptops):

1. Download **`LakanVault_DEMO.zip`** from LMS / GitHub Release, **or** clone this repo.
2. Double-click **`RUN_DEMO.bat`** at the project root.
3. Browser opens at **http://127.0.0.1:8080**.

Full instructions: [`docs/demo/GUIDE.md`](docs/demo/GUIDE.md)  
Architecture: [`docs/demo/PROJECT_OVERVIEW.md`](docs/demo/PROJECT_OVERVIEW.md)

Build the LMS zip (before submission):

```powershell
.\scripts\build_demo_package.ps1
```

Output: `dist/LakanVault_DEMO.zip`

## Run demo locally

```powershell
.\scripts\RUN_DEMO.ps1
# or double-click RUN_DEMO.bat
```

Demo integrity models ship in `demo_assets/models/` and are copied automatically.

1. **Model Integrity** → Scan → show poisoned hash mismatch  
2. **Sanitized Chat** → starter chips or PII demo (needs bundled runtime or LM Studio)  
3. **Pipeline Scan** → run on `demo-trusted.gguf`  
4. **Audit Log** → view recorded run  

## Cybersecurity features (205 elective)

| Area | Implementation |
|------|----------------|
| Cryptography | SHA-256 model hashing, baseline verification |
| CIA | PII confidentiality, integrity checks, local availability, localhost-only policy |
| Threat scanning | Threat scanner stage, poisoned model detection |
| Privacy | PII anonymization before local LLM inference |

## Architecture

- `contracts/` — DTOs, events, ports, policies (no business logic)
- `local_core/` — integrity hashing, threat scanner, privacy (PII), audit
- `orchestration/` — pipeline runner, gateway (pure Python), event bus
- `app/` — FastAPI + HTML UI shell; zero business logic in UI
- `cloud_intelligence/` — optional cloud enrichment (disabled by default)

Cloud is **off by default**. Nothing leaves the machine unless `config/local.yaml` sets `cloud.enabled: true`.

## Local AI providers

OpenAI-compatible **localhost** only (LM Studio, Ollama, llama.cpp). Configure in Settings or the Chat connect bar.

## Build LMS demo package

```powershell
.\scripts\build_demo_package.ps1
```

Output: `dist/LakanVault_DEMO.zip` — see [`docs/demo/BUILD_ZIP.md`](docs/demo/BUILD_ZIP.md)

## Tests

```powershell
python scripts/verify_boundaries.py
python -m pytest tests/ -q
```

## Pipeline order

`integrity → threat_scanner → privacy → audit`

Fail-closed: any FAIL or ERROR halts the pipeline immediately.

## Documentation

- **Demo:** [`docs/demo/GUIDE.md`](docs/demo/GUIDE.md) · [`docs/demo/PROJECT_OVERVIEW.md`](docs/demo/PROJECT_OVERVIEW.md)
- Architecture ADRs: `docs/architecture/`
- Technical report stays local only (`docs/submission/` — gitignored)

## Team

| Role | Name |
|------|------|
| Cybersecurity lead | [ Samiullah ] |
| LLM integration reviewer | Kartik Goel |
| Scrum Master | [Rouwa Yalda] |
| Product Owner | [ Samiullah ] |
