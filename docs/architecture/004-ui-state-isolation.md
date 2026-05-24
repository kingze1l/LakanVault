# 004 — UI vs gateway (my rules)

Phase 1a — Streamlit is display only; gateway must survive without it (Phase 2 `.exe`).

## Why

Streamlit reruns the whole script on clicks. Hashing a 30GB model inline would freeze the dashboard. I want gateway logic I can run in a background process later.

## `orchestration/gateway.py` — plain Python only

- In: `str`, `Path`, dict, contract types — **no** `st.session_state`, `st.button`, etc.
- Out: DTOs / status enums — **no** Streamlit widgets
- Zero UI imports in this file

## `app/` — thin Streamlit shell

- UI calls `Gateway.receive(...)`
- UI renders results
- I don't log raw prompts, read model bytes here, or import `cloud_intelligence`

## Heavy work (Phase 2)

Hashing / scanning runs outside the Streamlit rerun loop — subprocess, thread, or `.exe`. UI polls gateway for status.

## Streamlit habits I'm avoiding

- Don't stash prompts/paths in `session_state` longer than needed
- Don't `st.write` sensitive stuff when debugging
- Flow is always: **UI → gateway → pipeline**

## Payoff

Gateway stays portable. Streamlit is just the CISO dashboard skin.
