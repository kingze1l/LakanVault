# Repository structure

How the LakanVault repo is organized. **Active branch:** `CS301`.

## Plain English map (for Joan / new readers)

Folder names stay technical (ADR-001). Here is what they mean in normal words:

| Folder | Plain meaning |
|--------|----------------|
| `app/` | HTTP doors the browser/Cursor hit |
| `tray/` | Windows tray icon + Status flyout |
| `mcp/` | Tools Cursor can call |
| `launcher/` | Starts the daemon / exe |
| `orchestration/` | Glue — calls the security pieces in order |
| `local_core/` | The security brain (PII, secrets, policy, audit) |
| `infrastructure/` | Vault DB + outbound HTTP helpers |
| `contracts/` | Shared request/response shapes (no logic) |
| `shared/` | Paths, config load, URL allowlist |
| `eval/` | Small research metric helpers only |

Those `__init__.py` files are **not** empty junk folders — Python needs them so `import lakanvault.…` works. Open one: short casual notes at the top (Joan's detection/Vault packages left as she wrote them).

## Root layout

```
LakanVault/
├── config/              # YAML settings (default + local overrides)
├── docs/                # All documentation — start at docs/README.md
├── scripts/             # Runnable scripts — see scripts/README.md
├── src/lakanvault/      # Python package (all product code)
├── tests/               # pytest suite
├── pyproject.toml       # Package definition + dependencies
└── README.md            # Project overview
```

**Not in git:** `data/` (runtime), `runtime/` (optional llama sidecar), `dist/`, `.venv/`, `docs/internal/`

---

## `src/lakanvault/` — package layers

Imports flow **down** the stack. `scripts/verify_boundaries.py` enforces this.

```
┌─────────────────────────────────────────────────────────────┐
│  app/          HTTP shell — FastAPI routes only (UI TBD)   │
│  mcp/          MCP tools + stdio sanitizing shim          │
│  launcher/     Daemon bootstrap (uvicorn, optional browser)│
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│  orchestration/   gateway.py, proxy_gateway.py, pipeline      │
└──────────────────────────┬────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  │
┌───────────────┐  ┌───────────────┐         │
│  local_core/  │  │infrastructure/│         │
│  DLP, PII,    │  │ token vault,  │         │
│  integrity,   │  │ upstream httpx│         │
│  audit        │  │               │         │
└───────────────┘  └───────────────┘         │
        ▲                  ▲
        └──────── contracts/  (DTOs, ports — no logic)
                  shared/     (config, paths, url policy)
                  eval/       (RQ metrics helpers)
```

### `app/` — HTTP API (dashboard UI TBD)

| File | Role |
|------|------|
| `server.py` | FastAPI app, lifespan (vault + proxy), `/api/*` routes |
| `proxy_routes.py` | `/v1/chat/completions`, `/v1/models`, `/internal/v1/sanitize` |
| `static/` | Reserved assets (logo/favicon) for future UI |
| `picker.py` | Windows file/folder dialogs |

### `orchestration/` — wiring only

| File | Role |
|------|------|
| `gateway.py` | Scan, chat, classify, settings |
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
| `runtime/` | Optional bundled llama.cpp sidecar |

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

See [`scripts/README.md`](../scripts/README.md). Notable entries:

| Script | Purpose |
|--------|---------|
| `INSTALL_RECOMMENDED.bat` | Optional spaCy NER (`.[ner]` + `en_core_web_lg`) for source/dev installs |
| `package_mvp.ps1` | Build lean `LakanVault-MVP.zip` (regex PII; no spaCy in the zip) |
| `verify_boundaries.py` | ADR-001 import boundary checker |

Product DLP lives under `local_core/` (scan, pii, secrets, policy, anonymizer). RQ metric helpers stay in `eval/`; the old Joan `local_core/evaluation/` RQ scripts and committed CSV/report were removed from the tree.

---

## HTTP surface (daemon `:8080`)

| Path | Layer |
|------|--------|
| `/` | API status JSON (UI pending) |
| `/static/*` | Reserved static assets |
| `/api/*` | Gateway API (scan, chat, integrity, audit) |
| `/v1/chat/completions`, `/v1/models` | Option 3 OpenAI proxy |
| `/internal/v1/sanitize` | MCP shim → daemon DLP |
