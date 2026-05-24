# 002 — Pipeline order + fail-closed (my rules)

Phase 1a — fixed stage order so I'm not bolting security on later.

## Order (from `config/default.yaml`)

```yaml
pipeline:
  order: [integrity, threat_scanner, privacy, audit]
```

| Stage | Where | What it can see |
|-------|-------|-----------------|
| Integrity | `local_core/integrity/` | Model paths, manifest baseline |
| Threat scanner | `local_core/threat_scanner/` | Host/env misconfig — **not** raw prompts |
| Privacy | `local_core/privacy/` | Prompts / text going to the LLM |
| Audit | `local_core/audit/` | Stage outcomes, redacted metadata |

## If something fails — I stop everything

1. `FAIL` or `ERROR` on any stage → no downstream stages run.
2. No cloud forward if anything failed or if `cloud.enabled` is false.
3. Audit gets failure type + stage name — not prompt text or model bytes.
4. I don't show partial runs as "complete" in UI or cloud.

## Hash chunk size

`local.chunk_size_bytes: 1048576` (1 MB). Fewer disk reads on 30GB+ models; RAM stays tiny on my EliteBook.

## Split of responsibility

- `orchestration` — order and wiring
- `local_core` — actual scan/hash logic
- Threat vs privacy — different inputs on purpose so threat doesn't see PII before privacy runs
