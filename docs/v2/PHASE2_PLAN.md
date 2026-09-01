# LakanVault v2 — Phase 2 Plan

**Product:** Local-first AI DLP gateway for small NZ dev teams  
**Active branch:** `CS301` (Option 3 hybrid gateway)  
**Frozen (historical):** `Phase-1-YB` — CS205 snapshot; do not modify  
**Target merge:** `CS301` → `main` via PR  
**Review:** Joan Allysen at sprint gates (detection, anonymizer, RQ1)

---

## North star (60-second demo)

1. LakanVault tray icon running (green)
2. User copies fake API key → tries to paste in Cursor
3. **BLOCKED** — `Confidential — API key pattern detected`
4. Audit log shows the event
5. Pitch: *"No cloud. No enterprise contract. Runs on your laptop."*

---

## Inherited pipeline (kept, not rebuilt)


| Module       | Path                                  | Role                          |
| ------------ | ------------------------------------- | ----------------------------- |
| Integrity    | `local_core/integrity/`               | SHA-256, registry, quarantine |
| Threat       | `local_core/threat_scanner/`          | Host/env checks only          |
| Privacy      | `local_core/privacy/`                 | PII detect + anonymiser       |
| Audit        | `local_core/audit/`                   | JSON audit records            |
| Prompt guard | `local_core/security/prompt_guard.py` | Pre-LLM injection block       |
| Gateway      | `orchestration/gateway.py`            | Single entry point            |
| Contracts    | `contracts/dtos.py`, `ports.py`       | Layer boundaries              |
| Boundaries   | `scripts/verify_boundaries.py`        | CI gate                       |


---



## Explicitly OUT of v2

- Okta / ISPM / identity posture engine
- Local API-key password manager (BYOK pass-through; mappings stay in RAM)
- Autonomous idle attack / Shadow-Agent threads
- Silent machine-wide TLS MITM
- Marketing claims without QA evidence

**CS301 Option 3 (approved additive):** explicit localhost API proxy + MCP stdio shim + in-memory token map. See [`../architecture/005-option3-hybrid-gateway.md`](../architecture/005-option3-hybrid-gateway.md) and [`CLIENT_COMPAT.md`](./CLIENT_COMPAT.md).

---



## Sprint overview


| Sprint | Weeks | Deliverable                                    | Sellable after                   |
| ------ | ----- | ---------------------------------------------- | -------------------------------- |
| **1**  | 4–6   | Tray daemon + MCP classify/audit + PyInstaller | "MCP classify hook for Cursor"   |
| **2**  | 4–6   | 4-tier DLP + clipboard hook                    | "Blocks secrets before AI tools" |
| **3**  | 4     | Team tier: exports, policies, license          | Paid team tier                   |
| **4**  | 2–4   | Self-Test Mode (Garak/PyRIT)                   | Compliance credibility           |


---



## Sprint 1 — Tray + MCP + packaging (+ CS301 Option 3)

**Goal:** Installable Windows background app exposing MCP tools to IDEs.  
**CS301 add-on (approved):** localhost OpenAI proxy, in-memory token map, MCP stdio sanitizing shim. See ADR-005.

### Ticket 1.1 — MCP contracts ✅ DONE

- [x] `contracts/mcp.py` — Pydantic models for MCP classify/audit
- [x] `tests/unit/test_mcp_contracts.py` — schema validation tests
- [x] No server logic in contracts layer

**Acceptance:** DTOs validate; forbidden fields rejected; tests pass.

### Ticket 1.2 — Classify service (gateway) ✅ DONE

- [x] `gateway.classify_text(text)` — wraps privacy + prompt_guard
- [x] `local_core/privacy/classifier.py` — tier + action mapping
- [x] `tests/unit/test_classify.py`

**Acceptance:** Known API key string → `Block`; clean text → `Allow`.

### Ticket 1.3 — MCP server module 🔄 PARTIAL

- [x] `src/lakanvault/mcp/server.py` — `lakanvault_classify`, `lakanvault_audit_recent`
- [x] Read-only; no prompt forwarding to cloud
- [x] `tests/unit/test_mcp_server.py` (tool list + classify + audit metadata)
- [x] `src/lakanvault/mcp/stdio_proxy.py` — console shim sanitizes child `tools/call` via daemon HTTP
- [x] `tests/unit/test_mcp_stdio_proxy.py`
- [ ] Full stdio JSON-RPC loop inside `mcp/server.py` (deferred — shim is the canonical MCP wrapper for now)

**Acceptance:** IDE can call classify locally; tool outputs sanitizable via `lakanvault-mcp` shim.

### Ticket 1.4 — Tray daemon shell ⏳ NOT STARTED

- [ ] `src/lakanvault/tray/` — `pystray` icon (green/amber/red)
- [ ] Start/stop gateway subprocess from tray
- [ ] `tests/` for tray state machine (mock subprocess)

**Acceptance:** Tray icon appears; click opens dashboard URL.

### Ticket 1.5 — PyInstaller + path routing 🔄 PARTIAL

- [x] `scripts/build_tray_exe.ps1` — onedir windowed daemon + console `lakanvault-mcp`
- [x] `shared/paths.py` — `resource_path()` + `writable_data_root()` with `_MEIPASS` support
- [x] `tests/unit/test_paths.py` — dev vs frozen path mocks
- [x] `tests/unit/test_packaging.py` — build script contract
- [ ] Manual smoke: built `.exe` launches dashboard; MCP console exe stdio purity verified on real machine

**Acceptance:** `.exe` launches; static assets load; audit dir writable beside exe (not in `_MEIPASS`).

### CS301 Option 3 — Hybrid gateway ✅ DONE (code + tests)

Delivered on branch `CS301` (commit `bd46584`):

- [x] `contracts/proxy.py` — vault port, transform DTOs, forbidden log fields
- [x] `infrastructure/token_vault.py` — in-memory SQLite `:memory:`, TTL, cap
- [x] `local_core/dlp/transformer.py` — unified secrets + PII + policy + opaque tokens
- [x] `local_core/dlp/openai_payload.py` — OpenAI JSON walk; restore assistant text only
- [x] `orchestration/proxy_gateway.py` — sanitize → upstream → restore lifecycle
- [x] `app/proxy_routes.py` — `/v1/chat/completions`, `/v1/models`, `/internal/v1/sanitize`
- [x] `infrastructure/upstream/openai.py` + `sse.py` — allowlisted upstream + sliding-tail SSE restore
- [x] `orchestration/gateway.py` — `/api/chat` uses same DLP (API keys block)
- [x] `local_core/dlp/image_inspector.py` — block-first scaffold (OCR engine not wired; `allow_images: false`)
- [x] `docs/architecture/005-option3-hybrid-gateway.md`, `docs/v2/CLIENT_COMPAT.md`
- [x] 128 pytest tests + `verify_boundaries.py` + `smoke_test.py` green

**Not claimed:** universal Cursor support, 100% DLP, Anthropic proxy (Sprint 2), real OCR engine (Sprint 3).

### Sprint 1 gate (Joan review)

- [ ] Demo: MCP classify from terminal
- [ ] Demo: tray launches, dashboard opens
- [x] `verify_boundaries.py` + full pytest green (128 passed)
- [x] `smoke_test.py` — dashboard, injection block, internal sanitize, `/v1` secret 403
- [x] No scope creep into Sprint 2 clipboard hooks
- [ ] PR `CS301` → `main` merged
- [ ] Joan sign-off

---



## Sprint 2 — 4-tier DLP + clipboard

**Note:** Option 3 already delivered core DLP for chat + proxy paths. Sprint 2 focuses on clipboard, pipeline metadata, and client evidence.

### Ticket 2.1 — Classification engine 🔄 PARTIAL (ahead of schedule)

- [x] `contracts/mcp.py` — `DataTier` + `PolicyAction` enums
- [x] `local_core/policy/engine.py` — action matrix
- [x] `tests/unit/test_policy_engine.py`
- [ ] Dedicated `tiers.py` / `policy.py` modules (optional refactor)
- [ ] Config in `config/default.yaml` under `privacy.tiers` (editable profiles)



### Ticket 2.2 — Integrate tiers into pipeline + chat 🔄 PARTIAL

- [ ] Privacy stage emits tier + action in metadata
- [x] Gateway chat path respects `Block` before LLM call (`transform_text` in `_prepare_chat`)
- [x] Proxy path respects `Block` / `Redact` (`proxy_gateway` + `transformer`)
- [ ] Audit records tier + action consistently (not raw text)



### Ticket 2.3 — Clipboard monitor (Windows)

- [ ] `src/lakanvault/tray/clipboard.py` — detect paste-bound content
- [ ] Classify on clipboard change; toast on Block/Warn
- [ ] Scope: Windows only for v2.0



### Ticket 2.4 — Cursor/VS Code integration doc

- [ ] `docs/v2/CURSOR_SETUP.md` — MCP config snippet for Cursor
- [ ] Demo script updated



### Sprint 2 gate

- [ ] 60-second demo works end-to-end
- [ ] Joan review

---



## Sprint 3 — Team tier (monetization)



### Ticket 3.1 — Audit export

- [ ] CSV + PDF export from audit log
- [ ] No raw PII in exports (counts + tiers only)



### Ticket 3.2 — Policy profiles

- [ ] `strict` vs `dev` profiles in config
- [ ] UI/settings toggle



### Ticket 3.3 — License check (simple)

- [ ] Solo = free, Team = license key file or env var
- [ ] No DRM theatre — honest gate for paid features



### Sprint 3 gate

- [ ] Pricing page draft
- [ ] One pilot customer conversation (agency/barbershop angle)

---



## Sprint 4 — Self-Test Mode (optional credibility)



### Ticket 4.1 — Garak/PyRIT runner

- [ ] On-demand only; human clicks "Run self-test"
- [ ] Scored report PDF
- [ ] Full logging; no unsupervised runs

---



## Definition of done (every ticket)

```powershell
python scripts/verify_boundaries.py   # must pass
python -m pytest tests/ -q            # must pass
```

- One logical commit per slice
- No placeholders or TODO in shipped code
- Peer review note in commit or sprint doc if Joan flagged something

---



## Cursor usage

Rules in `.cursor/rules/` load automatically. When starting work, say:

> Follow `lakanvault-v2-scope` and `incremental-implementation`. Implement Sprint 1 Ticket X only.

Add `code-review-and-quality` before merge. Add security rule when touching DLP/clipboard (copy from agent-skills when needed).

---



## Current status (updated 2026-08-31)


| Ticket / area            | Status | Notes |
| ------------------------ | ------ | ----- |
| Cursor rules + this plan | ✅ Done | |
| 1.1 MCP contracts        | ✅ Done | |
| 1.2 Classify service     | ✅ Done | |
| 1.3 MCP server           | 🔄 Partial | Tools + shim done; full stdio server loop deferred |
| 1.4 Tray daemon          | ⏳ Not started | Blocks north-star demo |
| 1.5 PyInstaller          | 🔄 Partial | Script + path tests; no frozen exe smoke yet |
| CS301 Option 3 proxy     | ✅ Done | On `CS301`; not merged to `main` |
| Sprint 1 gate            | 🔄 Partial | Tests green; Joan review + tray + PR pending |
| Sprint 2 DLP core        | 🔄 Partial | Transformer/policy in place; clipboard not started |

### Sprint 1 — what's left to close

1. **Tray** (`pystray`) — ticket 1.4  
2. **Frozen `.exe` smoke** — run `scripts/build_tray_exe.ps1`, verify dashboard + MCP console  
3. **Joan demo** — MCP classify + `/v1` API-key block + dashboard audit  
4. **Merge PR** — `CS301` → `main` (after review)

### Already shipped (do not rebuild)

- OpenAI `/v1/chat/completions` proxy with SSE restore  
- In-memory token vault + opaque `[LV_…]` tokens  
- MCP stdio sanitizing shim (`lakanvault-mcp`)  
- Unified DLP on `/api/chat` and proxy paths  
- ADR-005 + client compatibility matrix


---



## Pricing sketch (for sales conversations)


| Tier     | Price                  | Includes                               |
| -------- | ---------------------- | -------------------------------------- |
| Solo     | Free                   | 1 seat, classify + block + local audit |
| Team     | ~$149/mo or ~$1,500/yr | 5–20 seats, exports, policy profiles   |
| Services | Bundled in client work | "Built with LakanVault-safe pipeline"  |


