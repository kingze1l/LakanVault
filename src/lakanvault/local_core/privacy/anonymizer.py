"""Reversible PII anonymizer.

Replaces PII spans with stable placeholders (NAME_001, EMAIL_001, ...)
and returns a mapping so the caller can restore the original values
in the model's response. The mapping NEVER touches disk — session only.
"""
from __future__ import annotations

import logging
import re
from collections import defaultdict

from lakanvault.local_core.privacy.detectors import find_pii_spans

logger = logging.getLogger(__name__)

_ENTITY_ALIAS = {
    "PERSON": "NAME",
    "EMAIL_ADDRESS": "EMAIL",
    "PHONE_NUMBER": "PHONE",
}


_PLACEHOLDER_RE = re.compile(r"\b(NAME|EMAIL|PHONE)_(\d{3})\b", re.IGNORECASE)


class ReversibleAnonymizer:
    """
    anonymize(text) -> (sanitized_text, mapping)
    restore(text, mapping) -> original_text

    mapping: {"NAME_001": "John Doe", "EMAIL_001": "john@x.com", ...}
    """

    @property
    def available(self) -> bool:
        return True

    def anonymize(self, text: str) -> tuple[str, dict[str, str], str]:
        if not text:
            return text, {}, "none"

        spans, engine = find_pii_spans(text)
        if not spans:
            return text, {}, engine

        logger.debug("Anonymizing %d span(s) via %s", len(spans), engine)

        spans_sorted = sorted(spans, key=lambda s: s.start, reverse=True)
        counters: dict[str, int] = defaultdict(int)
        mapping: dict[str, str] = {}
        value_to_placeholder: dict[str, str] = {}

        out = text
        for span in spans_sorted:
            original = span.text
            if original in value_to_placeholder:
                placeholder = value_to_placeholder[original]
            else:
                label = _ENTITY_ALIAS.get(span.entity_type, span.entity_type)
                counters[label] += 1
                placeholder = f"{label}_{counters[label]:03d}"
                value_to_placeholder[original] = placeholder
                mapping[placeholder] = original

            out = out[: span.start] + placeholder + out[span.end :]

        return out, mapping, engine

    @staticmethod
    def restore(text: str, mapping: dict[str, str]) -> str:
        if not mapping or not text:
            return text
        # Normalize keys to canonical NAME_001 form for lookup
        canon: dict[str, str] = {}
        for placeholder, original in mapping.items():
            m = _PLACEHOLDER_RE.fullmatch(placeholder.strip())
            if m:
                key = f"{m.group(1).upper()}_{m.group(2)}"
            else:
                key = placeholder.upper()
            canon[key] = original

        def _repl(match: re.Match[str]) -> str:
            key = f"{match.group(1).upper()}_{match.group(2)}"
            return canon.get(key, match.group(0))

        out = _PLACEHOLDER_RE.sub(_repl, text)
        # Exact match pass for any placeholders the regex missed
        for placeholder in sorted(canon, key=len, reverse=True):
            out = out.replace(placeholder, canon[placeholder])
        return out

    @staticmethod
    def placeholder_system_hint(mapping: dict[str, str]) -> str | None:
        if not mapping:
            return None
        tokens = ", ".join(sorted(mapping.keys()))
        return (
            "The user message uses privacy placeholders (" + tokens + "). "
            "When referring to those people or values, repeat the exact placeholder "
            "tokens (e.g. NAME_001) in your reply. They are restored for the user automatically."
        )
