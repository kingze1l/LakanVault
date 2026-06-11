# LakanVault — project files guide

What each major file does and how the system runs end-to-end.

---

## How to run (quick)

```powershell
cd c:\Users\1Admin\source\repos\LakanVault
pip install -e .

# 1) Download a small test model (first time only)
.\scripts\download_test_model.ps1

# 2) Start the HTML dashboard + API
.\scripts\run_ui.ps1
```

Open **http://127.0.0.1:8080**

- **Folder icon** — pick a models directory (Windows native dialog)
- **File icon** — pick a single `.gguf` / `.bin` / `.safetensors` file
- **Dropdown** — lists models found in `./data/models`
- **Run** — executes the security pipeline on that file

> **Note:** LakanVault currently **scans and verifies** model files (hash, host checks, PII on prompts). It does **not** run LLM inference yet. Your model is the *target* of the integrity pipeline.

---

## Config

| File | Purpose |
|------|---------|
| [`config/default.yaml`](../config/default.yaml) | Baseline settings — cloud off, 1 MB hash chunks, pipeline order |
| [`config/local.yaml`](../config/local.yaml) | My machine overrides (paths) |
| [`config/cloud.example.yaml`](../config/cloud.example.yaml) | Hybrid mode template (no secrets) |

Key values:

- `local.models_dir` — where test models live (`./data/models`)
- `local.chunk_size_bytes` — `1048576` (1 MB) for streaming SHA-256 on large files
- `cloud.enabled` — `false` by default (air-gapped)

---

## App layer (UI only)

| File | What it does |
|------|----------------|
| [`src/lakanvault/app/server.py`](../src/lakanvault/app/server.py) | FastAPI server — serves HTML, exposes `/api/scan`, `/api/models`, `/api/pick-file`, `/api/pick-folder` |
| [`src/lakanvault/app/static/index.html`](../src/lakanvault/app/static/index.html) | Your HTML dashboard UI (pipeline bar, metrics, audit, config) |
| [`src/lakanvault/app/picker.py`](../src/lakanvault/app/picker.py) | Windows file/folder dialogs + model file listing |
| [`src/lakanvault/app/dashboard.py`](../src/lakanvault/app/dashboard.py) | Optional Streamlit UI (same gateway, different skin) |
| [`lakanvault_dashboard.html`](../lakanvault_dashboard.html) | Redirect note → live UI at `:8080` |

### API endpoints

| Endpoint | Function |
|----------|----------|
| `GET /` | Serves the HTML dashboard |
| `GET /api/config` | Returns merged YAML config |
| `GET /api/models` | Lists `.gguf`, `.bin`, `.safetensors`, etc. in models dir |
| `GET /api/pick-file` | Opens native **file** picker → returns absolute path |
| `GET /api/pick-folder` | Opens native **folder** picker → lists models inside |
| `POST /api/scan` | Runs full pipeline via `Gateway.receive()` |
| `GET /api/audit` | Reads JSON audit logs from `./data/audit/` |

---

## Orchestration (wiring, no crypto/PII logic)

| File | What it does |
|------|----------------|
| [`src/lakanvault/orchestration/gateway.py`](../src/lakanvault/orchestration/gateway.py) | **Main entry point** — builds stages from config, runs pipeline, returns `ScanResponse`. No Streamlit imports. |
| [`src/lakanvault/orchestration/pipeline.py`](../src/lakanvault/orchestration/pipeline.py) | Runs stages in order; **fail-closed** on FAIL/ERROR; passes `prompt_text` through |
| [`src/lakanvault/orchestration/bus.py`](../src/lakanvault/orchestration/bus.py) | Only cloud egress point — redacts via `policies.redact_for_cloud()` when `cloud.enabled` is true |

### `Gateway.receive(request)` flow

1. Accept `ScanRequest` (model path + optional prompt)
2. `Pipeline.run()` → four stages
3. `EventBus.publish()` → cloud forward only if enabled
4. Return `ScanResponse` (status, hash summary, PII count, stage list)

---

## Local core (sensitive plane)

| File | Stage | What it does |
|------|-------|----------------|
| [`src/lakanvault/local_core/integrity/stage.py`](../src/lakanvault/local_core/integrity/stage.py) | Integrity | SHA-256 hash of model file in 1 MB chunks; optional baseline compare |
| [`src/lakanvault/local_core/threat_scanner/stage.py`](../src/lakanvault/local_core/threat_scanner/stage.py) | Threat | Scans host env for leaked API keys, bad folder permissions — **not** prompt text |
| [`src/lakanvault/local_core/privacy/stage.py`](../src/lakanvault/local_core/privacy/stage.py) | Privacy | PII detection on `prompt_text` (Presidio patterns + regex fallback) |
| [`src/lakanvault/local_core/audit/stage.py`](../src/lakanvault/local_core/audit/stage.py) | Audit | Writes JSON audit record to `./data/audit/` — no raw prompts stored |

---

## Contracts (boundary — schemas + policies only)

| File | What it does |
|------|----------------|
| [`src/lakanvault/contracts/events.py`](../src/lakanvault/contracts/events.py) | `PipelineEvent`, `StageResult`, `StageStatus` — what happened in a run |
| [`src/lakanvault/contracts/dtos.py`](../src/lakanvault/contracts/dtos.py) | `ScanRequest`, `ScanResponse`, `CloudTelemetryDTO` (cloud-safe fields only) |
| [`src/lakanvault/contracts/ports.py`](../src/lakanvault/contracts/ports.py) | `PipelineStage` ABC — every stage implements `run(event)` |
| [`src/lakanvault/contracts/policies.py`](../src/lakanvault/contracts/policies.py) | `redact_for_cloud()` — strips sensitive fields before any cloud forward |

---

## Infrastructure & shared

| File | What it does |
|------|----------------|
| [`src/lakanvault/shared/config.py`](../src/lakanvault/shared/config.py) | Loads `default.yaml` + `local.yaml` merge |
| [`src/lakanvault/infrastructure/config_loader.py`](../src/lakanvault/infrastructure/config_loader.py) | Typed Pydantic config (used by tests) |
| [`src/lakanvault/shared/constants.py`](../src/lakanvault/shared/constants.py) | `CHUNK_SIZE_BYTES`, forbidden cloud DTO field names |

---

## Scripts

| Script | What it does |
|--------|----------------|
| [`scripts/run_ui.ps1`](../scripts/run_ui.ps1) | Starts FastAPI + HTML UI on port 8080 |
| [`scripts/download_test_model.ps1`](../scripts/download_test_model.ps1) | Downloads SmolLM2-360M GGUF (~220 MB) to `./data/models/` |
| [`scripts/verify_boundaries.py`](../scripts/verify_boundaries.py) | Fails if `local_core` imports `cloud_intelligence` (etc.) |

---

## Tests

| Path | What it covers |
|------|----------------|
| `tests/contracts/` | Cloud DTO allowlist, gateway PII detection, air-gap bus |
| `tests/unit/test_pipeline.py` | Integrity hash, threat scan, privacy prompt flow, audit write |

```powershell
python scripts/verify_boundaries.py
python -m pytest tests/ -q
```

---

## Data directories (runtime, gitignored)

| Path | Contents |
|------|----------|
| `./data/models/` | Local GGUF / safetensors models |
| `./data/audit/` | JSON audit logs per pipeline run |
| `./data/manifest.db` | Future integrity baseline store (Phase 2) |

---

## Architecture docs

| File | Topic |
|------|-------|
| [`docs/architecture/001-hybrid-boundary.md`](architecture/001-hybrid-boundary.md) | Import firewall local ↔ cloud |
| [`docs/architecture/002-pipeline-order.md`](architecture/002-pipeline-order.md) | Stage order + fail-closed |
| [`docs/architecture/003-cryptographic-provenance.md`](architecture/003-cryptographic-provenance.md) | Signed artifacts / baselines |
| [`docs/architecture/004-ui-state-isolation.md`](architecture/004-ui-state-isolation.md) | Gateway stays free of Streamlit |
| [`docs/architecture/data-classification.md`](architecture/data-classification.md) | What may cross cloud boundary |

---

## Pipeline order (always)

```
integrity → threat_scanner → privacy → audit
```

Any stage **FAIL** or **ERROR** stops the rest immediately.
