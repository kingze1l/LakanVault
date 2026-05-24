# Data classification — what I allow over the cloud boundary

Default: `cloud.enabled: false` → nothing leaves the machine.

## OK to send (if I ever turn cloud on)

| Type | Examples | Notes |
|------|----------|-------|
| Event metadata | `event_type`, `severity`, `timestamp` | No bodies |
| Integrity summary | chunk hash, manifest diff | Prefix/summary only |
| PII stats | count of masked spans | Not the text |
| Perf metrics | `duration_ms`, `bytes_processed` | Aggregated |
| Threat category | `finding_type`, severity | No hostnames / keys / detailed port lists |

## Never send

| Type | Why |
|------|-----|
| Full prompts | PII |
| Model file bytes | sovereignty |
| Raw audit JSON | might contain secrets |
| API keys / tokens | obvious |
| Port scans with hostnames | too much recon detail |
| Paths that identify the user | privacy |

## Redaction

Cloud payloads only via `contracts.policies.redact_for_cloud()`. `bus.py` doesn't invent its own dicts.

## When I add a DTO field

Update this file + the forbidden-field tests in `tests/contracts/`.
