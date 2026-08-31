# Repository structure

How the LakanVault repo is organized. **Active branch:** `CS301`.

## Root layout

```
LakanVault/
├── config/              # YAML settings (default + local overrides)
├── demo_assets/         # Small demo models for integrity scan (shipped in zip)
├── docs/                # All documentation — start at docs/README.md
├── scripts/             # Runnable scripts — see scripts/README.md
├── src/lakanvault/      # Python package (all product code)
├── tests/               # pytest suite
├── RUN_DEMO.bat         # One-click demo entry (markers)
├── pyproject.toml       # Package definition + dependencies
└── README.md            # Project overview
```

**Not in git:** `data/` (runtime), `runtime/` (llama-server + GGUF), `dist/`, `.venv/`, `docs/internal/`

---

## `src/lakanvault/` — package layers

Imports flow **down** the stack. `scripts/verify_boundaries.py` enforces this.

```
┌─────────────────────────────────────────────────────────────┐
│  app/          HTTP shell — FastAPI routes, static HTML   │
│  mcp/          MCP tools + stdio sanitizing shim          │
│  launcher/     Demo bootstrap (uvicorn, browser)          │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│  orchestration/   gateway.py, proxy_gateway.py, pipeline      │
└──────────────────────────┬────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
┌───────────────┐  ┌───────────────┐  ┌──────────────────┐
│  local_core/  │  │infrastructure/│  │ cloud_intelligence│
│  DLP, PII,    │  │ token vault,  │  │ (off by default)  │
│  integrity,   │  │ upstream httpx│  │                   │
│  audit        │  │               │  │                   │
└───────────────┘  └───────────────┘  └──────────────────┘
        ▲                  ▲
        └──────── contracts/  (DTOs, ports — no logic)
                  shared/     (config, paths, url policy)
                  eval/       (RQ metrics helpers)
```

### `app/` — HTTP API + dashboard UI

| File | Role |
|------|------|
| `server.py` | FastAPI app, lifespan (vault + proxy), `/api/*` routes |
| `proxy_routes.py` | `/v1/chat/completions`, `/v1/models`, `/internal/v1/sanitize` |
| `static/index.html` | Primary HTML dashboard |
| `picker.py` | Windows file/folder dialogs |
| `dashboard.py` | Optional Streamlit UI (legacy; not used by RUN_DEMO) |

### `orchestration/` — wiring only

| File | Role |
|------|------|
| `gateway.py` | CS205 entry: scan, chat, classify, settings |
| `proxy_gateway.py` | Option 3: sanitize → upstream → restore |
| `pipeline.py` | integrity → threat → privacy → audit |
| `bus.py` | Cloud egress (redacted metadata only) |

### `local_core/` — security logic

| Path | Role |
|------|------|
| `dlp/` | Unified transformer, OpenAI payload walk, image inspector |
| `privacy/` | PII detection, classifier, anonymizers |
| `secrets/` | API key / high-entropy secret detection |
| `policy/` | Tier → action matrix |
| `security/` | Prompt injection guard |
| `integrity/` | Model hash registry + stage |
| `threat_scanner/` | Host/env checks |
| `audit/` | JSON audit records |
| `adapters/` | Local LLM HTTP clients (localhost only) |
| `runtime/` | Bundled llama.cpp sidecar |

### `infrastructure/` — IO and external systems

| Path | Role |
|------|------|
| `token_vault.py` | In-memory SQLite token map (`:memory:`) |
| `upstream/openai.py` | Allowlisted OpenAI httpx client |
| `upstream/sse.py` | SSE parse + sliding-tail token restore |
| `config_loader.py` | Typed config loader (contracts) |

### `mcp/` — Model Context Protocol

| File | Role |
|------|------|
| `server.py` | `lakanvault_classify`, `lakanvault_audit_recent` tools |
| `stdio_proxy.py` | Console shim — wraps child MCP, sanitizes via daemon HTTP |

### `contracts/` — shared types

| File | Role |
|------|------|
| `dtos.py` | Scan/chat request/response shapes |
| `mcp.py` | Classify/audit DTOs, `DataTier`, `PolicyAction` |
| `proxy.py` | Proxy/vault/sanitize DTOs (Option 3) |
| `events.py`, `ports.py`, `policies.py` | Pipeline contracts |

### `shared/` — cross-cutting utilities

| File | Role |
|------|------|
| `config.py` | Load `default.yaml` + `local.yaml` |
| `paths.py` | Dev vs PyInstaller frozen paths |
| `url_policy.py` | Localhost-only + upstream allowlist |

---

## `tests/`

```
tests/
├── contracts/     # DTO safety, boundaries, config
└── unit/          # Per-module behavior (DLP, proxy, vault, MCP, SSE, …)
```

Run: `python -m pytest tests/ -q`

---

## `config/`

| File | Purpose |
|------|---------|
| `default.yaml` | Baseline — cloud off, pipeline order, **proxy** block |
| `local.yaml` | Machine overrides (gitignored if personal) |
| `cloud.example.yaml` | Hybrid template |

---

## `scripts/`

See [`scripts/README.md`](../scripts/README.md).

---

## HTTP surface (daemon `:8080`)

| Path | Layer |
|------|--------|
| `/`, `/static/*` | Dashboard UI |
| `/api/*` | CS205 demo API (scan, chat, integrity, audit) |
| `/v1/chat/completions`, `/v1/models` | Option 3 OpenAI proxy |
| `/internal/v1/sanitize` | MCP shim → daemon DLP |
