# LakanVault

A local safety layer for AI coding tools. It runs on your own machine and checks text **before** it reaches a cloud model:

- **API keys and credentials** (`sk-…`, `AKIA…`, `ghp_…`, `xox…`, `Bearer …`) → **blocked**
- **Personal information** (names, emails, phone numbers) → replaced with **reversible opaque tokens** `[LV_…]`, then restored in the model's reply
- **Prompt injection** patterns → **blocked**

Nothing is sent anywhere except the upstream you explicitly configure. Cloud telemetry is off by default. The token map lives only in memory.

**Status:** working slice, not full coverage. [`WHAT_CHANGED.md`](WHAT_CHANGED.md) has the short version. [`docs/v2/PHASE2_PLAN.md`](docs/v2/PHASE2_PLAN.md) has the sprint checklist.

---

## 1. Quick start

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m uvicorn lakanvault.app.server:app --host 127.0.0.1 --port 8080
```

The daemon listens on **http://127.0.0.1:8080** (loopback only). `GET /` returns `{"status": "api-only"}`.

Windows tray mode instead of uvicorn:

```powershell
python -m lakanvault.launcher --tray --no-runtime
```

Optional stronger PII detection (spaCy NER):

```powershell
pip install -e ".[ner]"
python -m spacy download en_core_web_sm
```

### 60-second check

In a second PowerShell window, send a fake key through the proxy. It must return **403** and never call OpenAI:

```powershell
try {
  Invoke-WebRequest http://127.0.0.1:8080/v1/chat/completions -Method POST `
    -ContentType "application/json" `
    -Body '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"key sk-abcdefghijklmnopqrstuvwxyz1234567890"}]}'
} catch { $_.Exception.Response.StatusCode.value__ }
```

Or open the paste-check page in a browser: **http://127.0.0.1:8080/static/shim.html**. Paste any text, press *Check*. The page shows tier / action / entity types only; the raw text is never echoed back.

---

## 2. How the protection works

```
your text
   │
   ▼
classify_content()          local_core/privacy/classifier.py
   ├─ prompt injection?  → tier secret        → BLOCK
   ├─ API key pattern?   → tier confidential  → BLOCK
   ├─ PII span?          → tier internal      → REDACT  → [LV_…] tokens (in-memory vault, TTL)
   └─ nothing            → tier public        → ALLOW
   │
   ▼
upstream model (only on ALLOW / REDACT)
   │
   ▼
response: [LV_…] tokens restored to the original values, including mid-stream (SSE)
```

| Tier | Default action | Example |
|------|----------------|---------|
| Secret | Block | prompt-injection phrase |
| Confidential | Block | `sk-…`, AWS/GitHub/Slack keys, `Bearer …` |
| Internal | Redact (tokenize + restore) | names, emails, phones |
| Public | Allow | normal code and prose |

The reversible anonymizer: `local_core/privacy/opaque_anonymizer.py` mints tokens; `infrastructure/token_vault.py` stores them in an in-memory SQLite map (`:memory:`) with TTL; `proxy_gateway.py` restores them on the way back, per request. Mappings never touch disk.

Fail-closed: if a detector throws, the request is blocked, not passed through.

---

## 3. Blocking API keys in each IDE (what works today)

LakanVault has **no editor extension and no silent HTTPS interception**. An IDE is protected only if its traffic goes through one of two doors:

1. **The OpenAI-compatible proxy** – the client must point its base URL at `http://127.0.0.1:8080/v1`.
2. **MCP tools** – the client must call `lakanvault_classify` (or run a child MCP server through our sanitizing shim).

| IDE / client | Door | What is covered | Status |
|--------------|------|-----------------|--------|
| **Cursor** | MCP tools (`lakanvault_classify`, `lakanvault_audit_recent`) | Text the agent sends to the tool. Key → `action: block`, key never echoed | Verified with SDK + subprocess tests; works in a sandbox Cursor window |
| **Cursor** | MCP sanitizing shim (`lakanvault-mcp`) around a third-party MCP server | Tool **results** coming back from that server (e.g. file contents) | Unit-tested; not yet captured inside Cursor UI |
| **Cursor** Chat / Agent / Tab typed prompts | — | **Not covered.** Cursor routes these through its own backend | Unclaimed |
| **VS Code + Continue.dev** | Proxy: `apiBase: http://127.0.0.1:8080/v1` | Every chat request Continue sends to that model | Proxy tested; Continue end-to-end capture still to record |
| **VS Code + GitHub Copilot** | — | **Not possible** – Copilot does not expose a base URL | Out of reach |
| **Claude Desktop / Claude Code** | MCP tools (same stdio server) | Same as Cursor MCP row | Standard stdio MCP; not yet verified by us |
| **Claude Code** | Proxy via `ANTHROPIC_BASE_URL` | Would need an Anthropic Messages codec | Not built (Sprint 2) |
| **Any OpenAI-compatible client** (curl, scripts, LM Studio chat UIs) | Proxy | Full request body, images blocked in strict mode | Tested |

### 3.1 Cursor – safe sandbox (recommended)

Do **not** add LakanVault to `%USERPROFILE%\.cursor\mcp.json`; that affects every Cursor window. Use a second worktree with a **project-only** config:

```powershell
.\scripts\setup_mcp_sandbox.ps1
```

Then open `..\LakanVault-mcp-sandbox` in a **new** Cursor window, go to **Settings → MCP**, turn on `lakanvault`, confirm the two tools appear, and ask the agent:

> Use lakanvault_classify on this: sk-abcdefghijklmnopqrstuvwxyz1234567890

Expected: `action: block`, `tier: confidential`, no key in the result. Full steps: [`docs/cs301/CURSOR_SETUP.md`](docs/cs301/CURSOR_SETUP.md). Template: [`docs/cs301/examples/cursor-mcp.json`](docs/cs301/examples/cursor-mcp.json).

### 3.2 VS Code – Continue.dev through the proxy

Start the daemon (section 1), then in Continue's `config.yaml`:

```yaml
models:
  - name: lakanvault-openai
    provider: openai
    model: gpt-4o-mini
    apiBase: http://127.0.0.1:8080/v1
    apiKey: ${{ secrets.OPENAI_API_KEY }}
    useResponsesApi: false
    roles: [chat]
```

A prompt containing `sk-…` gets a 403 from LakanVault and Continue shows the block error. A prompt containing an email goes upstream as `[LV_…]` and comes back restored. Autocomplete, embeddings and `/v1/responses` are not proxied. Matrix: [`docs/v2/CLIENT_COMPAT.md`](docs/v2/CLIENT_COMPAT.md).

To route to a **local** model instead of OpenAI (LM Studio / Ollama), the proxy's upstream allowlist already includes `localhost:1234`, `11434`, `8081`; set `proxy.openai_base_url` in `config/local.yaml`.

### 3.3 Claude Desktop / Claude Code (MCP, untested)

The same stdio server works with any MCP host. Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "lakanvault": {
      "command": "C:\\path\\to\\LakanVault\\.venv\\Scripts\\python.exe",
      "args": ["-m", "lakanvault.mcp.stdio_server", "--config-dir", "C:\\path\\to\\LakanVault\\config"],
      "env": { "PYTHONUTF8": "1", "PYTHONPATH": "C:\\path\\to\\LakanVault\\src" }
    }
  }
}
```

Claude Code: `claude mcp add lakanvault -- <same command and args>`. We have not run this ourselves yet; treat it as "should work", not "verified".

### 3.4 Honest limits

- Text typed straight into Cursor Chat/Agent/Tab or Copilot never reaches LakanVault.
- MCP only sees what the agent chooses to send to the tool; the agent can skip the tool.
- No clipboard hook, no editor extension, no browser extension yet.
- Claims in this repo use "verified via test/capture" language on purpose. If a row above says *not verified*, it is not.

---

## 4. HTTP surface (`127.0.0.1:8080`)

| Path | Purpose |
|------|---------|
| `GET /` | Status JSON |
| `GET /static/shim.html` | Paste-check page (metadata only) |
| `POST /v1/chat/completions`, `GET /v1/models` | OpenAI-compatible proxy with DLP |
| `POST /internal/v1/classify-chat-payload` | Loopback-only. Classify an OpenAI-shaped payload; returns tier/action/counts, never the text |
| `POST /internal/v1/sanitize` | Loopback-only. Used by the MCP shim to tokenize tool results |
| `/api/*` | Scan, chat, settings, integrity, audit (CS205 pipeline) |

MCP tools: `lakanvault_classify(text)`, `lakanvault_audit_recent(limit)` via `python -m lakanvault.mcp.stdio_server` (or the `lakanvault-mcp-server` script). Transport is stdio, newline-delimited JSON-RPC.

---

## 5. Repository map

```
LakanVault/
├── config/              YAML settings (see §7)
├── docs/                Architecture decisions, IDE setup, sprint plan
├── scripts/             Dev/quality/packaging scripts (see §6)
├── src/lakanvault/      Python package
├── tests/               pytest suite (contracts/ + unit/)
├── WHAT_CHANGED.md      Short "what works now" note
└── pyproject.toml
```

### `src/lakanvault/` layers

Imports flow downward only. `scripts/verify_boundaries.py` fails if `app/` or `mcp/` import `local_core/` or `infrastructure/` directly (ADR-001).

| Folder | What it is | Key files |
|--------|------------|-----------|
| `app/` | FastAPI HTTP shell. Routes only, no security logic | `server.py` (`/api/*`, lifespan), `proxy_routes.py` (`/v1/*`, `/internal/*`), `static/shim.html` |
| `mcp/` | MCP entry points | `stdio_server.py` (native tools, official SDK), `stdio_proxy.py` (sanitizing shim), `server.py` (tool handlers) |
| `launcher/` | Daemon bootstrap, PyInstaller paths, config seeding | `bootstrap.py` |
| `tray/` | Windows tray icon (`pystray`) | `app.py`, `state.py`, `icons.py` |
| `orchestration/` | Wiring between HTTP/MCP and core | `gateway.py` (scan/chat/classify), `proxy_gateway.py` (sanitize → upstream → restore), `pipeline.py`, `bus.py` |
| `local_core/` | All detection and policy logic (pure Python, no HTTP) | `privacy/` (PII detectors, classifier, anonymizers), `secrets/` (key regex + entropy), `policy/` (tier→action), `security/` (prompt guard), `dlp/` (payload walk, transformer, image inspector), `integrity/`, `threat_scanner/`, `audit/` |
| `infrastructure/` | IO adapters | `token_vault.py` (in-memory SQLite), `upstream/openai.py`, `upstream/sse.py`, `config_loader.py` |
| `contracts/` | Pydantic DTOs and ports shared across layers, zero logic | `mcp.py` (tiers/actions), `proxy.py`, `dtos.py`, `ports.py`, `policies.py`, `events.py` |
| `shared/` | Cross-cutting helpers | `config.py`, `paths.py`, `url_policy.py`, `loopback.py` |
| `eval/` | RQ1/RQ2 metric helpers (precision/recall, latency) | `metrics.py` |

Detailed per-file table: [`docs/REPO_STRUCTURE.md`](docs/REPO_STRUCTURE.md).

---

## 6. Scripts

Run from repo root after `pip install -e ".[dev]"`.

| Script | Purpose |
|--------|---------|
| `python scripts/verify_boundaries.py` | Import-boundary gate (ADR-001). Must pass before commit |
| `python scripts/smoke_test.py` | Hits live endpoints + proxy block (daemon must be running) |
| `.\scripts\setup_mcp_sandbox.ps1` | Creates `..\LakanVault-mcp-sandbox` worktree + venv + project-only `.cursor/mcp.json` |
| `.\scripts\build_tray_exe.ps1` | PyInstaller onedir: `dist/LakanVault/LakanVault.exe` + `dist/lakanvault-mcp/lakanvault-mcp.exe` |
| `.\scripts\smoke_frozen_exe.ps1` | Starts the frozen exe and checks it answers |

All five are used; none are leftovers.

---

## 7. Tests

```powershell
python scripts/verify_boundaries.py
python -m pytest tests/ -q
```

| Folder | Covers |
|--------|--------|
| `tests/contracts/` | DTOs carry no raw PII to cloud, config contracts, policy/bus rules |
| `tests/unit/` | Detectors, classifier, transformer, token vault, proxy (block / tokenize / SSE restore), MCP server (in-memory + real subprocess), shim NDJSON, launcher paths, tray state, shim page |

Key files for the IDE story: `test_openai_proxy.py`, `test_classify_chat_payload.py`, `test_mcp_stdio_server.py`, `test_mcp_stdio_server_subprocess.py`, `test_mcp_stdio_proxy.py`, `test_token_vault.py`, `test_opaque_anonymizer.py`.

Rules: TDD (failing test first), one slice per commit, run both commands above before every commit.

---

## 8. Config

| File | Purpose |
|------|---------|
| `config/default.yaml` | Baseline: cloud **off**, pipeline order, `privacy.engine`, `local_ai` presets, `proxy` block (strict mode, allowlist, vault TTL) |
| `config/local.yaml` | Your machine's overrides (e.g. LM Studio URL). Optional |
| `config/cloud.example.yaml` | Template for the optional cloud-metadata path. Disabled |

These are **LakanVault's** settings, read by `shared/config.py` (detector engine, audit/model paths, local AI URL, proxy policy). They are not a Continue/Cursor config and should not be replaced by one; IDE configs live in the IDE (section 3).

---

## 9. Docs

- [`docs/README.md`](docs/README.md) – index
- [`docs/REPO_STRUCTURE.md`](docs/REPO_STRUCTURE.md) – per-file layout
- [`docs/cs301/CURSOR_SETUP.md`](docs/cs301/CURSOR_SETUP.md) – Cursor MCP sandbox
- [`docs/v2/CLIENT_COMPAT.md`](docs/v2/CLIENT_COMPAT.md) – client matrix
- [`docs/architecture/005-option3-hybrid-gateway.md`](docs/architecture/005-option3-hybrid-gateway.md) – proxy + vault + shim decision
- [`docs/v2/PHASE2_PLAN.md`](docs/v2/PHASE2_PLAN.md) – sprint tickets

## Team

| Role | Name |
|------|------|
| Cybersecurity lead / Product Owner | Samiullah |
| Detection / anonymizer / peer review | Joan Allysen |
| Scrum Master | Rouwa Yalda |
