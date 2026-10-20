"""Subprocess integration: launch stdio server the same way Cursor will."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from lakanvault.contracts.mcp import FORBIDDEN_MCP_RESPONSE_FIELDS

API_KEY = "sk-abcdefghijklmnopqrstuvwxyz1234567890"
REPO = Path(__file__).resolve().parents[2]
CONFIG = REPO / "config"


def _server_params() -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable,
        args=[
            "-m",
            "lakanvault.mcp.stdio_server",
            "--config-dir",
            str(CONFIG),
        ],
        cwd=str(REPO),
        env={"PYTHONPATH": str(REPO / "src"), "PYTHONUTF8": "1"},
    )


def test_subprocess_lists_and_classifies() -> None:
    async def run() -> None:
        async with stdio_client(_server_params()) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                listed = await session.list_tools()
                names = {t.name for t in listed.tools}
                assert names == {"lakanvault_classify", "lakanvault_audit_recent"}

                clean = await session.call_tool("lakanvault_classify", {"text": "hello world"})
                clean_text = next(b.text for b in clean.content if hasattr(b, "text"))
                clean_payload = json.loads(clean_text)
                assert clean_payload["action"] == "allow"

                blocked = await session.call_tool(
                    "lakanvault_classify",
                    {"text": f"key {API_KEY}"},
                )
                blocked_text = next(b.text for b in blocked.content if hasattr(b, "text"))
                assert "sk-" not in blocked_text
                blocked_payload = json.loads(blocked_text)
                assert blocked_payload["action"] == "block"
                assert FORBIDDEN_MCP_RESPONSE_FIELDS.isdisjoint(blocked_payload)

                audit = await session.call_tool("lakanvault_audit_recent", {"limit": 3})
                audit_text = next(b.text for b in audit.content if hasattr(b, "text"))
                audit_payload = json.loads(audit_text)
                assert "entries" in audit_payload
                assert "prompt_text" not in audit_text

    asyncio.run(run())
