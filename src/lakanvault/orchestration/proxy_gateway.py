"""Proxy request lifecycle — sanitize, optional upstream, restore, audit metadata."""
from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from typing import Any

from lakanvault.contracts.mcp import DataTier, PolicyAction
from lakanvault.contracts.proxy import ProxyAuditRecord, TokenVaultPort, TransformResult
from lakanvault.infrastructure.upstream.openai import OpenAIUpstream
from lakanvault.infrastructure.upstream.sse import SlidingTokenRestorer, parse_sse_chunk, restore_sse_data_json, serialize_sse
from lakanvault.local_core.dlp.openai_payload import (
    UninspectedPayloadError,
    collect_existing_tokens,
    restore_chat_response,
    sanitize_chat_request,
)
from lakanvault.local_core.dlp.transformer import transform_text
from lakanvault.local_core.privacy.opaque_anonymizer import OpaqueAnonymizer

logger = logging.getLogger(__name__)


@dataclass
class ProxyOutcome:
    blocked: bool
    status_code: int
    body: dict[str, Any]
    audit: ProxyAuditRecord
    allow_mapping: dict[str, str]
    sanitized_payload: dict[str, Any] | None
    request_id: str


class ProxyGateway:
    def __init__(
        self,
        vault: TokenVaultPort,
        upstream: OpenAIUpstream | None,
        *,
        strict: bool = True,
        ttl_seconds: float = 3600.0,
        allow_images: bool = False,
        image_inspector=None,
    ) -> None:
        self._vault = vault
        self._upstream = upstream
        self._strict = strict
        self._ttl = ttl_seconds
        self._allow_images = allow_images
        if allow_images and image_inspector is None:
            from lakanvault.local_core.dlp.image_inspector import ImageInspector

            image_inspector = ImageInspector()
        self._image_inspector = image_inspector

    def sanitize_text(self, text: str, request_id: str) -> TransformResult:
        return transform_text(
            text, self._vault, request_id=request_id, ttl_seconds=self._ttl, fail_closed=True
        )

    def _prepare(self, payload: dict[str, Any], request_id: str) -> ProxyOutcome:
        def _tx(text: str) -> TransformResult:
            return self.sanitize_text(text, request_id)

        try:
            if self._image_inspector is not None:
                img = self._image_inspector.inspect(payload, _tx, strict=self._strict)
                if img.blocked:
                    audit = ProxyAuditRecord(
                        request_id=request_id,
                        overall_status="BLOCK",
                        action=PolicyAction.BLOCK,
                        blocked=True,
                        reason=img.reason,
                        image_inspected=img.inspected,
                    )
                    return ProxyOutcome(
                        True, 403,
                        {"error": {"message": img.reason, "type": "lakanvault_block"}},
                        audit, {}, None, request_id,
                    )
            sanitized, findings, uninspected = sanitize_chat_request(
                payload,
                _tx,
                strict=self._strict,
                allow_images=self._allow_images or self._image_inspector is not None,
            )
        except UninspectedPayloadError as exc:
            audit = ProxyAuditRecord(
                request_id=request_id,
                overall_status="BLOCK",
                action=PolicyAction.BLOCK,
                blocked=True,
                reason=str(exc),
                uninspected_blocks=1,
            )
            return ProxyOutcome(
                True, 403,
                {"error": {"message": "unsupported content blocked", "type": "lakanvault_block"}},
                audit, {}, None, request_id,
            )

        blocked = next((f for f in findings if f.blocked), None)
        if blocked:
            audit = ProxyAuditRecord(
                request_id=request_id,
                overall_status="BLOCK",
                tier=blocked.tier,
                action=blocked.action,
                pii_span_count=blocked.pii_span_count,
                entity_types=list(blocked.entity_types),
                blocked=True,
                reason=blocked.reason,
                uninspected_blocks=uninspected,
            )
            return ProxyOutcome(
                True, 403,
                {"error": {"message": blocked.reason, "type": "lakanvault_block"}},
                audit, {}, None, request_id,
            )

        allow = collect_existing_tokens(sanitized, OpaqueAnonymizer.find_tokens)
        for finding in findings:
            for token in finding.tokens_minted:
                allow.add(token)
        mapping = allow.mapping_view(self._vault.get)
        top = findings[0] if findings else TransformResult()
        audit = ProxyAuditRecord(
            request_id=request_id,
            overall_status="PASS",
            tier=top.tier,
            action=top.action,
            pii_span_count=sum(f.pii_span_count for f in findings),
            entity_types=sorted({e for f in findings for e in f.entity_types}),
            blocked=False,
            reason=top.reason,
            stream=bool(payload.get("stream")),
            uninspected_blocks=uninspected,
        )
        return ProxyOutcome(False, 200, {}, audit, mapping, sanitized, request_id)

    async def _await_prepare(self, payload: dict[str, Any], rid: str) -> ProxyOutcome:
        loop = asyncio.get_running_loop()
        fut = loop.run_in_executor(None, self._prepare, payload, rid)
        try:
            return await asyncio.shield(fut)
        except asyncio.CancelledError:
            await fut
            raise

    async def chat_completions(
        self,
        payload: dict[str, Any],
        headers: Mapping[str, str],
        request_id: str | None = None,
    ) -> ProxyOutcome:
        rid = request_id or uuid.uuid4().hex[:12]
        try:
            outcome = await self._await_prepare(payload, rid)
            if outcome.blocked or outcome.sanitized_payload is None:
                return outcome
            if self._upstream is None:
                outcome.body = {"error": {"message": "no upstream configured", "type": "lakanvault_config"}}
                outcome.status_code = 503
                outcome.blocked = True
                return outcome
            try:
                resp = await self._upstream.chat_completions(outcome.sanitized_payload, headers)
            except Exception:
                logger.exception("upstream chat failed")
                outcome.body = {"error": {"message": "upstream request failed", "type": "upstream_error"}}
                outcome.status_code = 502
                return outcome
            if resp.status_code >= 400:
                await resp.aclose()
                outcome.body = {"error": {"message": "upstream request failed", "type": "upstream_error"}}
                outcome.status_code = resp.status_code
                return outcome
            try:
                data = resp.json()
            except Exception:
                await resp.aclose()
                outcome.body = {"error": {"message": "upstream request failed", "type": "upstream_error"}}
                outcome.status_code = 502
                return outcome
            await resp.aclose()
            restored = restore_chat_response(
                data, lambda text: OpaqueAnonymizer.restore(text, outcome.allow_mapping)
            )
            outcome.body = restored
            outcome.status_code = 200
            return outcome
        finally:
            self._vault.delete_request(rid)

    async def iter_sse(
        self,
        payload: dict[str, Any],
        headers: Mapping[str, str],
        request_id: str | None = None,
    ) -> AsyncIterator[bytes]:
        rid = request_id or uuid.uuid4().hex[:12]
        resp = None
        try:
            outcome = await self._await_prepare(payload, rid)
            if outcome.blocked or outcome.sanitized_payload is None:
                import json

                yield (
                    f"data: {json.dumps(outcome.body)}\n\n".encode()
                )
                return
            if self._upstream is None:
                yield b'data: {"error":{"message":"no upstream configured"}}\n\n'
                return
            try:
                resp = await self._upstream.chat_completions(outcome.sanitized_payload, headers)
            except Exception:
                logger.exception("upstream stream failed")
                yield b'data: {"error":{"message":"upstream request failed"}}\n\n'
                return
            if resp.status_code >= 400:
                yield b'data: {"error":{"message":"upstream request failed"}}\n\n'
                return
            restorer = SlidingTokenRestorer(outcome.allow_mapping)
            pending = ""
            async for raw in resp.aiter_text():
                pending += raw.replace("\r\n", "\n")
                while "\n\n" in pending:
                    block, pending = pending.split("\n\n", 1)
                    for fields, data in parse_sse_chunk(block + "\n\n"):
                        if data == "[DONE]":
                            leftover = restorer.flush()
                            if leftover:
                                extra = {
                                    "choices": [{"index": 0, "delta": {"content": leftover}}]
                                }
                                import json as _json

                                yield serialize_sse({}, _json.dumps(extra, separators=(",", ":"))).encode()
                            yield serialize_sse(fields, "[DONE]").encode()
                            continue
                        yield serialize_sse(fields, restore_sse_data_json(data, restorer)).encode()
            if pending.strip():
                events = parse_sse_chunk(pending + "\n\n")
                for i, (fields, data) in enumerate(events):
                    last = i == len(events) - 1
                    yield serialize_sse(
                        fields,
                        restore_sse_data_json(data, restorer, flush=last and data != "[DONE]"),
                    ).encode()
            leftover = restorer.flush()
            if leftover:
                import json as _json

                extra = {"choices": [{"index": 0, "delta": {"content": leftover}}]}
                yield serialize_sse({}, _json.dumps(extra, separators=(",", ":"))).encode()
        except Exception:
            logger.exception("upstream stream failed")
            yield b'data: {"error":{"message":"upstream request failed"}}\n\n'
        finally:
            if resp is not None:
                await resp.aclose()
            self._vault.delete_request(rid)
