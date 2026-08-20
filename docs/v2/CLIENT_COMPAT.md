# Client compatibility matrix (CS301 Option 3)

**Last updated:** 18 Aug 2026  
**Evidence bar:** claim a path only after a network capture shows sanitized upstream bytes.

| Client | Path | Status | How to point at LakanVault | Residual risk |
|--------|------|--------|----------------------------|---------------|
| Continue.dev | Chat Completions | Sprint 1 target | `provider: openai`, `apiBase: http://127.0.0.1:8080/v1`, `useResponsesApi: false` | Autocomplete / embeddings / `/v1/responses` not proxied |
| Claude Code | Messages API | Sprint 2 | `ANTHROPIC_BASE_URL=http://127.0.0.1:8080` (after Anthropic codec) | OAuth/header forwarding |
| Cursor Chat/Ask | Custom OpenAI-compatible URL | Experimental | Product docs mention override; loopback/HTTP/Agent not specified | Requests may still go through Cursor backend |
| Cursor Agent | Custom base URL | Unclaimed | Not documented | Tool-calling may bypass proxy |
| Cursor Tab | — | Unclaimed | Tab uses Cursor built-in models | Permanent blind spot for API proxy |
| Cursor MCP | Tool I/O via shim | Sprint 1 | MCP config → `lakanvault-mcp` wrapping a child server | Builtin file read skips tools |

Continue example (YAML):

```yaml
models:
  - name: lakanvault-openai
    provider: openai
    model: gpt-4o-mini
    apiBase: http://127.0.0.1:8080/v1
    apiKey: ${{ secrets.OPENAI_API_KEY }}
    useResponsesApi: false
    roles:
      - chat
```
