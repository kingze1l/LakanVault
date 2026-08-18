"""Content classification — maps text to tier + action for DLP policy."""
from __future__ import annotations

from dataclasses import dataclass

from lakanvault.local_core.privacy.detectors import PiiSpan, find_pii_spans
from lakanvault.local_core.secrets.detector import detect_secrets
from lakanvault.local_core.security.prompt_guard import detect_prompt_injection

_DLP_ENTITY_TYPES = frozenset({"PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER"})


@dataclass(frozen=True)
class ClassificationResult:
    tier: str
    action: str
    reason: str
    pii_span_count: int
    entity_types: list[str]
    injection_blocked: bool
    injection_category: str


def _detect_api_key(text: str) -> bool:
    return bool(detect_secrets(text))


def _entity_types(spans: list[PiiSpan]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for span in spans:
        if span.entity_type not in seen:
            seen.add(span.entity_type)
            ordered.append(span.entity_type)
    return ordered


def classify_content(text: str) -> ClassificationResult:
    """Classify text into tier + action. No raw span text in result."""
    injection = detect_prompt_injection(text)
    if injection:
        return ClassificationResult(
            tier="secret",
            action="block",
            reason=f"Prompt injection detected: {injection}",
            pii_span_count=0,
            entity_types=[],
            injection_blocked=True,
            injection_category=injection,
        )

    if _detect_api_key(text):
        return ClassificationResult(
            tier="confidential",
            action="block",
            reason="API key or credential pattern detected",
            pii_span_count=0,
            entity_types=["API_KEY"],
            injection_blocked=False,
            injection_category="",
        )

    spans, _engine = find_pii_spans(text)
    dlp_spans = [s for s in spans if s.entity_type in _DLP_ENTITY_TYPES]
    if dlp_spans:
        types = _entity_types(dlp_spans)
        return ClassificationResult(
            tier="internal",
            action="redact",
            reason="PII detected — redact before AI submission",
            pii_span_count=len(dlp_spans),
            entity_types=types,
            injection_blocked=False,
            injection_category="",
        )

    return ClassificationResult(
        tier="public",
        action="allow",
        reason="No sensitive content detected",
        pii_span_count=0,
        entity_types=[],
        injection_blocked=False,
        injection_category="",
    )
