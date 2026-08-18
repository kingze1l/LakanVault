"""Opaque-token anonymizer (CS301). Do not edit ReversibleAnonymizer in place."""
from __future__ import annotations


class OpaqueAnonymizer:
    """Replace PII with opaque tokens (TKN_xxxx) in a later slice.

    Today this is identity-only so the module and restore helper exist
    without changing the chat path, which still uses ReversibleAnonymizer.
    """

    def anonymize(self, text: str) -> tuple[str, dict[str, str], str]:
        if not text:
            return text, {}, "opaque"
        return text, {}, "opaque"

    @staticmethod
    def restore(text: str, mapping: dict[str, str]) -> str:
        if not mapping or not text:
            return text
        out = text
        for token, original in sorted(mapping.items(), key=lambda kv: len(kv[0]), reverse=True):
            out = out.replace(token, original)
        return out
