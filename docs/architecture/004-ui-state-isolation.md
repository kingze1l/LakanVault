# 004 — UI vs gateway (my rules)

Phase 1a — UI is display only; gateway must survive without any UI shell (Phase 2 `.exe`).

**Current state:** FastAPI daemon exposes `/api/*` and `/v1/*` only. Dashboard UI is being rebuilt; `GET /` returns API status JSON.

## Why

Heavy work (hashing, scanning, DLP) must not depend on a web UI rerun loop. Gateway logic stays in plain Python so it can run in a background process or bundled `.exe`.

## `orchestration/gateway.py` — plain Python only

- In: `str`, `Path`, dict, contract types — **no** UI framework imports
- Out: DTOs / status enums — **no** UI widgets
- Zero UI imports in this file

## `app/` — thin HTTP shell

- Routes call `Gateway.receive(...)` and related gateway methods
- No raw prompt logging, model byte reads, or `cloud_intelligence` imports in the shell

## Heavy work (Phase 2)

Hashing / scanning runs outside the UI request loop — subprocess, thread, or bundled runtime. Future UI polls gateway for status.

## UI habits I'm avoiding

- Don't stash prompts/paths in UI state longer than needed
- Don't log sensitive stuff when debugging
- Flow is always: **UI → gateway → pipeline**

## Payoff

Gateway stays portable. Any future UI (tray + web dashboard) is just a skin over the same API.
