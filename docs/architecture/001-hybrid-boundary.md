# 001 — Local vs cloud boundary (my rules)

Phase 1a — I treat this as the import firewall for the whole project.

## Why I split it this way

Sensitive stuff (models, prompts, hashes, PII, audit logs) stays in `local_core`. Cloud is optional enrichment only. Nothing sensitive should leak across without going through `contracts` and redaction.

## Who can import what

| Layer | I allow imports from | I never import |
|-------|----------------------|----------------|
| `app` | `orchestration`, `contracts`, `infrastructure`, `shared` | `local_core`, `cloud_intelligence` |
| `orchestration` | `local_core`, `contracts`, `infrastructure`, `shared` | `cloud_intelligence` directly — ports only |
| `local_core` | `contracts`, `infrastructure`, `shared` | `cloud_intelligence`, `app` |
| `cloud_intelligence` | `contracts`, `infrastructure`, `shared` | `local_core`, `app` |
| `contracts` | `shared`, stdlib, pydantic | everything else |

## Two types I keep separate

- **`SensitiveContext`** — local only (paths, prompts). Never goes in a cloud DTO.
- **`CloudTelemetryDTO`** — what I'm willing to send out. I only build this via `contracts.policies.redact_for_cloud()`.

## Egress — one door

Only `orchestration/bus.py` forwards toward cloud. I won't hand-roll dicts there; everything goes through `contracts.policies`.

## How I'll enforce it

- `scripts/verify_boundaries.py` (P1b) — catch bad imports
- Contract tests — catch forbidden fields on cloud DTOs

## Adapter pattern

`local_core/adapters/` and `cloud_intelligence/adapters/` implement `contracts.ports`. Events + ports only — no direct local ↔ cloud calls.
