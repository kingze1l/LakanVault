"""Shared types for LakanVault detectors (secrets/ and pii/ both import from here)."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum

# ---- thresholds -------------------------------------------------------------
CONFIDENT_AT = 0.75    # confidence >= this: decisive, no LLM needed
DISCARD_BELOW = 0.35   # confidence <  this: ignored entirely
# Findings between the two values are "unsure" -> needs_escalation == True


class Tier(str, Enum):
    """
    Risk tiers. The three PII levels follow the PII confidentiality impact
    levels (low / moderate / high) of NIST SP 800-122, section 3.1.
    SECRET is a project addition: NIST SP 800-122 covers PII only.
    BENIGN = NIST's "not applicable"; detectors never emit it, it exists
    for the local LLM to return.
    """
    SECRET = "SECRET"
    PII_HIGH = "PII_HIGH"
    PII_MODERATE = "PII_MODERATE"
    PII_LOW = "PII_LOW"
    BENIGN = "BENIGN"


TIER_RANK = {Tier.SECRET: 4, Tier.PII_HIGH: 3, Tier.PII_MODERATE: 2,
             Tier.PII_LOW: 1, Tier.BENIGN: 0}


@dataclass(frozen=True)
class Finding:
    entity_type: str               # e.g. "aws-access-token", "EMAIL_ADDRESS"
    text: str = field(repr=False)  # matched value (repr=False: never leak in logs)
    start: int                     # character offset in the prompt (inclusive)
    end: int                       # character offset (exclusive)
    confidence: float              # 0..1
    tier: Tier
    source: str                    # "secrets" | "presidio" | ... (LLM layer adds "llm")

    @property
    def needs_escalation(self) -> bool:
        """True when the fast layer is unsure -> hand to the local LLM."""
        return self.confidence < CONFIDENT_AT

    @property
    def preview(self) -> str:
        return self.text


class DetectionEngine(ABC):
    """Common interface. The local LLM classifier can implement it too."""
    layer: str

    @abstractmethod
    def detect(self, text: str) -> list[Finding]:
        ...


def resolve_overlaps(findings: list[Finding]) -> list[Finding]:
    """
    Two findings on the same characters (an email inside a connection string,
    two secret rules hitting one value) must not both survive. Keep one:
    higher tier, then higher confidence, then longer span.
    """
    ranked = sorted(
        findings,
        key=lambda f: (-TIER_RANK[f.tier], -f.confidence,
                       f.entity_type == "generic-api-key",   # generic rule loses ties
                       -(f.end - f.start), f.start),
    )
    kept: list[Finding] = []
    for f in ranked:
        if all(f.end <= k.start or f.start >= k.end for k in kept):
            kept.append(f)
    return sorted(kept, key=lambda f: f.start)

