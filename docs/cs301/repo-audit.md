# CS301 repo audit (cs301-phase2)

**Branch:** `cs301-phase2` (created from `Phase-1-YB` at `e509818`)  
**Date:** 18 Aug 2026  
**Phase-1-YB:** untouched (still `e509818`; no new commits on that branch)  
**Proposal file:** `docs/cs301/proposal.md` is **not** in the repo. Classifications use the submitted CS301 proposal scope (MCP DLP gateway, secrets + PII, policy, tokens, RQ1/RQ2).

**Task 3 (reorganize / move to `legacy_v1/`) is not done.** That waits for your review. Moving integrity, the HTML/Streamlit UI, or launcher would require **import rewrites** in files that still need those modules for the CS205 demo path — see questions at the end.

---

## Verification on this branch

| Check | Result |
|-------|--------|
| `python scripts/verify_boundaries.py` | **OK: All boundary checks passed.** |
| `python -m pytest tests/ -q` | **40 passed** |

---

## Classification key

| Label | Meaning for CS301 |
|-------|-------------------|
| **REUSE AS-IS** | Keep in place; only later cleanup (dead code / unused imports) if you approve Task 3 |
| **REUSE WITH REWORK** | Keep in the live tree; do not rewrite yet — notes below |
| **NOT NEEDED FOR CS301** | Out of proposal DLP/MCP scope. **Do not delete.** Candidate for `src/lakanvault/legacy_v1/` after you approve |

---

## `src/lakanvault` — file-by-file

### `app/` (UI shell)

| Path | What it actually does | Class | Why |
|------|----------------------|-------|-----|
| `app/server.py` | FastAPI HTTP API + serves HTML dashboard; scan, chat, integrity, settings, runtime | NOT NEEDED FOR CS301 | Standalone chat/integrity UI is CS205 demo, not MCP interception. **Do not move yet** — `launcher/bootstrap.py` imports it. |
| `app/dashboard.py` | Optional Streamlit skin calling `Gateway` | NOT NEEDED FOR CS301 | Proposal UI is MCP, not Streamlit. Unused by `RUN_DEMO.bat`. Safe to move once nothing imports it (nothing production does except README). |
| `app/picker.py` | Tkinter file/folder picker for model files | NOT NEEDED FOR CS301 | Model-file picking for integrity demo only. |
| `app/static/index.html` | Primary HTML dashboard (chat, pipeline, integrity, audit) | NOT NEEDED FOR CS301 | CS205 product UI. |
| `app/static/logo.png` | Dashboard logo | NOT NEEDED FOR CS301 | UI asset. |
| `app/static/favicon.png` | Favicon | NOT NEEDED FOR CS301 | UI asset. |

### `contracts/`

| Path | What it actually does | Class | Why |
|------|----------------------|-------|-----|
| `contracts/dtos.py` | Scan/chat/settings/cloud DTOs (Pydantic) | REUSE WITH REWORK | Keep scan/chat DTOs for tests; cloud DTO is CS205. CS301 needs policy/finding DTOs aligned with allow/warn/**mask**/block (today MCP uses **redact**). |
| `contracts/events.py` | `PipelineEvent`, `StageResult`, statuses | REUSE AS-IS | Fail-closed pipeline events still useful if stages remain. |
| `contracts/ports.py` | `PipelineStage`, `AuditWriter`, `CloudForwarder` ABCs | REUSE WITH REWORK | Keep `PipelineStage`. `CloudForwarder` is not CS301 core. |
| `contracts/policies.py` | `redact_for_cloud()` for telemetry DTO | NOT NEEDED FOR CS301 | Cloud egress policy, not the 4-tier DLP engine. Name collision with CS301 “policy engine”. |
| `contracts/mcp.py` | `DataTier`, `PolicyAction`, classify/audit request/response; forbids extra fields | REUSE WITH REWORK | Right shape for MCP tools. Rework: `REDACT` vs proposal `mask`; `WARN`/`LOG` unused by classifier; no MCP server yet. |

### `orchestration/`

| Path | What it actually does | Class | Why |
|------|----------------------|-------|-----|
| `orchestration/gateway.py` | Wires pipeline, chat (inject → anonymize → LLM → restore), `classify_text()` | REUSE WITH REWORK | `classify_text()` is the CS301 entry. Chat/integrity/runtime methods are CS205. MCP must not pretend to see the full cloud prompt. |
| `orchestration/pipeline.py` | Runs stages fail-closed; returns event + duration | REUSE AS-IS | Keep for any staged pipeline. Unused import: `ScanResponse`. |
| `orchestration/bus.py` | Cloud forward (disabled by default); stub HTTP | NOT NEEDED FOR CS301 | Cloud bus; not MCP DLP. Keep until Task 3 so gateway still constructs it. |

### `local_core/privacy/`

| Path | What it actually does | Class | Why |
|------|----------------------|-------|-----|
| `privacy/detectors.py` | PII spans: regex + Presidio + optional spaCy | REUSE AS-IS | This is the PII sibling the proposal wants. Do **not** merge secrets into it. |
| `privacy/anonymizer.py` | Reversible `NAME_001` / `EMAIL_001` / `PHONE_001`; in-memory map | REUSE AS-IS | Keep original for comparison. CS301 opaque tokens = **new module**, not an in-place edit. |
| `privacy/stage.py` | Pipeline privacy stage: counts PII, no span text in metadata | REUSE WITH REWORK | Useful for PII pass; does not emit tier/action for CS301 policy. |
| `privacy/classifier.py` | Cascade: injection → API-key regex → PII → allow | REUSE WITH REWORK | Working Pass-1, but **secrets are merged into this file**. Proposal: new secret-detection **sibling**, not this mix. No entropy, no 3-class, no warn/log. |

### `local_core/security/`

| Path | What it actually does | Class | Why |
|------|----------------------|-------|-----|
| `security/prompt_guard.py` | Regex prompt-injection block before LLM | REUSE WITH REWORK | Useful extra control; not in CS301 feature table as “injection = Secret”. Confirm with Joan whether injection stays Secret/Block. |
| `security/__init__.py` | Re-exports guard helpers | REUSE AS-IS | Package export. |

### `local_core/integrity/`

| Path | What it actually does | Class | Why |
|------|----------------------|-------|-----|
| `integrity/stage.py` | Chunked SHA-256 of a model file vs baseline | NOT NEEDED FOR CS301 | Model hashing, not prompt DLP. |
| `integrity/registry.py` | TRUSTED / POISONED / UNVERIFIED + quarantine | NOT NEEDED FOR CS301 | Model registry for CS205 demo. |

### `local_core/threat_scanner/`

| Path | What it actually does | Class | Why |
|------|----------------------|-------|-----|
| `threat_scanner/stage.py` | Host env-key names, POSIX root, world-writable dirs; **does not read prompts** | NOT NEEDED FOR CS301 | Host posture, not prompt DLP. |

### `local_core/audit/`

| Path | What it actually does | Class | Why |
|------|----------------------|-------|-----|
| `audit/stage.py` | Writes `data/audit/{run_id}.json` (no raw prompt) | REUSE WITH REWORK | Keep idea of local audit. CS301 MCP `audit_recent` and RQ logging need a prompt/classify-oriented store, not only model-scan JSON. |

### `local_core/adapters/`

| Path | What it actually does | Class | Why |
|------|----------------------|-------|-----|
| `adapters/local_llm_client.py` | OpenAI-compatible localhost chat client | REUSE WITH REWORK | Needed for confidence-gated **local** LLM (P4 / RQ2), not as the product chat UI. |
| `adapters/lmstudio_client.py` | Alias re-export of `LocalLLMClient` | NOT NEEDED FOR CS301 | Dead compatibility shim; **no other file imports it**. |

### `local_core/runtime/`

| Path | What it actually does | Class | Why |
|------|----------------------|-------|-----|
| `runtime/llama_runtime.py` | Bundled llama.cpp process manager | NOT NEEDED FOR CS301 | Demo LLM runtime, not DLP. |
| `runtime/__init__.py` | Re-exports runtime helpers | NOT NEEDED FOR CS301 | Pairs with llama_runtime. |

### `launcher/`

| Path | What it actually does | Class | Why |
|------|----------------------|-------|-----|
| `launcher/bootstrap.py` | Starts bundled runtime + uvicorn + browser | NOT NEEDED FOR CS301 | CS205 demo launcher. |
| `launcher/__main__.py` | Entry to bootstrap | NOT NEEDED FOR CS301 | Demo entry. |
| `launcher/__init__.py` | Empty | NOT NEEDED FOR CS301 | Package marker. |

### `infrastructure/`

| Path | What it actually does | Class | Why |
|------|----------------------|-------|-----|
| `infrastructure/config_loader.py` | Pydantic YAML config (`AppConfig`) | REUSE WITH REWORK | **Duplicate** of `shared/config.py` (dict merge). Tests use this; gateway uses `shared.config`. Pick one for CS301. |

### `shared/`

| Path | What it actually does | Class | Why |
|------|----------------------|-------|-----|
| `shared/config.py` | Merge `default.yaml` + `local.yaml`; runtime URL env | REUSE AS-IS | Live config path for gateway. |
| `shared/url_policy.py` | Localhost-only URL check | REUSE AS-IS | Keep for any local LLM / MCP HTTP. |
| `shared/system_prompt.py` | Chat system prompt + placeholder hint | NOT NEEDED FOR CS301 | Sanitized-chat product, not MCP DLP core. |
| `shared/constants.py` | Chunk size + forbidden cloud field names | REUSE WITH REWORK | Cloud-field list is CS205; chunk size is integrity. |
| `shared/exceptions.py` | `NotImplementedStageError` | NOT NEEDED FOR CS301 | **Unused** anywhere else. |

### `cloud_intelligence/`

| Path | What it actually does | Class | Why |
|------|----------------------|-------|-----|
| `cloud_intelligence/adapters/noop.py` | No-op enrich/analytics classes | NOT NEEDED FOR CS301 | **Unused** by runtime gateway (bus never imports these classes). Boundary package only. |

---

## Dead code / duplicates (on REUSE and related files)

| Issue | Where | Note |
|-------|--------|------|
| Unused import `ScanResponse` | `orchestration/pipeline.py` | Imported, never used |
| Unused class | `shared/exceptions.py` | No references |
| Unused module | `adapters/lmstudio_client.py` | No importers |
| Unused cloud adapters | `cloud_intelligence/adapters/noop.py` | Not constructed by gateway |
| Duplicate config loaders | `shared/config.py` vs `infrastructure/config_loader.py` | Two sources of truth |
| Duplicate secret-ish detection | `classifier.py` API-key regex vs future sibling secrets module | Classifier currently owns secrets |
| Naming clash | `contracts/policies.py` (cloud redact) vs CS301 policy engine | Easy to confuse |
| `PolicyAction.REDACT` vs proposal **mask** | `contracts/mcp.py` | Same idea, different word |
| `WARN` / `LOG` never returned | `classifier.py` | Enum-only |
| Commented HTTP | `orchestration/bus.py` | Cloud stub |
| Classifier `source` discarded | `gateway.classify_text` | Validates then ignores |

No unused-import sweep was run with a linter beyond grep; pytest does not fail on unused imports.

---

## Test suite map (current)

| File | Covers |
|------|--------|
| `tests/unit/test_classify.py` | Cascade + `gateway.classify_text` |
| `tests/unit/test_mcp_contracts.py` | MCP DTO validation |
| `tests/unit/test_anonymizer.py` | NAME/EMAIL restore |
| `tests/unit/test_prompt_guard.py` | Injection regex |
| `tests/unit/test_pipeline.py` | Fail-closed stages |
| `tests/unit/test_registry.py` | Model baselines |
| `tests/unit/test_settings.py` | local.yaml |
| `tests/unit/test_url_policy.py` | localhost URLs |
| `tests/contracts/*` | Cloud DTO / bus / gateway config |

CS301 RQ1/RQ2 corpus tests **do not exist yet**.

---

## Planned Task 3 moves (not executed)

Would go to `src/lakanvault/legacy_v1/` **only after you approve**, because several are imported by `gateway.py` / `server.py` / `bootstrap.py`:

| Candidate | Blocker |
|-----------|---------|
| `app/dashboard.py` | Low — unused at runtime |
| `app/server.py` + `static/` | High — demo + launcher |
| `integrity/*` | High — gateway + tests |
| `threat_scanner` | Medium — pipeline |
| `runtime/` + `launcher/` | High — demo |
| `cloud_intelligence/` | Medium — `verify_boundaries.py` still names this package (`scripts/` — out of allowed touch set without your OK) |
| `lmstudio_client.py`, `exceptions.py` | Low |

**Not moving:** `privacy/anonymizer.py` — proposal says keep original and add a **new** opaque-token module.

---

## Planned Task 4 scaffolding (not executed)

New stubs (proposed paths, same layering):

| New module | Layer | RQ |
|------------|-------|----|
| `src/lakanvault/mcp/server.py` | new `mcp` package (orchestration-adjacent; must not import `app`) | RQ2 (latency of intercept path) |
| `src/lakanvault/local_core/secrets/detector.py` | local_core sibling to privacy | RQ1 |
| `src/lakanvault/local_core/policy/engine.py` | local_core | RQ1 (tier actions) |
| `src/lakanvault/local_core/privacy/opaque_anonymizer.py` | local_core (new file, old anonymizer stays) | RQ1 |
| `src/lakanvault/eval/metrics.py` | eval (or `local_core/eval`) | RQ1 + RQ2 |

Matching `tests/unit/test_*.py` stubs.

`scripts/verify_boundaries.py` would need a rule for `mcp/` / `eval/` if those packages appear — that file is **outside** `src/`, `tests/`, `docs/`. **Need your OK** before editing it.

---

## Reorganization Summary

_Not applicable yet — waiting for review of this audit._

## Scaffolding Added

_None yet — waiting for review._

---

## Stop / ask before proceeding

Please confirm:

1. **Task 3:** Move NOT NEEDED modules into `legacy_v1/` even if that means updating imports in `gateway.py` / tests (you previously said stop before renaming files other files import from)?
2. **Chat UI / integrity:** Leave in place for CS205 demo on this branch, or isolate in `legacy_v1/` and accept a broken `RUN_DEMO.bat` until rewired?
3. **Task 4:** OK to add empty stubs under `src/lakanvault` + `tests/` + this doc only (no `scripts/` change until you say so)?
4. **Commit:** One commit on `cs301-phase2` after you approve 3–4, leaving `Phase-1-YB` at `e509818`?

---

## How to work with Joan

```text
git fetch
git checkout cs301-phase2
```

PRs **into `cs301-phase2`**. Do not commit on `Phase-1-YB`.
