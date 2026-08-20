# LakanVault — Research & Additive Controls Backlog

**Status:** Living document (CS301 Investigative Studio / capstone)  
**Last updated:** August 2026  

## Ground rules

1. **Proposal features are locked.** We may ADD controls, spikes, and findings. We do not remove promised MVP features from the submitted proposal.
2. **Attack the leak problem from all sides.** Measure coverage per leak path; document failures as valid research.
3. **Stay honest about MCP.** MCP is a tool-calling protocol, not a full-prompt interception layer. The agent only sends what it chooses to put in tool arguments. Builtin file read / final cloud prompt may never hit LakanVault.
4. **Decision rule.** New idea → spike ≤ ~1 week → keep / defer / reject with evidence → never delete a proposal (P) item.

---

## 1. Proposal-locked MVP (must ship)

| ID | Feature | Owner (proposal) | Approach |
|----|---------|------------------|----------|
| P1 | MCP stdio server + inspect/classify entry | Samiullah | Python MCP SDK; tools call `gateway.classify_text` / sanitize |
| P2 | Regex + entropy Pass-1 | Joan / shared | Pattern library + unit tests; ReDoS-safe bounds |
| P3 | Presidio PII | Joan | spaCy-backed NER config |
| P4 | Confidence-gated local LLM | Joan | Ollama / llama.cpp only on low-confidence findings |
| P5 | Policy allow / warn / mask / block + fail-open/closed by tier | Samiullah | Config-driven engine |
| P6 | Opaque tokens + SQLite restore map | Joan | Session TTL; unrestored-token logging |
| P7 | 3-class anonymizer (heuristic → learned) | Joan | Real secret vs placeholder vs weak-credential; FP cut |
| P8 | Custom dictionary | Shared | User terms → sensitive tiers |
| P9 | RQ1 corpus + baselines | Joan | Precision / recall / F1 vs regex-only and Presidio-only |
| P10 | RQ2 latency (gated vs fixed pipeline) | Samiullah | p50 / p95 per layer |

### Already present in codebase (Phase 1 / early Phase 2)

- CS205 pipeline: integrity → threat → privacy → audit
- `contracts/mcp.py` — Classify / Audit DTOs, tiers, actions
- `local_core/privacy/classifier.py` — Pass-1 cascade (injection → API key regex → PII → allow)
- `gateway.classify_text()` — MCP-ready classify entry (no MCP server process yet)
- `ReversibleAnonymizer` — NAME/EMAIL/PHONE placeholders (chat path; not yet opaque + 3-class)
- HTML UI + FastAPI + demo packaging
- Path A product direction: MCP + clipboard + tray; no silent MITM as default

### Not built yet (still required by proposal)

- MCP stdio server package (`lakanvault_classify`, audit tool)
- Full entropy Pass-1, JWT/SSH/PEM, config-driven policy matrix
- Confidence-gated local LLM escalation wired to policy
- Opaque tokens + SQLite mapping + unrestored metrics
- 3-class anonymizer; custom dictionary UX
- RQ1/RQ2 evaluation corpus and reports
- Tray + packaging (proposal marks one-click tray as v2 distribution; still valuable additive demo)

---

## 2. What we learned (architecture truth)

### MCP does not intercept “the prompt”

| Sees | Does not see |
|------|----------------|
| Tool **inputs** the agent chooses to send | Final assembled prompt to the cloud LLM |
| Tool **outputs** we return | Builtin IDE file reads that skip our tools |

**Implication:** Prefer tools like `read_file_safe` / `classify` that sanitize **at the source**, plus endpoint controls (clipboard). Do not claim “every Cursor prompt passes through MCP” unless a host hook proves it.

### Open research question (RQ0 / Week 1 spike)

> Will the agent reliably call LakanVault tools instead of builtin file reading?  
> What fraction of our threat-model leaks does **clipboard** cover even when MCP is bypassed?

### Red-team (AegisGateway dual interceptor) — summary

MITM + MV3 as a **default** product path fails hard on: cert pinning, WebSockets/Workers bypassing fetch hooks, proxy/VPN/Docker conflicts, SSE token fragmentation, LLM rewriting placeholders, ReDoS/entropy FPs, ONNX OOM fail-open vs fail-closed, Shadow DOM races, RAM on huge prompts.

**Decision:** Browser + silent HTTPS MITM remain **opt-in Lab Mode**, not the silent core. CS301 Option 3 adds an **explicit localhost reverse proxy** (client must set `apiBase` / equivalent) plus an MCP stdio shim. Clipboard + MCP + (optional) IDE extension remain complementary. See [`CLIENT_COMPAT.md`](./CLIENT_COMPAT.md).

---

## 3. Additive controls (all-sides)

### A. Agent / MCP path (soft — measurable)

| ID | Idea | Approach | Risk | Priority |
|----|------|----------|------|----------|
| A1 | Cursor rules / AGENTS.md mandate LV tools | Ship rule pack with demo | Bypassable | High (cheap) |
| A2 | `read_file_safe` / `read_config_safe` | Sanitize on read via MCP | Agent may use builtin read | High |
| A3 | Tool-invocation telemetry | Call vs skip rate (RQ0) | Metric privacy | High |
| A4 | Deny-list paths (`.env`, `*.pem`) | Policy in tool layer | Incomplete | Medium |

### B. Endpoint / machine-adjacent (strong for paste)

| ID | Idea | Approach | Risk | Priority |
|----|------|----------|------|----------|
| B1 | Clipboard watch + Block/Warn | Tray daemon; classify on change | Typed secrets miss | **High** |
| B2 | “Safe paste” from tray | Copy sanitized text from LV | Soft UX | High |
| B3 | Foreground-app scoped clipboard | Only when Cursor/Chrome focused | Platform APIs | Medium |
| B4 | Keylogger / global keystroke capture | **Rejected** — ethics, AV/EDR, consent, unsellable | Do not build | Document rejection only |

### C. IDE extension (high leverage additive)

| ID | Idea | Approach | Risk | Priority |
|----|------|----------|------|----------|
| C1 | VS Code/Cursor extension: paste / classify selection | TS extension → localhost FastAPI or MCP | API limits | **High spike** |
| C2 | Command: “LakanVault: Classify selection” | Selection → gateway → UI | Soft | High |
| C3 | Pre-send chat / agent prompt hook | Spike only if host exposes API | May be impossible | Week 1–2 spike |
| C4 | Status bar tier indicator | UX | Low | Medium |

See also: [IDE_EXTENSION_NOTES.md](./IDE_EXTENSION_NOTES.md).

### D. Browser (vision — after MVP core)

| ID | Idea | Approach | Risk | Priority |
|----|------|----------|------|----------|
| D1 | MV3 extension, AI-domain allowlist | Observe; limited body handling | Shadow DOM; weak body DLP | Late PoC |
| D2 | Native messaging ↔ local LV tray | Extension ↔ daemon | Install friction | With D1 |
| D3 | In-page prompt rewrite | Fragile inject | Breaks host UI | Research only |

### E. Network MITM (Lab Mode only)

| ID | Idea | Approach | Risk | Priority |
|----|------|----------|------|----------|
| E1 | Local HTTPS proxy + lab-only CA | Opt-in “Lab Mode” | Pinning, VPN, Docker | Late optional |
| E2 | Pinning compatibility matrix | Which clients break | Support cost | Required if E1 |
| E3 | SSE sliding-window token restore | FSM across chunks | Latency | Only with E1 |

### F. Hygiene / process

| ID | Idea | Approach |
|----|------|----------|
| F1 | Pre-commit Gitleaks compare | Live contrast vs LV (lit review) |
| F2 | Sanitized worktree | Agent only opens redacted tree |
| F3 | Self-Test Mode (Garak/PyRIT) | Human-triggered only |
| F4 | Threat × control matrix in final report | Coverage + residual risk per path |

---

## 4. How we approach phases (proposal-safe)

| Phase | Focus | Exit criteria |
|-------|--------|---------------|
| Cycle 1 | P1 + P2 + spikes C3 + A3 | MCP works; know if pre-send hook exists |
| Cycle 2 | P3–P6 + B1 clipboard | Policy e2e + paste demo |
| Cycle 3 | P4 escalation + P7 + RQ1/RQ2 | Numbers for research questions |
| Additive track | C1 extension PoC; D1/E1 design spikes | Written findings; optional demos |
| Delivery | Package PoC + report | Honest coverage table; all P-items addressed |

**Framing for markers:**  
“We implemented the proposed MCP-facing gateway and detection stack. Investigation showed MCP does not guarantee full-prompt interception; we **added** complementary controls (clipboard / extension / optional Lab Mode) and report coverage per leak path.”

---

## 5. Threat × control matrix (fill as you learn)

| Leak path | Controls (planned) | Coverage (measure) | Residual risk |
|-----------|--------------------|--------------------|---------------|
| Paste into IDE / chat | B1, B2, C1 | TBD | Typed entry |
| Agent calls our MCP tool | P1–P7, A2, A4 | TBD | — |
| Agent builtin file read | A1, A2, A4, F2 | TBD | If tools skipped |
| Browser ChatGPT / Claude | D1, D2 | TBD | MV3 limits |
| IDE → cloud HTTPS body | E1–E3 (Lab Mode) | TBD | Pinning / install |
| Secret committed to git | F1 | TBD | Not prompt-path |

---

## 6. Spike log (append rows)

| Date | Spike | Result | Decision |
|------|-------|--------|----------|
| | C3 — Does Cursor/VS Code expose pre-send prompt text? | | |
| | A3 — MCP tool call rate with/without rules | | |
| | B1 — Clipboard Block for `sk-` / PEM / email | | |
| | C1 — Extension paste → classify via localhost | | |
| | E1 — MITM Lab Mode feasibility on one client | | |
| | D1 — MV3 observe-only on one AI domain | | |

---

## 7. Learning resources (watch / read by layer)

| Topic | Why |
|-------|-----|
| Official MCP + “build stdio server” | Tools ≠ middleware |
| Cursor MCP / Rules / Agent docs | What the host actually allows |
| Endpoint DLP (clipboard / USB analogies) | Frames B1 for examiners |
| Microsoft Presidio tutorials | Joan pipeline |
| Gitleaks / TruffleHog overviews | Repo scanners ≠ prompt gate |
| Ollama small local models | Confidence-gated escalation |
| OWASP LLM Top 10 (sensitive disclosure) | Problem framing |
| VS Code extension API + `vsce` publish | C1 + store path |

**Do not treat as product direction:** keylogger tutorials; silent always-on MITM as the core story.

---

## 8. Team split (additive)

| Track | Owner | Core (P) | Research add-ons |
|-------|-------|----------|------------------|
| Detection, anonymizer, RQ1 | Joan Allysen | P2–P4, P6–P9 | 3-class Pass-2, FP studies |
| MCP, policy, RQ2, packaging | Samiullah | P1, P5, P10 | B1 clipboard, C1 extension, A3, Lab Mode spikes |
| Shared | Both | Interfaces Week 2 | Threat×control matrix; spike log |

---

## 9. Success criteria (capstone — honest)

1. All proposal-locked features (P1–P10) implemented and demoable.  
2. RQ1 and RQ2 answered with numbers.  
3. Written finding: MCP coverage is **conditional**; clipboard/extension/Lab Mode add measured path coverage.  
4. Residual risks listed (typed secrets, builtin read, browser, pinning).  
5. Rejected approaches documented (keylogger; silent MITM as default) with rationale.

---

## 10. Related docs

- [PLAN.md](./PLAN.md) — Phase 2 execution plan (Path A)  
- [PHASE2_PLAN.md](./PHASE2_PLAN.md) — Sprint backlog  
- [IDE_EXTENSION_NOTES.md](./IDE_EXTENSION_NOTES.md) — Extension + Marketplace process  
- `.cursor/rules/lakanvault-v2-scope.mdc` — Always-on product boundaries  
