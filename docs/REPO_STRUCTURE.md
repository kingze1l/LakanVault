# Repository structure

Per-file layout of the code on `main` (Oct 2026). For the product story and IDE setup read the root [`README.md`](../README.md).

## Root layout

```
LakanVault/
├── config/              # YAML settings (default + local overrides)
├── docs/                # Documentation — start at docs/README.md
├── scripts/             # Dev, quality, sandbox, packaging scripts
├── src/lakanvault/      # Python package (all product code)
├── tests/               # pytest suite
├── pyproject.toml       # Package definition + console scripts
├── WHAT_CHANGED.md      # Short "what works now" note
└── README.md            # Project overview, per-IDE blocking guide
```

**Not in git:** `data/` (runtime), `runtime/` (optional llama sidecar), `dist/`, `.venv/`, `docs/internal/`, `.cursor/` (except rules), `site/`.

---

## `src/lakanvault/` — package layers

Imports flow **down** the stack. `scripts/verify_boundaries.py` enforces this (ADR-001): `app/` and `mcp/` never import `local_core/` or `infrastructure/`.

```
┌─────────────────────────────────────────────────────────────┐
│  app/        FastAPI routes + static paste page             │
│  mcp/        MCP stdio server (tools) + sanitizing shim     │
│  launcher/   Daemon bootstrap, frozen paths, config seeding │
│  tray/       Windows tray icon                              │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│  orchestration/   gateway.py, proxy_gateway.py, pipeline    │
└──────────────────────────┬──────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  │
┌───────────────┐  ┌───────────────┐         │
│  local_core/  │  │infrastructure/│         │
│  DLP, PII,    │  │ token vault,  │         │
│  secrets,     │  │ upstream httpx│         │
│  policy, audit│  │ SSE restore   │         │
└───────────────┘  └───────────────┘         │
        ▲                  ▲
        └──────── contracts/  (DTOs, ports — no logic)
                  shared/     (config, paths, url policy, loopback)
                  eval/       (RQ metrics helpers)
```

### `app/` — HTTP shell

| File | Role |
|------|------|
| `server.py` | FastAPI app, lifespan (vault + proxy gateway, config seeding), `/api/*` routes, mounts `/static` |
| `proxy_routes.py` | `/v1/chat/completions`, `/v1/models`, loopback-only `/internal/v1/classify-chat-payload` and `/internal/v1/sanitize` |
| `static/shim.html` | Paste-check page; posts to the metadata-only classifier |
| `picker.py` | Windows file/folder dialogs |

### `mcp/` — Model Context Protocol

| File | Role |
|------|------|
| `stdio_server.py` | Native MCP server (official SDK, stdio). Tools `lakanvault_classify(text)`, `lakanvault_audit_recent(limit)`. Entry `lakanvault-mcp-server` / `python -m lakanvault.mcp.stdio_server` |
| `__main__.py` | `python -m lakanvault.mcp` → `stdio_server.main` |
| `stdio_proxy.py` | Shim `lakanvault-mcp`: wraps a child MCP server, NDJSON framing, sanitizes `tools/call` results via daemon `/internal/v1/sanitize` |
| `server.py` | Tool handlers shared by the stdio server (call gateway only) |

### `launcher/` and `tray/`

| File | Role |
|------|------|
| `launcher/bootstrap.py` | Data dirs, `seed_bundled_config()` for PyInstaller `_MEIPASS`, uvicorn start, runtime sidecar |
| `launcher/__main__.py` | `python -m lakanvault.launcher [--tray] [--no-runtime] [--daemon-only]` |
| `tray/app.py`, `state.py`, `icons.py` | `pystray` icon, state machine, generated icons |

### `orchestration/` — wiring only

| File | Role |
|------|------|
| `gateway.py` | Scan, chat, classify, settings, audit (single entry for UI/MCP) |
| `proxy_gateway.py` | Proxy lifecycle: sanitize → upstream → restore; `classify_chat_payload()` metadata-only |
| `pipeline.py` | integrity → threat → privacy → audit, fail-closed |
| `bus.py` | Only cloud egress point; redacted metadata; off by default |

### `local_core/` — security logic (no HTTP, no IO adapters)

| Path | Role |
|------|------|
| `privacy/detectors.py` | PII spans (regex, optional spaCy / Presidio-style engines) |
| `privacy/classifier.py` | injection → API key → PII → allow cascade; returns tier + action, no raw text |
| `privacy/opaque_anonymizer.py` | Mints `[LV_…]` tokens via vault port; restore |
| `privacy/anonymizer.py` | Older `NAME_001` placeholder anonymizer (chat demo path) |
| `secrets/detector.py` | API key regexes + Shannon entropy helper |
| `policy/engine.py` | Tier → action matrix |
| `security/prompt_guard.py` | Prompt-injection patterns |
| `dlp/openai_payload.py` | Walk OpenAI chat payloads; extract/replace text; restore responses |
| `dlp/transformer.py` | Unified transform: classify → block / tokenize / pass |
| `dlp/image_inspector.py` | Image block/OCR scaffold (strict mode blocks) |
| `integrity/`, `threat_scanner/`, `audit/` | CS205 pipeline stages |
| `adapters/local_llm_client.py` | Localhost-only LLM client |
| `runtime/llama_runtime.py` | Optional bundled llama.cpp sidecar |

### `infrastructure/` — IO and external systems

| Path | Role |
|------|------|
| `token_vault.py` | In-memory SQLite token map (`:memory:`), TTL, size caps |
| `upstream/openai.py` | Allowlisted OpenAI-compatible httpx client |
| `upstream/sse.py` | SSE parse + sliding-tail token restore |
| `config_loader.py` | Typed config loader |

### `contracts/` — shared types, zero logic

| File | Role |
|------|------|
| `mcp.py` | `DataTier`, `PolicyAction`, classify/audit DTOs |
| `proxy.py` | Proxy/vault/sanitize DTOs, `ChatPayloadClassifyResponse`, `TokenVaultPort`, `OPAQUE_TOKEN_REGEX` |
| `dtos.py` | Scan/chat request/response shapes |
| `events.py`, `ports.py`, `policies.py` | Pipeline contracts, `redact_for_cloud()` |

### `shared/` — cross-cutting utilities

| File | Role |
|------|------|
| `config.py` | Load `default.yaml` + `local.yaml` |
| `paths.py` | Dev vs PyInstaller frozen paths |
| `url_policy.py` | Localhost-only + upstream allowlist |
| `loopback.py` | `assert_loopback_client()` for internal endpoints |
| `constants.py`, `system_prompt.py` | Shared constants / chat system prompt |

---

## `tests/`

```
tests/
├── contracts/     # DTO safety (no PII to cloud), boundaries, config, policies
└── unit/          # Per-module behavior: detectors, transformer, vault, proxy, SSE,
                   # MCP server (in-memory + subprocess), shim, launcher, tray, shim page
```

Run: `python scripts/verify_boundaries.py` then `python -m pytest tests/ -q`.

---

## `scripts/`

| Script | Purpose |
|--------|---------|
| `verify_boundaries.py` | ADR-001 import gate |
| `smoke_test.py` | Live endpoint + proxy block checks against a running daemon |
| `setup_mcp_sandbox.ps1` | Worktree `..\LakanVault-mcp-sandbox` (branch `personal/mcp-sandbox`) + venv + project `.cursor/mcp.json` |
| `build_tray_exe.ps1` | PyInstaller onedir: `LakanVault.exe` + `lakanvault-mcp.exe` |
| `smoke_frozen_exe.ps1` | Start frozen exe `--daemon-only`, check it answers, check MCP artifact exists |

---

## `config/`

| File | Purpose |
|------|---------|
| `default.yaml` | Baseline: cloud off, pipeline order, `privacy.engine`, `local_ai`, `local_runtime`, `proxy` (strict, allowlist, vault TTL) |
| `local.yaml` | Machine overrides |
| `cloud.example.yaml` | Disabled cloud-metadata template |

---

## HTTP surface (daemon `127.0.0.1:8080`)

| Path | Layer |
|------|-------|
| `GET /` | Status JSON (`api-only`) |
| `GET /static/shim.html` | Paste-check page |
| `/api/*` | Gateway API (scan, chat, settings, integrity, audit) |
| `POST /v1/chat/completions`, `GET /v1/models` | Option 3 OpenAI proxy |
| `POST /internal/v1/classify-chat-payload` | Loopback only; metadata response |
| `POST /internal/v1/sanitize` | Loopback only; MCP shim → daemon DLP |
