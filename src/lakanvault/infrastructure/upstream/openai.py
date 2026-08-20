"""OpenAI Chat Completions upstream — verified TLS, allowlisted origin, BYOK headers only."""
from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from typing import Any

import httpx

from lakanvault.shared.url_policy import assert_allowed_upstream

_FORWARD = frozenset({
    "authorization",
    "content-type",
    "openai-organization",
    "openai-project",
    "openai-beta",
})
_DROP = frozenset({
    "host",
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "content-length",
    "cookie",
    "x-forwarded-for",
    "x-forwarded-host",
    "x-forwarded-proto",
})


def filter_upstream_headers(headers: Mapping[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in headers.items():
        low = key.lower()
        if low in _DROP:
            continue
        if low in _FORWARD:
            out[key] = value
    return out


class OpenAIUpstream:
    def __init__(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        allowlist: list[str],
        timeout_seconds: float = 120.0,
    ) -> None:
        self._client = client
        self._base = assert_allowed_upstream(base_url, allowlist)
        self._timeout = timeout_seconds

    async def chat_completions(
        self,
        payload: dict[str, Any],
        headers: Mapping[str, str],
    ) -> httpx.Response:
        url = f"{self._base}/v1/chat/completions"
        fwd = filter_upstream_headers(headers)
        fwd.setdefault("Content-Type", "application/json")
        if payload.get("stream"):
            request = self._client.build_request(
                "POST",
                url,
                json=payload,
                headers=fwd,
                timeout=self._timeout,
            )
            return await self._client.send(request, stream=True)
        return await self._client.post(
            url,
            json=payload,
            headers=fwd,
            timeout=self._timeout,
        )

    async def list_models(self, headers: Mapping[str, str]) -> httpx.Response:
        url = f"{self._base}/v1/models"
        fwd = filter_upstream_headers(headers)
        return await self._client.get(url, headers=fwd, timeout=min(self._timeout, 30.0))

    async def aiter_bytes(self, response: httpx.Response) -> AsyncIterator[bytes]:
        try:
            async for chunk in response.aiter_bytes():
                yield chunk
        finally:
            await response.aclose()
