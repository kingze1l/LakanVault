# LakanVault v2 — Phase 2 Plan

**Product:** Local-first AI DLP gateway for small NZ dev teams  
**Branch:** `Phase-2` (create from `Phase-1-YB` when ready)  
**Process:** [agent-skills Cursor setup](https://github.com/addyosmani/agent-skills/blob/main/docs/cursor-setup.md) + `.cursor/rules/`  
**Review:** Real peer review with Kartik at end of each sprint

---

## North star (60-second demo)

1. LakanVault tray icon running (green)
2. User copies fake API key → tries to paste in Cursor
3. **BLOCKED** — `Confidential — API key pattern detected`
4. Dashboard audit log shows the event
5. Pitch: *"No cloud. No enterprise contract. Runs on your laptop."*

---

## What we reuse from CS205 (do not rebuild)

| Module | Path | Role |
|--------|------|------|
| Integrity | `local_core/integrity/` | SHA-256, registry, quarantine |
| Threat | `local_core/threat_scanner/` | Host/env checks only |
| Privacy | `local_core/privacy/` | PII detect + anonymiser |
| Audit | `local_core/audit/` | JSON audit records |
| Prompt guard | `local_core/security/prompt_guard.py` | Pre-LLM injection block |
| Gateway | `orchestration/gateway.py` | Single entry point |
| Contracts | `contracts/dtos.py`, `ports.py` | Layer boundaries |
| Boundaries | `scripts/verify_boundaries.py` | CI gate |

---

## Explicitly OUT of v2

- Okta / ISPM / identity posture engine
- Local API token vault
- Autonomous idle attack / Shadow-Agent threads
- Web-proxy unification with MCP
- Marketing claims without QA evidence

---

## Sprint overview

| Sprint | Weeks | Deliverable | Sellable after |
|--------|-------|-------------|----------------|
| **1** | 4–6 | Tray daemon + MCP classify/audit + PyInstaller | "MCP classify hook for Cursor" |
| **2** | 4–6 | 4-tier DLP + clipboard hook | "Blocks secrets before AI tools" |
| **3** | 4 | Team tier: exports, policies, license | Paid team tier |
| **4** | 2–4 | Self-Test Mode (Garak/PyRIT) | Compliance credibility |

---

## Sprint 1 — Tray + MCP + packaging

**Goal:** Installable Windows background app exposing MCP tools to IDEs.

### Ticket 1.1 — MCP contracts ✅ START HERE
- [ ] `contracts/mcp.py` — Pydantic models for MCP classify/audit
- [ ] `tests/unit/test_mcp_contracts.py` — schema validation tests
- [ ] No server logic yet — contracts only

**Acceptance:** DTOs validate; forbidden fields rejected; tests pass.

### Ticket 1.2 — Classify service (gateway) ✅
- [x] `gateway.classify_text(text)` — wraps privacy + prompt_guard
- [x] `local_core/privacy/classifier.py` — tier + action mapping
- [x] `tests/unit/test_classify.py`

**Acceptance:** Known API key string → `Block`; clean text → `Allow`.

### Ticket 1.3 — MCP server module
- [ ] `src/lakanvault/mcp/server.py` — stdio MCP server
- [ ] Tools: `lakanvault_classify`, `lakanvault_audit_recent`
- [ ] Read-only; no prompt forwarding to cloud
- [ ] `tests/unit/test_mcp_server.py` (tool list + classify round-trip)

**Acceptance:** `cursor` / MCP client can call classify locally.

### Ticket 1.4 — Tray daemon shell
- [ ] `src/lakanvault/tray/` — `pystray` icon (green/amber/red)
- [ ] Start/stop gateway subprocess from tray
- [ ] `tests/` for tray state machine (mock subprocess)

**Acceptance:** Tray icon appears; click opens dashboard URL.

### Ticket 1.5 — PyInstaller + path routing
- [ ] `scripts/build_tray_exe.ps1`
- [ ] `shared/paths.py` — `resource_path()` with `sys._MEIPASS` support
- [ ] Tests: asset path resolves in dev and frozen mode (mock `_MEIPASS`)

**Acceptance:** `.exe` launches tray; static assets load; audit dir writable.

### Sprint 1 gate (Kartik review)
- [ ] Demo: MCP classify from terminal
- [ ] Demo: tray launches, dashboard opens
- [ ] `verify_boundaries.py` + full pytest green
- [ ] No scope creep into Sprint 2 clipboard hooks

---

## Sprint 2 — 4-tier DLP + clipboard

### Ticket 2.1 — Classification engine
- [ ] `local_core/privacy/tiers.py` — Public / Internal / Confidential / Secret
- [ ] `local_core/privacy/policy.py` — action matrix (Allow/Warn/Redact/Block/Log)
- [ ] Config in `config/default.yaml` under `privacy.tiers`
- [ ] Tests for each tier + action combination

### Ticket 2.2 — Integrate tiers into pipeline + chat
- [ ] Privacy stage emits tier + action in metadata
- [ ] Gateway chat path respects `Block` before LLM call
- [ ] Audit records tier + action (not raw text)

### Ticket 2.3 — Clipboard monitor (Windows)
- [ ] `src/lakanvault/tray/clipboard.py` — detect paste-bound content
- [ ] Classify on clipboard change; toast on Block/Warn
- [ ] Scope: Windows only for v2.0

### Ticket 2.4 — Cursor/VS Code integration doc
- [ ] `docs/v2/CURSOR_SETUP.md` — MCP config snippet for Cursor
- [ ] Demo script updated

### Sprint 2 gate
- [ ] 60-second demo works end-to-end
- [ ] Kartik review

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
- Peer review note in commit or sprint doc if Kartik flagged something

---

## Cursor usage

Rules in `.cursor/rules/` load automatically. When starting work, say:

> Follow `lakanvault-v2-scope` and `incremental-implementation`. Implement Sprint 1 Ticket X only.

Add `code-review-and-quality` before merge. Add security rule when touching DLP/clipboard (copy from agent-skills when needed).

---

## Current status

| Ticket | Status |
|--------|--------|
| Cursor rules + this plan | ✅ Done |
| 1.1 MCP contracts | ✅ Done |
| 1.2 Classify service | ✅ Done |
| 1.3 MCP server | 🔄 Next |
| 1.4 Tray daemon | ⏳ Pending |
| 1.5 PyInstaller | ⏳ Pending |

---

## Pricing sketch (for sales conversations)

| Tier | Price | Includes |
|------|-------|----------|
| Solo | Free | 1 seat, classify + block + local audit |
| Team | ~$149/mo or ~$1,500/yr | 5–20 seats, exports, policy profiles |
| Services | Bundled in client work | "Built with LakanVault-safe pipeline" |
