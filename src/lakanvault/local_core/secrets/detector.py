"""Secret detection — regex + entropy. Sibling of privacy/detectors.py (PII)."""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

_API_KEY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bsk-[a-zA-Z0-9]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bghp_[a-zA-Z0-9]{36}\b"),
    re.compile(r"\bxox[baprs]-[a-zA-Z0-9-]{10,}\b"),
    re.compile(r"\bBearer\s+[a-zA-Z0-9._-]{20,}\b", re.IGNORECASE),
)


@dataclass(frozen=True)
class SecretHit:
    kind: str
    start: int
    end: int


def shannon_entropy(text: str) -> float:
    """Bits per character. Empty string is 0. Not yet used as a classify gate."""
    if not text:
        return 0.0
    counts = Counter(text)
    n = len(text)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def detect_secrets(text: str) -> list[SecretHit]:
    """Return credential-pattern hits. No raw secret text on the hit."""
    if not text:
        return []
    hits: list[SecretHit] = []
    for pattern in _API_KEY_PATTERNS:
        for match in pattern.finditer(text):
            hits.append(SecretHit(kind="API_KEY", start=match.start(), end=match.end()))
    hits.sort(key=lambda h: h.start)
    return hits
