"""The paste-check page is served and points at the metadata classifier."""
from __future__ import annotations

import asyncio

import httpx
from httpx import ASGITransport

from lakanvault.app.server import app


def test_shim_page_is_served() -> None:
    async def run() -> None:
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://lakanvault.test",
        ) as client:
            response = await client.get("/static/shim.html")
        assert response.status_code == 200
        text = response.text
        assert "/internal/v1/classify-chat-payload" in text
        assert "does not watch the VS Code editor" in text

    asyncio.run(run())
