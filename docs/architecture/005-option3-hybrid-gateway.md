# 005 — Option 3 hybrid dual-gateway (CS301)

**Status:** Approved for CS301 on branch `CS301`  
**Date:** 18 Aug 2026  
**Does not replace:** CS205 pipeline, MCP classify/audit tools, clipboard/tray Path A.

## Claim (testable)

Coverage applies only to traffic **demonstrably routed** through the LakanVault MCP shim or the local API proxy. Builtin IDE file reads, Tab/autocomplete, unsupported endpoints, attachments, and clients that bypass the configured gateway remain residual paths.

Do not claim “100% DLP” or “universal Cursor support.”

## Topology

One FastAPI daemon on `127.0.0.1:8080`:

- Existing `/` and `/api/*` stay as the demo UI.
- Isolated routers add `/v1/chat/completions`, `/v1/models`, and an internal sanitize API.
- A separate console MCP shim wraps a child MCP server over stdio and asks the daemon to sanitize tool results. The shim never owns the token vault.

## Token map (not a credential vault)

Session mappings live in **in-memory SQLite** (`:memory:`) owned by the daemon process. Raw secrets never reach disk. This is a reversible anonymization map, not an API-key password manager. Provider keys stay BYOK (client `Authorization` forwarded to an allowlisted upstream).

## Strict mode (default for external providers)

- Detector failure, malformed payloads, and unsupported image/audio/file blocks → **block** (no upstream call).
- Local Ollama may use an explicit availability policy in config.
- Secret/Confidential findings → **block**. Internal PII → **redact** with opaque tokens.

## Client matrix (Sprint 1)

| Client | Documented hook | Sprint 1 claim |
|--------|-----------------|----------------|
| Continue.dev | `apiBase` + `useResponsesApi: false` | Intended; verify with capture |
| Claude Code | `ANTHROPIC_BASE_URL` | Deferred to Sprint 2 |
| Cursor Chat/Ask | OpenAI-compatible override acknowledged, contract incomplete | Experimental spike only |
| Cursor Agent | Not documented | Unclaimed |
| Cursor Tab | Built-in models | Unclaimed |

## Streaming restore

Restore only complete opaque tokens in assistant text, using a bounded sliding tail. Never restore into `tool_calls[].function.arguments`. Restore only tokens minted or already present on **this** request.

## Image OCR (Sprint 3)

Local OCR of inline data-URL images. Remote `https://` image URLs are uninspected → strict block. Sensitive OCR text → **block the request** (pixel redaction is later).
