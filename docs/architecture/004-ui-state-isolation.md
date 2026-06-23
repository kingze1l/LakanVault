# 004 — UI vs gateway (my rules)

Phase 1a — UI is display only; gateway must survive without any UI shell (Phase 2 `.exe`).

**Shipped demo UI:** FastAPI + HTML (`app/static/index.html`, `RUN_DEMO.bat`).  
**Proposal UI shell:** Streamlit (`app/dashboard.py`) — same Gateway, optional alternate skin per original design.

## Why

Streamlit reruns the whole script on clicks. Hashing a large model inline would freeze the dashboard. Gateway logic stays in plain Python so it can run in a background process or bundled runtime later.

## `orchestration/gateway.py` — plain Python only

- In: `str`, `Path`, dict, contract types — **no** `st.session_state`, `st.button`, etc.
- Out: DTOs / status enums — **no** Streamlit widgets
- Zero UI imports in this file

## `app/` — thin UI shell (HTML or Streamlit)

- UI calls `Gateway.receive(...)` and related gateway methods
- UI renders results only
- No raw prompt logging, model byte reads, or `cloud_intelligence` imports in the shell

## Heavy work (Phase 2)

Hashing / scanning runs outside the UI rerun/request loop — subprocess, thread, or bundled runtime. UI polls gateway for status.

## UI habits I'm avoiding

- Don't stash prompts/paths in UI state longer than needed
- Don't log sensitive stuff when debugging
- Flow is always: **UI → gateway → pipeline**

## Payoff

Gateway stays portable. HTML or Streamlit is just the dashboard skin.
