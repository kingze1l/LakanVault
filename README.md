# LakanVault

Local-first AI DLP gateway: block secrets and PII before they reach ChatGPT, Copilot, Cursor, or Claude.

**What changed:** [`WHAT_CHANGED.md`](WHAT_CHANGED.md)  
**Product plan:** [`docs/v2/PHASE2_PLAN.md`](docs/v2/PHASE2_PLAN.md)

## Quick start (developers)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m uvicorn lakanvault.app.server:app --reload --host 127.0.0.1 --port 8080
```

API daemon: **http://127.0.0.1:8080**  
Prompt Review UI: **http://127.0.0.1:8080/review** (loopback Joan scan → mask/block → optional local send).

Tray mode (Windows):

```powershell
python -m lakanvault.launcher --tray --no-runtime
```

Left-click / **Open Dashboard** opens the API URL; **Quit** exits.

### Cursor project hooks (this workspace)

**Where they apply:** only while this repo (`LakanVault`) is the open Cursor workspace. Other folders / other chats elsewhere are unaffected. Cloud agents do not run these hooks.

**On / off (so this chat is not blocked while you build):**

1. Open [`.cursor/hooks/mode.txt`](.cursor/hooks/mode.txt)
2. First word must be exactly `off` or `on`
3. Save — next send uses the new mode (no restart needed for the script; restart Cursor only if hooks failed to load)

| `mode.txt` | Behavior |
|------------|----------|
| `off` | Pass-through — normal Cursor chat |
| `tag` (current) | Gate **only** if the prompt contains `[[lv]]` — this chat stays normal; test chat prefixes with `[[lv]]` |
| `on` | Gate every prompt: secrets **blocked**; PII **blocked** + sanitized text to paste/resend |
Optional override: env `LAKANVAULT_HOOKS=on` or `off`.

With the daemon on `:8080` and mode `on` (or `tag` + `[[lv]]`), [`.cursor/hooks.json`](.cursor/hooks.json) calls `/api/review`:

- `beforeSubmitPrompt` — Cursor **cannot rewrite** the prompt; we stop unsafe sends (`continue: false`).
- **MASK (FR1/FR8):** deny + show sanitized text; that exact paste is **trusted once** (TTL ~10 min) so fake names are not remasked forever.
- **BLOCK:** deny with no handoff (secrets never leave).
- `beforeReadFile` — deny `.env`, `vault.key`, `*.pem` when mode is `on`.

Honest claim: gate + one-shot paste handoff, not silent in-place rewrite. Not Copilot, not browser ChatGPT, not Tab. FR9 UI: `/review`.
## Scripts

| Script | Purpose |
|--------|---------|
| `python -m uvicorn lakanvault.app.server:app --reload` | Dev daemon on `:8080` (after `pip install -e .`) |
| `scripts/build_tray_exe.ps1` | PyInstaller onedir: `LakanVault.exe` + `lakanvault-mcp.exe` |
| `scripts/smoke_test.py` | Live endpoint + proxy block checks |
| `scripts/verify_boundaries.py` | Architecture import checks |

See [`scripts/README.md`](scripts/README.md) for the full index.

Optional stronger PII detection (Joan Presidio + spaCy NER). The detector expects `en_core_web_lg`:

```powershell
pip install -e ".[ner]"
python -m spacy download en_core_web_lg
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
| MCP | `mcp/` | Classify / protect / restore / audit tools + stdio sanitizing shim |
| Shared | `shared/` | Config, paths, URL policy |

Cloud is **off by default**. Nothing leaves the machine unless `config/local.yaml` sets `cloud.enabled: true`.

**Option 3 (CS301):** OpenAI-compatible proxy on `:8080/v1`, in-memory token map, MCP shim. See [`docs/architecture/005-option3-hybrid-gateway.md`](docs/architecture/005-option3-hybrid-gateway.md).

## Local AI (optional chat)

Sanitized chat via `/api/chat` needs a local LLM service (LM Studio, Ollama, or bundled runtime). The DLP gateway, proxy, and MCP classify/protect path work without a cloud model. For Cursor: call `lakanvault_protect` before the external LLM, then `lakanvault_restore` on the reply (see [`docs/cs301/CURSOR_SETUP.md`](docs/cs301/CURSOR_SETUP.md)).

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
