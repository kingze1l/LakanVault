"""Opaque-token anonymizer (CS301). Chat demo still may use ReversibleAnonymizer."""
from __future__ import annotations

import re

from lakanvault.contracts.proxy import OPAQUE_TOKEN_REGEX, TokenVaultPort

_TOKEN_RE = re.compile(OPAQUE_TOKEN_REGEX)


class OpaqueAnonymizer:
    """Replace spans with vault-minted [LV_…] tokens. No SQLite imports here."""

    def anonymize(
        self,
        text: str,
        spans: list[tuple[int, int, str]] | None = None,
        vault: TokenVaultPort | None = None,
        *,
        request_id: str = "",
        ttl_seconds: float = 3600.0,
    ) -> tuple[str, dict[str, str] | list[str], str]:
        if not text:
            return text, {} if vault is None else [], "opaque"
        if vault is None or not spans:
            return text, {} if vault is None else [], "opaque"
        minted: list[str] = []
        out = text
        for start, end, _kind in sorted(spans, key=lambda s: s[0], reverse=True):
            original = text[start:end]
            token = vault.mint(original, request_id=request_id, ttl_seconds=ttl_seconds)
            minted.append(token)
            out = out[:start] + token + out[end:]
        seen: set[str] = set()
        ordered: list[str] = []
        for token in reversed(minted):
            if token not in seen:
                seen.add(token)
                ordered.append(token)
        return out, ordered, "opaque"

    @staticmethod
    def restore(text: str, mapping: dict[str, str]) -> str:
        if not mapping or not text:
            return text
        out = text
        for token, original in sorted(mapping.items(), key=lambda kv: len(kv[0]), reverse=True):
            out = out.replace(token, original)
        return out

    @staticmethod
    def find_tokens(text: str) -> list[str]:
        return _TOKEN_RE.findall(text or "")
