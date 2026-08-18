# LakanVault v2 — Implementation Plan (Plan Mode)

**Status:** Active · **Branch:** `main` · **Last updated:** July 2026

This document is the single source of truth for Phase 2 execution. Follow `.cursor/rules/` when implementing.

---

## 1. Objective

Ship a **sellable** local AI DLP product: block secrets/PII before they reach Cursor, ChatGPT, Copilot, or Claude — with audit evidence.

**60-second demo:** tray running → paste API key in Cursor → BLOCKED → audit log entry.

---

## 2. Branch strategy

| Branch | Purpose |
|--------|---------|
| `main` | Active development — Phase 2 and releases |
| `Phase-1-YB` | CS205 submission snapshot (merged into `main`) |

All new v2 work lands on `main`. Do not fork parallel feature branches unless a risky spike needs isolation.

---

## 3. What transferred from Phase-1-YB

- Full CS205 MVP: pipeline, gateway, HTML UI, demo packaging
- 35 tests + `verify_boundaries.py` + CI
- `scripts/smoke_test.py`
- Phase 2 foundation: `contracts/mcp.py`, `docs/v2/`, `.cursor/rules/`

---

## 4. Architecture (unchanged)

```
IDE (Cursor MCP) ──→ MCP server ──→ gateway.classify_text()
Browser (HTML UI) ──→ FastAPI ──→ gateway ──→ pipeline / chat
                                         └──→ local_core (integrity, threat, privacy, audit)
```

**Rules:** `app/` never imports `local_core/` directly. Cloud off by default.

---

## 5. Sprint 1 — execution order

| # | Ticket | Status | Deliverable |
|---|--------|--------|-------------|
| 1.1 | MCP contracts | ✅ Done | `contracts/mcp.py` + tests |
| 1.2 | Classify service | ✅ Done | `gateway.classify_text()` |
| 1.3 | MCP server | 🔄 **Next** | stdio server, 2 tools |
| 1.4 | Tray daemon | ⏳ | `pystray` + subprocess |
| 1.5 | PyInstaller | ⏳ | `.exe` + path tests |

**Sprint 1 gate:** Kartik reviews MCP classify demo + tray launch before Sprint 2.

---

## 6. Ticket 1.2 — Classify service (current)

### Goal
Expose classification through the gateway so MCP and UI share one code path.

### Design
1. `Gateway.classify_text(text, source)` in `orchestration/gateway.py`
2. Run `detect_prompt_injection()` first → if hit: `BLOCK` + `SECRET` tier
3. Run `find_pii_spans()` → map entity types to tier + action
4. Return `ClassifyResponse` (no raw span text)

### Tier mapping (v2.0 stub — refined in Sprint 2)

| Detection | Tier | Action |
|-----------|------|--------|
| Injection pattern | SECRET | BLOCK |
| API key / credential pattern | CONFIDENTIAL | BLOCK |
| Email, phone, name | INTERNAL | REDACT |
| Clean text | PUBLIC | ALLOW |

### Tests
- `tests/unit/test_classify.py` — injection block, API key block, clean allow

### Out of scope for 1.2
- MCP server wiring (1.3)
- Clipboard (Sprint 2)
- Config-driven policy YAML (Sprint 2)

---

## 7. Definition of done (every ticket)

```powershell
python scripts/verify_boundaries.py
python -m pytest tests/ -q
```

One slice → one commit → tests green.

---

## 8. OUT of v2 (do not build)

Okta/ISPM · token vault · autonomous Shadow-Agent · web-proxy unification

---

## 9. References

- Full backlog: [`PHASE2_PLAN.md`](./PHASE2_PLAN.md)
- Research / all-sides controls: [`RESEARCH_BACKLOG.md`](./RESEARCH_BACKLOG.md)
- IDE extension + Marketplace: [`IDE_EXTENSION_NOTES.md`](./IDE_EXTENSION_NOTES.md)
- CS205 demo: [`../demo/GUIDE.md`](../demo/GUIDE.md)
- Cursor rules: [agent-skills setup](https://github.com/addyosmani/agent-skills/blob/main/docs/cursor-setup.md)
