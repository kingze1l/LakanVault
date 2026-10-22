# Client compatibility matrix (CS301 Option 3)

**Last updated:** 22 Oct 2026  
**Evidence bar:** claim a path only after a network capture or protocol test shows sanitized / classified bytes.

| Client | Path | Status | How to point at LakanVault | Residual risk |
|--------|------|--------|----------------------------|---------------|
| Continue.dev (VS Code) | Chat Completions | Proxy tested; Continue capture pending | `provider: openai`, `apiBase: http://127.0.0.1:8080/v1`, `useResponsesApi: false` | Autocomplete / embeddings / `/v1/responses` not proxied |
| GitHub Copilot (VS Code) | — | Not possible | No base-URL override | Permanent blind spot |
| Claude Desktop / Claude Code | MCP tools | Untested (standard stdio MCP) | Same server as Cursor MCP row; see root README §3.3 | Agent may skip tools |
| Claude Code | Messages API | Sprint 2 | `ANTHROPIC_BASE_URL=http://127.0.0.1:8080` (after Anthropic codec) | OAuth/header forwarding |
| Cursor Chat/Ask | Custom OpenAI-compatible URL | Experimental | Product docs mention override; loopback/HTTP/Agent not specified | Requests may still go through Cursor backend |
| Cursor Agent | Custom base URL | Unclaimed | Not documented | Tool-calling may bypass proxy |
| Cursor Tab | — | Unclaimed | Tab uses Cursor built-in models | Permanent blind spot for API proxy |
| Cursor MCP (native) | Classify / audit tools | Verified (dev path) | Copy `docs/cs301/examples/cursor-mcp.json` → `.cursor/mcp.json`; see [`CURSOR_SETUP.md`](../cs301/CURSOR_SETUP.md) | Agent may skip tools; not the final cloud prompt |
| Cursor MCP (shim) | Child tool **results** | Sprint 1 | `lakanvault-mcp` wrapping a child server + daemon sanitize | Outbound tool args unchanged; builtin file read skips tools |

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
