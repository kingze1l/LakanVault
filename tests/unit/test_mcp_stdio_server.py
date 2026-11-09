"""Native MCP stdio server — tool discovery and classify/audit via SDK."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from mcp.client.session import ClientSession
from mcp.shared.memory import create_client_server_memory_streams

from lakanvault.contracts.mcp import FORBIDDEN_MCP_RESPONSE_FIELDS
from lakanvault.mcp.stdio_server import build_server, resolve_config_dir

# Joan's gitleaks-style OpenAI rule needs a real-shaped key; URI creds always match.
SECRET_PROMPT = "connect with postgres://admin:SuperSecret99@db.example.com/app"


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


def test_list_tools_exposes_classify_protect_restore_and_audit() -> None:
    server = build_server(_repo_config())

    async def body(session):
        listed = await session.list_tools()
        names = {t.name for t in listed.tools}
        assert names == {
            "lakanvault_classify",
            "lakanvault_audit_recent",
            "lakanvault_protect",
            "lakanvault_restore",
        }

    asyncio.run(_with_session(server, body))


def test_classify_tool_blocks_secret_without_echo() -> None:
    server = build_server(_repo_config())

    async def body(session):
        result = await session.call_tool(
            "lakanvault_classify",
            {"text": SECRET_PROMPT},
        )
        assert result.is_error is not True
        text_parts = [
            block.text
            for block in result.content
            if getattr(block, "type", None) == "text" and hasattr(block, "text")
        ]
        joined = "\n".join(text_parts)
        assert "SuperSecret99" not in joined
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


def test_protect_then_restore_via_mcp(monkeypatch) -> None:
    from lakanvault.local_core.findings import Finding, Tier

    email = "jane.doe@example.com"

    def fake_pii(text: str, layers=("names",)):
        start = text.find(email)
        if start < 0:
            return []
        return [
            Finding(
                "EMAIL_ADDRESS",
                email,
                start,
                start + len(email),
                0.95,
                Tier.PII_MODERATE,
                "presidio",
            )
        ]

    monkeypatch.setattr("lakanvault.local_core.scan.detect_pii", fake_pii)
    server = build_server(_repo_config())
    prompt = f"please email {email} about the meeting"

    async def body(session):
        protected = await session.call_tool(
            "lakanvault_protect",
            {"text": prompt, "session_id": "mcp1", "llm": "never"},
        )
        assert protected.is_error is not True
        text = next(b.text for b in protected.content if hasattr(b, "text"))
        payload = json.loads(text)
        assert payload["session_id"] == "mcp1"
        assert email not in payload["sanitized"]
        assert payload["sanitized"]
        assert email not in text
        assert FORBIDDEN_MCP_RESPONSE_FIELDS.isdisjoint(payload)

        restored = await session.call_tool(
            "lakanvault_restore",
            {"text": payload["sanitized"], "session_id": "mcp1"},
        )
        assert restored.is_error is not True
        rtext = next(b.text for b in restored.content if hasattr(b, "text"))
        rpayload = json.loads(rtext)
        assert email in rpayload["text"]

    asyncio.run(_with_session(server, body))
