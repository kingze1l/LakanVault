"""Local LLM adapter — OpenAI-compatible chat on localhost only."""
from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Iterator

from lakanvault.shared.url_policy import assert_localhost_url

logger = logging.getLogger(__name__)

MODELS_CACHE_TTL = 30.0


@dataclass
class ChatCompletionResult:
    content: str
    model_used: str
    provider_url: str
    latency_ms: float = 0.0


@dataclass
class StreamChunk:
    delta: str = ""
    model_used: str = ""
    provider_url: str = ""
    done: bool = False
    full_content: str = ""


class LocalLLMClient:
    def __init__(
        self,
        base_url: str = "http://localhost:1234",
        model: str = "",
        timeout_seconds: float = 120,
        temperature: float = 0.7,
        max_tokens: int = 512,
        stream: bool = True,
    ):
        self._base_url = assert_localhost_url(base_url)
        self._model = model
        self._timeout = timeout_seconds
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._stream = stream
        self._models_cache: tuple[float, list[str]] | None = None

    @property
    def base_url(self) -> str:
        return self._base_url

    def configure(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stream: bool | None = None,
    ) -> None:
        if base_url is not None:
            self._base_url = assert_localhost_url(base_url)
            self._models_cache = None
        if model is not None:
            self._model = model
        if timeout_seconds is not None:
            self._timeout = timeout_seconds
        if temperature is not None:
            self._temperature = temperature
        if max_tokens is not None:
            self._max_tokens = max_tokens
        if stream is not None:
            self._stream = stream

    def _resolve_model(self, model: str | None, base_url: str | None) -> str:
        requested = (model or self._model or "").strip()
        if requested and requested != "local-model":
            return requested
        models = self.list_models(base_url=base_url)
        if models:
            return models[0]
        return requested or "local-model"

    def list_models(self, base_url: str | None = None, *, force: bool = False) -> list[str]:
        root = assert_localhost_url(base_url) if base_url else self._base_url
        now = time.monotonic()
        if (
            not force
            and base_url is None
            and self._models_cache is not None
            and now - self._models_cache[0] < MODELS_CACHE_TTL
        ):
            return self._models_cache[1]

        url = f"{root}/v1/models"
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                data = json.loads(resp.read().decode())
            models = [m["id"] for m in data.get("data", [])]
            if base_url is None:
                self._models_cache = (now, models)
            return models
        except Exception as exc:
            logger.warning("Local LLM not reachable at %s: %s", url, exc)
            return []

    def _build_payload(
        self,
        prompt: str,
        model: str,
        *,
        stream: bool,
        temperature: float | None,
        max_tokens: int | None,
    ) -> dict:
        return {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature if temperature is not None else self._temperature,
            "max_tokens": max_tokens if max_tokens is not None else self._max_tokens,
            "stream": stream,
        }

    def chat(
        self,
        prompt: str,
        model: str | None = None,
        base_url: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stream: bool | None = None,
    ) -> ChatCompletionResult:
        root = assert_localhost_url(base_url) if base_url else self._base_url
        use_stream = self._stream if stream is None else stream
        resolved_model = self._resolve_model(model, base_url)

        if use_stream:
            parts: list[str] = []
            model_used = resolved_model
            start = time.monotonic()
            for chunk in self.chat_stream(
                prompt,
                model=resolved_model,
                base_url=root,
                temperature=temperature,
                max_tokens=max_tokens,
            ):
                if chunk.delta:
                    parts.append(chunk.delta)
                if chunk.model_used:
                    model_used = chunk.model_used
                if chunk.done:
                    return ChatCompletionResult(
                        content=chunk.full_content or "".join(parts),
                        model_used=model_used,
                        provider_url=root,
                        latency_ms=round((time.monotonic() - start) * 1000, 1),
                    )
            return ChatCompletionResult(
                content="".join(parts),
                model_used=model_used,
                provider_url=root,
                latency_ms=round((time.monotonic() - start) * 1000, 1),
            )

        url = f"{root}/v1/chat/completions"
        payload = self._build_payload(
            prompt, resolved_model, stream=False,
            temperature=temperature, max_tokens=max_tokens,
        )
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        start = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                data = json.loads(resp.read().decode())
            latency_ms = round((time.monotonic() - start) * 1000, 1)
            model_used = data.get("model") or resolved_model
            content = data["choices"][0]["message"]["content"]
            return ChatCompletionResult(
                content=content,
                model_used=model_used,
                provider_url=root,
                latency_ms=latency_ms,
            )
        except urllib.error.URLError as exc:
            raise ConnectionError(
                f"Cannot reach local LLM at {url}. Is the server running on localhost?"
            ) from exc
        except (KeyError, IndexError) as exc:
            raise ValueError(f"Unexpected local LLM response shape: {exc}") from exc

    def chat_stream(
        self,
        prompt: str,
        model: str | None = None,
        base_url: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> Iterator[StreamChunk]:
        root = assert_localhost_url(base_url) if base_url else self._base_url
        resolved_model = self._resolve_model(model, base_url)
        url = f"{root}/v1/chat/completions"
        payload = self._build_payload(
            prompt, resolved_model, stream=True,
            temperature=temperature, max_tokens=max_tokens,
        )
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        parts: list[str] = []
        model_used = resolved_model
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                for raw_line in resp:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    if data.get("model"):
                        model_used = data["model"]
                    choices = data.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {}).get("content") or ""
                    if delta:
                        parts.append(delta)
                        yield StreamChunk(
                            delta=delta,
                            model_used=model_used,
                            provider_url=root,
                        )
            full = "".join(parts)
            yield StreamChunk(
                done=True,
                full_content=full,
                model_used=model_used,
                provider_url=root,
            )
        except urllib.error.URLError as exc:
            raise ConnectionError(
                f"Cannot reach local LLM at {url}. Is the server running on localhost?"
            ) from exc
