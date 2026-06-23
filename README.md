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

Open **http://127.0.0.1:8080** — HTML dashboard (primary demo UI).

## Quick start (markers / LMS zip)

**Recommended** — no `.exe` required (works on company laptops):

1. Download **`LakanVault_DEMO.zip`** from LMS / GitHub Release, **or** clone this repo.
2. Double-click **`RUN_DEMO.bat`** at the project root.
3. Browser opens at **http://127.0.0.1:8080**.

Full instructions: [`docs/demo/GUIDE.md`](docs/demo/GUIDE.md)  
Architecture: [`docs/demo/PROJECT_OVERVIEW.md`](docs/demo/PROJECT_OVERVIEW.md)

## Scripts

| Script | Purpose | Needed for demo? |
|--------|---------|------------------|
| `RUN_DEMO.bat` → `scripts/RUN_DEMO.ps1` | One-click start: venv, install, demo models, UI | **Yes** |
| `scripts/setup_demo_integrity.ps1` | Copy demo TRUSTED/POISONED stubs → `data/models/` | **Yes** (called by RUN_DEMO) |
| `scripts/fetch_demo_model.ps1` | Download llama-server + chat GGUF into `runtime/` | **Yes** for chat (or use LMS zip) |
| `scripts/build_demo_package.ps1` | Build `dist/LakanVault_DEMO.zip` for LMS | **Yes** (run once before upload) |
| `scripts/run_ui.ps1` | Dev hot-reload on :8080 | No — developers only |
| `scripts/verify_boundaries.py` | Architecture import checks (also runs in CI) | No — dev/CI only |

Optional Streamlit shell (ADR-004, not used by `RUN_DEMO.bat`):

```powershell
pip install -e ".[ui]"
streamlit run src/lakanvault/app/dashboard.py
```

Optional stronger PII detection (spaCy NER):

```powershell
pip install -e ".[ner]"
python -m spacy download en_core_web_sm
```

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
