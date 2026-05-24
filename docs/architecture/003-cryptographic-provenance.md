# 003 — Crypto / provenance (my rules)

Phase 1a — anything from outside gets verified locally before I trust it.

## What I verify offline

| Thing | How I check | If it fails |
|-------|-------------|-------------|
| Model manifest baseline | SHA-256 vs trusted baseline (USB / tutor JSON) | Fail closed — don't mark verified |
| Enrichment pack from cloud | Ed25519 (or similar) vs pinned public key | Reject — don't apply |
| Cloud telemetry in | Field allowlist from `data-classification.md` | Drop it — log rejection |

## Where trust comes from

Baselines and signing keys come **out-of-band** (me or Rouwa), not from cloud. Cloud is never the source of truth for model hashes.

## What I won't accept back from cloud

- Executable code / scripts
- Unverified blobs merged into prompts or model paths
- Full model files or raw audit dumps

## Apply rule

`local_core/adapters/` only applies signed stuff after local verify. Fail = reject. No "warn and continue."
