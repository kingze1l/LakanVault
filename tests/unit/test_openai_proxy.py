"""OpenAI reverse-proxy: fake upstream, no raw PII/secrets outbound, restore rules."""
from __future__ import annotations

import asyncio
import json
from time import monotonic

import httpx
from fastapi import FastAPI
from httpx import ASGITransport

from lakanvault.app.proxy_routes import internal_router, router
from lakanvault.eval.metrics import latency_summary
from lakanvault.infrastructure.token_vault import InMemoryTokenVault
from lakanvault.infrastructure.upstream.openai import OpenAIUpstream, filter_upstream_headers
from lakanvault.orchestration.proxy_gateway import ProxyGateway

EMAIL = "jane.doe@example.com"
API_KEY = "sk-abcdefghijklmnopqrstuvwxyz1234567890"
ALLOWLIST = ["https://api.openai.com"]


def test_filter_drops_hop_by_hop_and_host() -> None:
    out = filter_upstream_headers({
        "Host": "evil.example",
        "Authorization": "Bearer sk-live",
        "X-Forwarded-For": "1.2.3.4",
        "Content-Length": "99",
        "Cookie": "session=1",
        "OpenAI-Organization": "org",
        "Content-Type": "application/json",
    })
    keys = {k.lower() for k in out}
    assert "host" not in keys
    assert "x-forwarded-for" not in keys
    assert "content-length" not in keys
    assert "cookie" not in keys
    assert "authorization" in keys
    assert "openai-organization" in keys


async def _call(handler, method: str, path: str, **kwargs):
    captured: list[httpx.Request] = []

    def wrap(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return handler(request)

    vault = InMemoryTokenVault()
    async with httpx.AsyncClient(transport=httpx.MockTransport(wrap)) as upstream_client:
        upstream = OpenAIUpstream(upstream_client, "https://api.openai.com", ALLOWLIST)
        app = FastAPI()
        app.include_router(router)
        app.include_router(internal_router)
        app.state.proxy_gateway = ProxyGateway(vault, upstream, strict=True, allow_images=False)
        app.state.proxy_max_body = 1_048_576
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://lakanvault.test",
        ) as client:
            resp = await getattr(client, method)(path, **kwargs)
            body = resp.content
            return resp, body, captured, vault


def test_nonstream_redacts_email_before_upstream() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": body["messages"][0]["content"],
                            "tool_calls": [
                                {"function": {"arguments": body["messages"][0]["content"]}}
                            ],
                        }
                    }
                ]
            },
        )

    async def run():
        resp, raw, captured, vault = await _call(
            handler,
            "post",
            "/v1/chat/completions",
            json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": f"Contact {EMAIL}"}]},
            headers={"Authorization": "Bearer sk-test", "X-Forwarded-For": "8.8.8.8"},
        )
        try:
            assert resp.status_code == 200
            assert captured
            outbound = captured[0].content.decode()
            assert EMAIL not in outbound
            assert "x-forwarded-for" not in {k.lower() for k in captured[0].headers}
            data = resp.json()
            assert EMAIL in data["choices"][0]["message"]["content"]
            tool_args = data["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"]
            assert EMAIL not in tool_args
        finally:
            vault.close()

    asyncio.run(run())


def test_api_key_block_makes_zero_upstream_calls() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": []})

    async def run():
        resp, raw, captured, vault = await _call(
            handler,
            "post",
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": f"key {API_KEY}"}]},
        )
        try:
            assert resp.status_code == 403
            assert captured == []
            assert b"sk-" not in raw
        finally:
            vault.close()

    asyncio.run(run())


def test_strict_image_is_blocked() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    async def run():
        resp, _raw, captured, vault = await _call(
            handler,
            "post",
            "/v1/chat/completions",
            json={
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "see"},
                            {"type": "image_url", "image_url": {"url": "https://example.com/x.png"}},
                        ],
                    }
                ]
            },
        )
        try:
            assert resp.status_code == 403
            assert captured == []
        finally:
            vault.close()

    asyncio.run(run())


def test_internal_sanitize_redacts() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    async def run():
        resp, _raw, _captured, vault = await _call(
            handler,
            "post",
            "/internal/v1/sanitize",
            json={"text": f"mail {EMAIL}", "request_id": "mcp1"},
        )
        try:
            body = resp.json()
            assert EMAIL not in body["text"]
            assert "authorization" not in body
        finally:
            vault.close()

    asyncio.run(run())


def test_models_passthrough() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).endswith("/v1/models")
        return httpx.Response(200, json={"data": [{"id": "gpt-4o-mini"}]})

    async def run():
        resp, _raw, _captured, vault = await _call(
            handler,
            "get",
            "/v1/models",
            headers={"Authorization": "Bearer sk-test"},
        )
        try:
            assert resp.status_code == 200
            assert resp.json()["data"][0]["id"] == "gpt-4o-mini"
        finally:
            vault.close()

    asyncio.run(run())


def test_cross_request_token_not_restored() -> None:
    async def run():
        vault = InMemoryTokenVault()
        other = vault.mint("LEAK", request_id="r-other", ttl_seconds=60)

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"choices": [{"message": {"content": other}}]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as upstream_client:
            upstream = OpenAIUpstream(upstream_client, "https://api.openai.com", ALLOWLIST)
            gw = ProxyGateway(vault, upstream)
            outcome = await gw.chat_completions(
                {"messages": [{"role": "user", "content": "hello there"}]},
                {},
                request_id="r-this",
            )
        assert outcome.body["choices"][0]["message"]["content"] == other
        assert "LEAK" not in json.dumps(outcome.body)
        vault.close()

    asyncio.run(run())


def test_fifty_concurrent_lifecycles() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        content = body["messages"][0]["content"]
        assert EMAIL not in content
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": f"echo {content}"}}]},
        )

    async def run():
        vault = InMemoryTokenVault()
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            upstream = OpenAIUpstream(client, "https://api.openai.com", ALLOWLIST)
            gw = ProxyGateway(vault, upstream)

            async def one(i: int) -> float:
                t0 = monotonic()
                outcome = await gw.chat_completions(
                    {"messages": [{"role": "user", "content": f"Contact {EMAIL} #{i}"}]},
                    {"authorization": "Bearer sk-test"},
                    request_id=f"r{i}",
                )
                assert outcome.status_code == 200
                assert EMAIL in outcome.body["choices"][0]["message"]["content"]
                return (monotonic() - t0) * 1000

            samples = await asyncio.gather(*[one(i) for i in range(50)])
        summary = latency_summary(list(samples))
        assert summary["n"] == 50
        assert summary["p95_ms"] > 0
        vault.close()

    asyncio.run(run())


def test_stream_restores_split_token_and_done() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        text = body["messages"][0]["content"]
        assert EMAIL not in text
        mid = max(1, len(text) // 2)
        sse = (
            f'data: {{"choices":[{{"delta":{{"content":{json.dumps(text[:mid])}}}}}]}}\n\n'
            f'data: {{"choices":[{{"delta":{{"content":{json.dumps(text[mid:])}}}}}]}}\n\n'
            "data: [DONE]\n\n"
        )
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=sse.encode(),
        )

    async def run():
        resp, raw, _captured, vault = await _call(
            handler,
            "post",
            "/v1/chat/completions",
            json={"stream": True, "messages": [{"role": "user", "content": f"Contact {EMAIL}"}]},
        )
        try:
            text = raw.decode()
            assert EMAIL in text
            assert "[DONE]" in text
        finally:
            vault.close()

    asyncio.run(run())


def test_cancel_cleans_request_state() -> None:
    vault = InMemoryTokenVault()

    class Slow:
        async def chat_completions(self, payload, headers):
            started.set()
            await asyncio.sleep(30)
            return httpx.Response(200, json={})

    gw = ProxyGateway(vault, Slow())  # type: ignore[arg-type]
    started = asyncio.Event()

    async def consume() -> None:
        async for _ in gw.iter_sse(
            {"messages": [{"role": "user", "content": f"Contact {EMAIL}"}]},
            {},
            request_id="cancel-me",
        ):
            pass

    async def run() -> None:
        task = asyncio.create_task(consume())
        await started.wait()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(run())
    assert vault.delete_request("cancel-me") == 0
    vault.close()
