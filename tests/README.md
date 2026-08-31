# Tests

```powershell
python -m pytest tests/ -q
```

## Layout

| Folder | Purpose | Examples |
|--------|---------|----------|
| `contracts/` | DTO safety, boundary rules, config contracts | `test_proxy_contracts.py`, `test_boundaries.py` |
| `unit/` | Module behavior — DLP, proxy, vault, MCP, SSE | `test_openai_proxy.py`, `test_dlp_transformer.py` |

## CS301 / Option 3 coverage

| Area | Test file |
|------|-----------|
| Token vault | `test_token_vault.py` |
| Unified DLP | `test_dlp_transformer.py` |
| OpenAI proxy | `test_openai_proxy.py`, `test_openai_payload.py` |
| SSE streaming | `test_sse.py` |
| MCP shim | `test_mcp_stdio_proxy.py` |
| Image OCR scaffold | `test_image_inspector.py` |
| Frozen paths | `test_paths.py`, `test_packaging.py` |

Always run `python scripts/verify_boundaries.py` before commit.
