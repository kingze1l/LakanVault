"""Metadata-only classification of chat payloads. Never echo prompt text."""
from __future__ import annotations

import asyncio

import httpx
from fastapi import FastAPI
from httpx import ASGITransport

from lakanvault.app.proxy_routes import internal_router
from lakanvault.infrastructure.token_vault import InMemoryTokenVault
from lakanvault.orchestration.proxy_gateway import ProxyGateway

EMAIL = "jane.doe@example.com"
API_KEY = "sk-abcdefghijklmnopqrstuvwxyz1234567890"


class _ClientApp:
    def __init__(self, app, client: tuple[str, int] | None) -> None:
        self._app = app
        self._client = client

    async def __call__(self, scope, receive, send):
        scope = dict(scope)
        scope["client"] = self._client
        await self._app(scope, receive, send)


def _app(*, max_body: int = 1_048_576) -> FastAPI:
    app = FastAPI()
    app.include_router(internal_router)
    app.state.proxy_gateway = ProxyGateway(InMemoryTokenVault(), None, strict=True)
    app.state.proxy_max_body = max_body
    return app


async def _post(
    payload: dict,
    *,
    client: tuple[str, int] | None = ("127.0.0.1", 9),
    max_body: int = 1_048_576,
):
    app = _ClientApp(_app(max_body=max_body), client)
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://lakanvault.test") as http:
        return await http.post("/internal/v1/classify-chat-payload", json=payload)


def test_classify_chat_payload_is_metadata_only() -> None:
    async def run():
        resp = await _post(
            {"messages": [{"role": "user", "content": f"Contact {EMAIL} about {API_KEY}"}]}
        )
        raw = resp.content.decode()
        assert resp.status_code == 200
        body = resp.json()
        assert body["action"] == "block"
        assert "orchestrated_prompt" not in body
        assert EMAIL not in raw
        assert "sk-" not in raw

    asyncio.run(run())


def test_remote_client_is_rejected() -> None:
    async def run():
        resp = await _post(
            {"messages": [{"role": "user", "content": "hello"}]},
            client=("203.0.113.1", 12345),
        )
        assert resp.status_code == 403

    asyncio.run(run())


def test_loopback_client_is_allowed() -> None:
    async def run():
        resp = await _post({"messages": [{"role": "user", "content": "hello there"}]})
        assert resp.status_code == 200
        assert resp.json()["action"] == "allow"

    asyncio.run(run())


def test_oversized_content_length_is_rejected() -> None:
    async def run():
        resp = await _post(
            {"messages": [{"role": "user", "content": "this body exceeds the configured cap"}]},
            max_body=16,
        )
        assert resp.status_code == 413

    asyncio.run(run())


def test_extracted_text_over_cap_is_rejected() -> None:
    async def run():
        resp = await _post({"messages": [{"role": "user", "content": "a" * 100_001}]})
        assert resp.status_code == 413

    asyncio.run(run())


def test_sanitize_rejects_remote_client() -> None:
    async def run():
        app = _ClientApp(_app(), ("203.0.113.1", 9))
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://lakanvault.test"
        ) as http:
            resp = await http.post(
                "/internal/v1/sanitize",
                json={"text": "hello", "request_id": "r1"},
            )
        assert resp.status_code == 403

    asyncio.run(run())
