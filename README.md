# LakanVault

Local-first AI DLP gateway: block secrets and PII before they reach ChatGPT, Copilot, Cursor, or Claude.

**Active branch:** `CS301` (Option 3 hybrid gateway + tray packaging)  
**Product plan:** [`docs/v2/PHASE2_PLAN.md`](docs/v2/PHASE2_PLAN.md)

## Quick start (developers)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m uvicorn lakanvault.app.server:app --reload --host 127.0.0.1 --port 8080
```

API daemon: **http://127.0.0.1:8080** (dashboard UI is being rebuilt — use `/api/*` and `/v1/*` for now).

## Scripts

| Script | Purpose |
|--------|---------|
| `python -m uvicorn lakanvault.app.server:app --reload` | Dev daemon on `:8080` (after `pip install -e .`) |
| `scripts/build_tray_exe.ps1` | PyInstaller onedir: `LakanVault.exe` + `lakanvault-mcp.exe` |
| `scripts/smoke_test.py` | Live endpoint + proxy block checks |
| `scripts/verify_boundaries.py` | Architecture import checks |

See [`scripts/README.md`](scripts/README.md) for the full index.

Optional stronger PII detection (spaCy NER):

```powershell
pip install -e ".[ner]"
python -m spacy download en_core_web_sm
```

## Architecture

Layered design — see [`docs/REPO_STRUCTURE.md`](docs/REPO_STRUCTURE.md).

| Layer | Path | Role |
|-------|------|------|
| Contracts | `contracts/` | DTOs, ports, policies (no business logic) |
| App | `app/` | FastAPI routes: `/api/*` and `/v1/*` |
| Orchestration | `orchestration/` | `gateway.py`, `proxy_gateway.py`, pipeline |
| Core | `local_core/` | DLP, PII, secrets, integrity, audit |
| Infrastructure | `infrastructure/` | In-memory token vault, OpenAI upstream, SSE |
| MCP | `mcp/` | Classify/audit tools + stdio sanitizing shim |
| Shared | `shared/` | Config, paths, URL policy |

Cloud is **off by default**. Nothing leaves the machine unless `config/local.yaml` sets `cloud.enabled: true`.

**Option 3 (CS301):** OpenAI-compatible proxy on `:8080/v1`, in-memory token map, MCP shim. See [`docs/architecture/005-option3-hybrid-gateway.md`](docs/architecture/005-option3-hybrid-gateway.md).

## Local AI (optional chat)

Sanitized chat via `/api/chat` needs a local LLM service (LM Studio, Ollama, or bundled runtime). The DLP gateway, proxy, and MCP classify path work without a model.

| Provider | Default URL |
|----------|-------------|
| [LM Studio](https://lmstudio.ai) | `http://localhost:1234` |
| [Ollama](https://ollama.com) | `http://localhost:11434` |

Configure via `/api/settings` or `config/local.yaml` (`local_ai.base_url`).

## Build tray `.exe`

```powershell
.\scripts\build_tray_exe.ps1
```

Output: `dist/LakanVault/LakanVault.exe` and `dist/lakanvault-mcp/lakanvault-mcp.exe`.

## Tests

```powershell
python scripts/verify_boundaries.py
python -m pytest tests/ -q
```

## Pipeline order

`integrity → threat_scanner → privacy → audit`

Fail-closed: any FAIL or ERROR halts the pipeline immediately.

## Documentation

- **Index:** [`docs/README.md`](docs/README.md)
- **Code layout:** [`docs/REPO_STRUCTURE.md`](docs/REPO_STRUCTURE.md)
- **Sprint plan:** [`docs/v2/PHASE2_PLAN.md`](docs/v2/PHASE2_PLAN.md)
- **CS301 notes:** [`docs/cs301/README.md`](docs/cs301/README.md)
- Architecture ADRs: `docs/architecture/`

## Team

| Role | Name |
|------|------|
| Cybersecurity lead | Samiullah |
| Detection / anonymizer / peer review | Joan Allysen |
| Scrum Master | Rouwa Yalda |
| Product Owner | Samiullah |
