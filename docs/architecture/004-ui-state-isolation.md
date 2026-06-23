# 004 — UI vs gateway (my rules)

Phase 1a — The HTML UI (`app/static/index.html`) is display only; gateway must survive without it (Phase 2 `.exe`).

> **Note:** An earlier Streamlit shell was removed. The same boundary rules apply to the FastAPI + HTML UI.

## Why

UI reruns and blocking calls would freeze the dashboard if heavy work ran inline. Gateway logic stays in plain Python so it can run in a background process or bundled runtime later.

## `orchestration/gateway.py` — plain Python only

- In: `str`, `Path`, dict, contract types — **no** UI framework imports
- Out: DTOs / status enums — **no** UI widgets
- Zero UI imports in this file

## `app/` — thin HTML + FastAPI shell

- UI calls `Gateway.receive(...)`
- UI renders results
- I don't log raw prompts, read model bytes here, or import `cloud_intelligence`

## Heavy work (Phase 2)

Hashing / scanning runs outside the UI request loop — subprocess, thread, or bundled runtime. UI polls gateway for status.

## UI habits I'm avoiding

- Don't stash prompts/paths in browser state longer than needed
- Don't log sensitive stuff to the browser console when debugging
- Flow is always: **UI → gateway → pipeline**

## Payoff

Gateway stays portable. The HTML UI is just the dashboard skin.
