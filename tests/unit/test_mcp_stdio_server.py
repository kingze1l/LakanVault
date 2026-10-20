"""Native MCP stdio server — tool discovery and classify/audit via SDK."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from mcp.client.session import ClientSession
from mcp.shared.memory import create_client_server_memory_streams

from lakanvault.contracts.mcp import FORBIDDEN_MCP_RESPONSE_FIELDS
from lakanvault.mcp.stdio_server import build_server, resolve_config_dir

API_KEY = "sk-abcdefghijklmnopqrstuvwxyz1234567890"


def _repo_config() -> Path:
    return Path(__file__).resolve().parents[2] / "config"


async def _with_session(server, coro):
    lowlevel = server._lowlevel_server
    async with create_client_server_memory_streams() as (client_streams, server_streams):
        server_task = asyncio.create_task(
            lowlevel.run(
                server_streams[0],
                server_streams[1],
                lowlevel.create_initialization_options(),
            )
        )
        try:
            async with ClientSession(*client_streams) as session:
                await session.initialize()
                return await coro(session)
        finally:
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass


def test_list_tools_exposes_classify_and_audit() -> None:
    server = build_server(_repo_config())

    async def body(session):
        listed = await session.list_tools()
        names = {t.name for t in listed.tools}
        assert names == {"lakanvault_classify", "lakanvault_audit_recent"}

    asyncio.run(_with_session(server, body))


def test_classify_tool_blocks_secret_without_echo() -> None:
    server = build_server(_repo_config())

    async def body(session):
        result = await session.call_tool(
            "lakanvault_classify",
            {"text": f"my key is {API_KEY}"},
        )
        assert result.is_error is not True
        text_parts = [
            block.text
            for block in result.content
            if getattr(block, "type", None) == "text" and hasattr(block, "text")
        ]
        joined = "\n".join(text_parts)
        assert "sk-" not in joined
        payload = json.loads(joined)
        assert payload["action"] == "block"
        assert FORBIDDEN_MCP_RESPONSE_FIELDS.isdisjoint(payload)

    asyncio.run(_with_session(server, body))


def test_classify_clean_text_allows() -> None:
    server = build_server(_repo_config())

    async def body(session):
        result = await session.call_tool(
            "lakanvault_classify",
            {"text": "hello world"},
        )
        text = next(b.text for b in result.content if hasattr(b, "text"))
        payload = json.loads(text)
        assert payload["action"] == "allow"
        assert payload["tier"] == "public"

    asyncio.run(_with_session(server, body))


def test_resolve_config_dir_prefers_explicit(tmp_path: Path) -> None:
    assert resolve_config_dir(tmp_path) == tmp_path
