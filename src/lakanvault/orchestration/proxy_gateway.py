"""Proxy request lifecycle — sanitize, optional upstream, restore, audit metadata."""
from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lakanvault.contracts.mcp import DataTier, PolicyAction
from lakanvault.contracts.proxy import (
    ChatPayloadClassifyResponse,
    ProxyAuditRecord,
    TokenVaultPort,
    TransformResult,
)
from lakanvault.infrastructure.upstream.openai import OpenAIUpstream
from lakanvault.infrastructure.upstream.sse import SlidingMappingRestorer, parse_sse_chunk, restore_sse_data_json, serialize_sse
from lakanvault.local_core.anonymizer.anonymizer import Vault
from lakanvault.local_core.dlp.openai_payload import (
    UninspectedPayloadError,
    orchestrated_prompt,
    restore_chat_response,
    sanitize_chat_request,
)
from lakanvault.local_core.policy.engine import Action
from lakanvault.local_core.privacy.classifier import classify_content
from lakanvault.local_core.scan import process_input
from lakanvault.local_core.findings import Tier

logger = logging.getLogger(__name__)

_JOAN_TIER_TO_DATA: dict[Tier, DataTier] = {
    Tier.SECRET: DataTier.SECRET,
    Tier.PII_HIGH: DataTier.CONFIDENTIAL,
    Tier.PII_MODERATE: DataTier.INTERNAL,
    Tier.PII_LOW: DataTier.INTERNAL,
    Tier.BENIGN: DataTier.PUBLIC,
}

_JOAN_ACTION_TO_POLICY: dict[Action, PolicyAction] = {
    Action.ALLOW: PolicyAction.ALLOW,
    Action.WARN: PolicyAction.WARN,
    Action.MASK: PolicyAction.REDACT,
    Action.BLOCK: PolicyAction.BLOCK,
}


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
        vault_key_path: str | Path | None = None,
    ) -> None:
        self._vault = vault
        self._upstream = upstream
        self._strict = strict
        self._ttl = ttl_seconds
        self._allow_images = allow_images
        self._vault_key_path = Path(vault_key_path) if vault_key_path else Path("data") / "vault.key"
        self._joan_vaults: dict[str, Vault] = {}
        if allow_images and image_inspector is None:
            from lakanvault.local_core.dlp.image_inspector import ImageInspector

            image_inspector = ImageInspector()
        self._image_inspector = image_inspector

    def _joan_vault(self, request_id: str) -> Vault:
        vault = self._joan_vaults.get(request_id)
        if vault is None:
            self._vault_key_path.parent.mkdir(parents=True, exist_ok=True)
            vault = Vault(":memory:", workspace=request_id, key_path=str(self._vault_key_path))
            self._joan_vaults[request_id] = vault
        return vault

    def _drop_request(self, request_id: str) -> None:
        self._joan_vaults.pop(request_id, None)
        self._vault.delete_request(request_id)

    def classify_chat_payload(self, payload: dict[str, Any]) -> ChatPayloadClassifyResponse:
        """Classify outbound chat text. The response never includes that text."""
        text = orchestrated_prompt(payload)
        if len(text) > 100_000:
            raise ValueError("extracted text too large")
        result = classify_content(text)
        roles: list[str] = []
        messages = payload.get("messages")
        if isinstance(messages, list):
            for msg in messages:
                if isinstance(msg, dict):
                    roles.append(str(msg.get("role") or "user"))
        return ChatPayloadClassifyResponse(
            tier=DataTier(result.tier),
            action=PolicyAction(result.action),
            reason=result.reason,
            pii_span_count=result.pii_span_count,
            entity_types=list(result.entity_types),
            injection_blocked=result.injection_blocked,
            injection_category=result.injection_category,
            analyzed_char_count=len(text),
            message_roles=roles,
        )

    async def classify_chat_payload_async(self, payload: dict[str, Any]) -> ChatPayloadClassifyResponse:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.classify_chat_payload, payload)

    def sanitize_text(self, text: str, request_id: str) -> TransformResult:
        """Joan scan + decide + Vault surrogates (Presidio PII / format-preserving secrets)."""
        if not text:
            return TransformResult(text=text)
        try:
            vault = self._joan_vault(request_id)
            from lakanvault.orchestration.protect_events import record_protect_event

            protected = process_input(text, vault, llm="never")
            entity_types = sorted({f.entity_type for f in protected.findings})
            order = {
                DataTier.PUBLIC: 0,
                DataTier.INTERNAL: 1,
                DataTier.CONFIDENTIAL: 2,
                DataTier.SECRET: 3,
            }
            top_tier = max(
                (_JOAN_TIER_TO_DATA.get(f.tier, DataTier.PUBLIC) for f in protected.findings),
                key=lambda t: order[t],
                default=DataTier.PUBLIC,
            )
            action = _JOAN_ACTION_TO_POLICY.get(protected.final_action, PolicyAction.ALLOW)
            action_s = (
                protected.final_action.value
                if hasattr(protected.final_action, "value")
                else str(protected.final_action)
            )
            if action_s in ("warn", "mask", "block"):
                record_protect_event(
                    action_s,
                    source="proxy",
                    entity_types=entity_types,
                )
            if protected.final_action == Action.BLOCK:
                # Keep reason free of secret substrings (e.g. entity types containing "sk-").
                reason = "API key or credential pattern detected"
                return TransformResult(
                    text="",
                    tier=top_tier,
                    action=PolicyAction.BLOCK,
                    reason=reason,
                    pii_span_count=len(protected.findings),
                    entity_types=entity_types,
                    blocked=True,
                )
            fakes = list(vault.mapping().keys())
            return TransformResult(
                text=protected.sanitized,
                tier=top_tier,
                action=action,
                reason="joan_process_input",
                pii_span_count=len(protected.findings),
                entity_types=entity_types,
                tokens_minted=fakes,
                blocked=False,
            )
        except Exception as exc:
            logger.exception("joan sanitize failed")
            from lakanvault.orchestration.protect_events import record_protect_event

            record_protect_event("block", source="proxy", entity_types=[])
            return TransformResult(
                text="",
                tier=DataTier.SECRET,
                action=PolicyAction.BLOCK,
                reason=f"detector failure: {type(exc).__name__}",
                blocked=True,
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

        joan = self._joan_vaults.get(request_id)
        mapping = joan.mapping() if joan is not None else {}
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
            mapping = outcome.allow_mapping

            def _restore(text: str) -> str:
                if not mapping:
                    return text
                out = text
                for fake in sorted(mapping, key=len, reverse=True):
                    out = out.replace(fake, mapping[fake])
                return out

            restored = restore_chat_response(data, _restore)
            outcome.body = restored
            outcome.status_code = 200
            return outcome
        finally:
            self._drop_request(rid)

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
            restorer = SlidingMappingRestorer(outcome.allow_mapping)
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
            self._drop_request(rid)
