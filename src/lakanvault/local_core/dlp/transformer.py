"""Unified DLP transform: secrets + PII + policy + opaque tokens."""
from __future__ import annotations

from lakanvault.contracts.mcp import DataTier, PolicyAction
from lakanvault.contracts.proxy import TokenVaultPort, TransformResult
from lakanvault.local_core.policy.engine import decide_action
from lakanvault.local_core.privacy.classifier import classify_content
from lakanvault.local_core.privacy.detectors import find_pii_spans
from lakanvault.local_core.privacy.opaque_anonymizer import OpaqueAnonymizer
from lakanvault.local_core.secrets.detector import detect_secrets

_PII_TYPES = frozenset({"PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER"})
DEFAULT_TTL = 3600.0


def _merge_spans(text: str) -> list[tuple[int, int, str]]:
    raw: list[tuple[int, int, str]] = []
    for hit in detect_secrets(text):
        raw.append((hit.start, hit.end, hit.kind))
    spans, _engine = find_pii_spans(text)
    for span in spans:
        if span.entity_type in _PII_TYPES:
            raw.append((span.start, span.end, span.entity_type))
    raw.sort(key=lambda s: (s[0], -(s[1] - s[0])))
    kept: list[tuple[int, int, str]] = []
    for start, end, kind in raw:
        if any(start >= k[0] and end <= k[1] for k in kept):
            continue
        if any(start < k[1] and end > k[0] for k in kept):
            continue
        kept.append((start, end, kind))
    return sorted(kept, key=lambda s: s[0])


def transform_text(
    text: str,
    vault: TokenVaultPort,
    *,
    request_id: str,
    ttl_seconds: float = DEFAULT_TTL,
    fail_closed: bool = True,
) -> TransformResult:
    if not text:
        return TransformResult(text=text)
    try:
        classification = classify_content(text)
        action = PolicyAction(decide_action(classification.tier))
        # classifier already chose an action; prefer that when it is stricter
        ranked = {
            PolicyAction.ALLOW: 0,
            PolicyAction.LOG: 1,
            PolicyAction.WARN: 2,
            PolicyAction.REDACT: 3,
            PolicyAction.BLOCK: 4,
        }
        cls_action = PolicyAction(classification.action)
        if ranked[cls_action] > ranked[action]:
            action = cls_action
        tier = DataTier(classification.tier)
        if action == PolicyAction.BLOCK:
            return TransformResult(
                text="",
                tier=tier,
                action=action,
                reason=classification.reason,
                pii_span_count=classification.pii_span_count,
                entity_types=list(classification.entity_types),
                blocked=True,
            )
        if action != PolicyAction.REDACT:
            return TransformResult(
                text=text,
                tier=tier,
                action=action,
                reason=classification.reason,
                pii_span_count=classification.pii_span_count,
                entity_types=list(classification.entity_types),
            )
        spans = _merge_spans(text)
        sanitized, minted, _engine = OpaqueAnonymizer().anonymize(
            text, spans, vault, request_id=request_id, ttl_seconds=ttl_seconds
        )
        return TransformResult(
            text=sanitized,
            tier=tier,
            action=action,
            reason=classification.reason,
            pii_span_count=len(spans),
            entity_types=list(classification.entity_types),
            tokens_minted=minted,
        )
    except Exception as exc:
        if fail_closed:
            return TransformResult(
                text="",
                tier=DataTier.SECRET,
                action=PolicyAction.BLOCK,
                reason=f"detector failure: {type(exc).__name__}",
                blocked=True,
            )
        raise
