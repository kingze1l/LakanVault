# CS301 repo audit

**Branch:** `CS301` (from `Phase-1-YB` at `e509818`)  
**Date:** 18 Aug 2026  
**Scope:** Discovery + CS301 stubs. Task 3 (`legacy_v1/` moves) skipped.

**Verification on this branch:**

| Check | Result |
|-------|--------|
| `python scripts/verify_boundaries.py` | OK: All boundary checks passed |
| `python -m pytest tests/ -q` | 61 passed |

**`Phase-1-YB`:** still at `e509818`. No new commits on that branch.

---

## How labels are used

| Label | Meaning for CS301 (proposal: MCP + regex/entropy + Presidio + policy + opaque tokens + eval) |
|-------|-----------------------------------------------------------------------------------------------|
| **REUSE AS-IS** | Keep in place; only hygiene (unused imports) later |
| **REUSE WITH REWORK** | Keep, but logic must change before it matches the proposal |
| **NOT NEEDED FOR CS301** | Do not delete. Candidate to move to `src/lakanvault/legacy_v1/` **after you approve Task 3** |

Moving packages that other files import would require import rewrites. That is **paused** until you say go (per stop-rules).

---

## File-by-file (`src/lakanvault`)

### `contracts/`

| Path | What it actually does | CS301 |
|------|----------------------|-------|
| `contracts/dtos.py` | Scan/chat/settings/cloud DTOs for the FastAPI/pipeline UI | **REUSE WITH REWORK** — keep Scan/Chat types for demo UI; CS301 needs MCP + policy DTOs (partially already in `mcp.py`) |
| `contracts/mcp.py` | `DataTier`, `PolicyAction`, classify/audit request-response; forbids extra/PII fields | **REUSE AS-IS** — contract for MCP classify/audit; `WARN`/`LOG` unused at runtime |
| `contracts/events.py` | `PipelineEvent` / `StageResult` / `StageStatus` for the 4-stage scan | **REUSE AS-IS** — still used by pipeline; not the CS301 MCP hot path |
| `contracts/ports.py` | ABC `PipelineStage`, `AuditWriter`, `CloudForwarder` | **REUSE AS-IS** — keep if CS205 pipeline stays; new policy engine should get its own port later |
| `contracts/policies.py` | `redact_for_cloud()` builds `CloudTelemetryDTO` | **REUSE WITH REWORK** — this is cloud-egress redaction, **not** the 4-tier allow/warn/mask/block engine in the proposal |

### `orchestration/`

| Path | What it actually does | CS301 |
|------|----------------------|-------|
| `orchestration/gateway.py` | Wires pipeline, chat, integrity registry, `classify_text()`, runtime | **REUSE WITH REWORK** — `classify_text()` is the CS301 entry; chat/integrity/runtime are CS205 extras still imported here |
| `orchestration/pipeline.py` | Fail-closed sequential stages from config order | **REUSE AS-IS** — CS205 scan path; keep for demo unless you drop the HTML scanner |
| `orchestration/bus.py` | Cloud off-by-default; stub forward if enabled | **NOT NEEDED FOR CS301** — proposal is local-only; keep as reference, do not make it the product path |

### `local_core/privacy/`

| Path | What it actually does | CS301 |
|------|----------------------|-------|
| `privacy/detectors.py` | Regex + optional Presidio/spaCy PII spans | **REUSE AS-IS** — this **is** the PII layer; CS301 secret detector must stay a **sibling**, not merged here |
| `privacy/anonymizer.py` | Reversible `NAME_001` / `EMAIL_001` / `PHONE_001`; in-memory map | **REUSE WITH REWORK** — **do not edit in place** (proposal). New opaque-token module beside it; this file stays for comparison |
| `privacy/stage.py` | Pipeline stage: PII **count** only, no text in metadata | **REUSE AS-IS** — CS205 pipeline; not MCP intercept |
| `privacy/classifier.py` | Cascade: injection → 5 API-key regexes → PII → public/allow | **REUSE WITH REWORK** — stub policy+secrets in one function; proposal wants separate secret module + policy engine |

### `local_core/security/`

| Path | What it actually does | CS301 |
|------|----------------------|-------|
| `security/prompt_guard.py` | Regex prompt-injection block before LLM chat | **REUSE AS-IS** — useful extra control; not a substitute for secret DLP |
| `security/__init__.py` | Re-exports guard helpers | **REUSE AS-IS** |

### `local_core/integrity/`

| Path | What it actually does | CS301 |
|------|----------------------|-------|
| `integrity/stage.py` | Chunked SHA-256 vs baseline | **NOT NEEDED FOR CS301** — model hashing is CS205; proposal scope is prompt DLP |
| `integrity/registry.py` | TRUSTED/POISONED/UNVERIFIED + quarantine | **NOT NEEDED FOR CS301** — same; keep for demo/reference |

### `local_core/threat_scanner/`

| Path | What it actually does | CS301 |
|------|----------------------|-------|
| `threat_scanner/stage.py` | Env API-key **names**, POSIX root, world-writable dirs — **does not read prompts** | **NOT NEEDED FOR CS301** — host posture, not prompt DLP |

### `local_core/audit/`

| Path | What it actually does | CS301 |
|------|----------------------|-------|
| `audit/stage.py` | Writes `data/audit/{run_id}.json` (metadata, no raw prompt) | **REUSE WITH REWORK** — useful pattern for MCP audit tool; schema has no tier/action yet |

### `local_core/adapters/` + `runtime/`

| Path | What it actually does | CS301 |
|------|----------------------|-------|
| `adapters/local_llm_client.py` | OpenAI-compatible localhost chat/stream | **REUSE WITH REWORK** — needed later for confidence-gated **local** LLM (P4); today it is the **user chat** backend |
| `adapters/lmstudio_client.py` | Alias `LMStudioClient` → `LocalLLMClient` | **NOT NEEDED FOR CS301** — unused re-export |
| `runtime/llama_runtime.py` | Bundled llama.cpp process on 8081 | **NOT NEEDED FOR CS301** — demo chat runtime, not DLP |
| `runtime/__init__.py` | Re-exports runtime helpers | **NOT NEEDED FOR CS301** — follows runtime |

### `app/`

| Path | What it actually does | CS301 |
|------|----------------------|-------|
| `app/server.py` | FastAPI + static HTML; scan/chat/integrity/settings | **REUSE WITH REWORK** — keep as demo shell; not the MCP stdio server |
| `app/static/index.html` | CS205 dashboard UI | **NOT NEEDED FOR CS301** — standalone chat/integrity UI (keep for reference/demo) |
| `app/static/logo.png`, `favicon.png` | Assets | **NOT NEEDED FOR CS301** — UI assets |
| `app/dashboard.py` | Optional Streamlit skin | **NOT NEEDED FOR CS301** — not on `RUN_DEMO` path |
| `app/picker.py` | Tkinter model file/folder picker | **NOT NEEDED FOR CS301** — integrity UI helper |

### `launcher/`

| Path | What it actually does | CS301 |
|------|----------------------|-------|
| `launcher/bootstrap.py` | Starts bundled runtime + uvicorn + browser | **NOT NEEDED FOR CS301** — demo launcher |
| `launcher/__main__.py` | Calls `bootstrap.main` | **NOT NEEDED FOR CS301** |
| `launcher/__init__.py` | Empty | **NOT NEEDED FOR CS301** |

### `shared/` + `infrastructure/` + `cloud_intelligence/`

| Path | What it actually does | CS301 |
|------|----------------------|-------|
| `shared/config.py` | Merge `default.yaml` + `local.yaml` | **REUSE AS-IS** |
| `shared/url_policy.py` | Localhost-only URL guard | **REUSE AS-IS** |
| `shared/system_prompt.py` | Chat system prompt + placeholder hint | **NOT NEEDED FOR CS301** — chat UX |
| `shared/constants.py` | Chunk size + forbidden cloud field names | **REUSE AS-IS** |
| `shared/exceptions.py` | `NotImplementedStageError` only | **NOT NEEDED FOR CS301** — **dead**; nothing imports it |
| `infrastructure/config_loader.py` | Pydantic `AppConfig` YAML loader | **REUSE WITH REWORK** — **duplicate** of `shared/config.py`; tests use this, gateway uses `shared/config` |
| `cloud_intelligence/adapters/noop.py` | No-op cloud adapters | **NOT NEEDED FOR CS301** — unused except the file itself |

Missing `__init__.py` in several packages (`app/`, `contracts/`, `orchestration/`, `local_core/`, `privacy/`, …). Python 3 namespace packages still import; not a blocker.

**No MCP server package** (`src/lakanvault/mcp/` does not exist).

---

## Dead code / duplicates (REUSE set)

| Issue | Where |
|-------|--------|
| `ScanResponse` imported but unused | `orchestration/pipeline.py` |
| Dual config loaders | `shared/config.py` (runtime) vs `infrastructure/config_loader.py` (some tests) |
| Secrets regex inside classifier | `privacy/classifier.py` — should become sibling `secrets/` module per proposal |
| Human-readable placeholders | `anonymizer.py` vs promised opaque tokens |
| `PolicyAction.WARN` / `LOG` | In `mcp.py` enums, never returned by `classify_content` |
| `lmstudio_client.py` | Unused alias |
| `NotImplementedStageError` | Unused |
| `NoOpCloud*` | Unused |
| Classify vs chat | Chat uses anonymizer + injection; `classify_text` does not anonymize |

---

## Task 3 plan (not executed — waiting for your OK)

If you approve, proposed moves to `src/lakanvault/legacy_v1/` (**no deletes**):

- `app/dashboard.py`, `app/picker.py`, `app/static/`
- `local_core/integrity/`
- `local_core/threat_scanner/`
- `local_core/runtime/`
- `local_core/adapters/lmstudio_client.py`
- `launcher/`
- `cloud_intelligence/`
- `shared/exceptions.py`, `shared/system_prompt.py`

**Blocked until you confirm:** those moves **rename import paths**. `gateway.py` and `server.py` import integrity, runtime, picker, system_prompt. I will not rewrite those until you approve.

**Hygiene only (no moves):** unused `ScanResponse` import in `pipeline.py`.

---

## Scaffolding added

**Task 3 skipped** — CS205 UI/integrity/launcher stay in place. No `legacy_v1/` moves.

| New module | Status |
|------------|--------|
| `local_core/secrets/detector.py` | Regex API-key hits + Shannon entropy. `classify_content` calls `detect_secrets`. Entropy not a gate yet. |
| `local_core/policy/engine.py` | Public→allow, Internal→redact, Confidential/Secret→block. Not wired into classifier yet. |
| `local_core/privacy/opaque_anonymizer.py` | New file; identity anonymize + restore helper. Chat still uses `ReversibleAnonymizer`. |
| `mcp/server.py` | `list_tools()` + `classify()` via gateway. No stdio JSON-RPC loop yet (ticket 1.3). |
| `eval/metrics.py` | `precision_recall_f1` + `latency_summary`. |
| `tests/unit/test_secrets.py` etc. | Contract tests for the stubs. |

---

## Status

| Task | Result |
|------|--------|
| 1 Branch `CS301` from Phase-1-YB | Done — `Phase-1-YB` untouched |
| 2 Repo audit | Done (this file) |
| 3 Move unused CS205 code to `legacy_v1/` | **Skipped** |
| 4 CS301 stubs | Done |
| 5 Single commit of reorg+scaffold | Done |
