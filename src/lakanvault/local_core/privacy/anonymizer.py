"""Reversible PII anonymizer.

Replaces PII spans with stable placeholders (NAME_001, EMAIL_001, ...)
and returns a mapping so the caller can restore the original values
in the model's response. The mapping NEVER touches disk — session only.
"""
from __future__ import annotations

import logging
from collections import defaultdict

from lakanvault.local_core.privacy.detectors import find_pii_spans

logger = logging.getLogger(__name__)

_ENTITY_ALIAS = {
    "PERSON": "NAME",
    "EMAIL_ADDRESS": "EMAIL",
    "PHONE_NUMBER": "PHONE",
}


class ReversibleAnonymizer:
    """
    anonymize(text) -> (sanitized_text, mapping)
    restore(text, mapping) -> original_text

    mapping: {"NAME_001": "John Doe", "EMAIL_001": "john@x.com", ...}
    """

    @property
    def available(self) -> bool:
        return True

    def anonymize(self, text: str) -> tuple[str, dict[str, str]]:
        if not text:
            return text, {}

        spans, engine = find_pii_spans(text)
        if not spans:
            return text, {}

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

        return out, mapping

    @staticmethod
    def restore(text: str, mapping: dict[str, str]) -> str:
        if not mapping:
            return text
        out = text
        for placeholder in sorted(mapping, key=len, reverse=True):
            out = out.replace(placeholder, mapping[placeholder])
        return out
