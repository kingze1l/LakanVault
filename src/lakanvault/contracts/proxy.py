"""Proxy / transform / in-memory token-map contracts.

Sensitive values live only in local_core + infrastructure implementations.
Public DTOs and audit metadata must not carry raw prompts, mappings, or credentials.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from lakanvault.contracts.mcp import DataTier, PolicyAction

# 128-bit opaque tokens: [LV_ + Crockford/RFC base32 (26 chars) + ]
OPAQUE_TOKEN_PREFIX = "[LV_"
OPAQUE_TOKEN_BODY_LEN = 26
OPAQUE_TOKEN_REGEX = r"\[LV_[A-Z2-7]{26}\]"

FORBIDDEN_PROXY_LOG_FIELDS = frozenset({
    "prompt_text",
    "raw_prompt",
    "prompt",
    "mapping",
    "sanitized_prompt",
    "api_key",
    "secret",
    "authorization",
    "original_value",
    "token_value",
    "ocr_text",
    "image_bytes",
    "raw_bytes",
})


class FindingMeta(BaseModel):
    """Detector hit metadata — never includes the matched text."""

    entity_type: str
    start: int
    end: int

    model_config = {"extra": "forbid"}


class TransformResult(BaseModel):
    """Outcome of one text transformation. Mapping values stay in the vault."""

    text: str = ""
    tier: DataTier = DataTier.PUBLIC
    action: PolicyAction = PolicyAction.ALLOW
    reason: str = ""
    pii_span_count: int = 0
    entity_types: list[str] = Field(default_factory=list)
    tokens_minted: list[str] = Field(default_factory=list)
    blocked: bool = False
    uninspected: bool = False

    model_config = {"extra": "forbid"}


class ProxyAuditRecord(BaseModel):
    """Metadata-only audit row for a proxy/MCP sanitize hop."""

    request_id: str
    source: str = "proxy"
    overall_status: str = "PASS"
    tier: DataTier | None = None
    action: PolicyAction | None = None
    pii_span_count: int = 0
    entity_types: list[str] = Field(default_factory=list)
    blocked: bool = False
    reason: str = ""
    stream: bool = False
    image_inspected: int = 0
    uninspected_blocks: int = 0
    latency_ms: float = 0.0

    model_config = {"extra": "forbid"}


class SanitizeTextRequest(BaseModel):
    """Internal MCP shim → daemon. Raw text is local-only."""

    text: str = Field(min_length=0, max_length=500_000)
    request_id: str = Field(min_length=1, max_length=64)
    source: str = "mcp"


class SanitizeTextResponse(BaseModel):
    text: str = ""
    blocked: bool = False
    reason: str = ""
    tokens_minted: list[str] = Field(default_factory=list)
    action: PolicyAction = PolicyAction.ALLOW
    tier: DataTier = DataTier.PUBLIC

    model_config = {"extra": "forbid"}


def proxy_audit_field_names() -> frozenset[str]:
    return frozenset(ProxyAuditRecord.model_fields)


def assert_no_forbidden_proxy_fields() -> None:
    leaked = proxy_audit_field_names().intersection(FORBIDDEN_PROXY_LOG_FIELDS)
    if leaked:
        raise AssertionError(
            "Forbidden proxy audit fields present: " + ", ".join(sorted(leaked))
        )


@dataclass
class RestoreAllowSet:
    """Tokens this request is allowed to restore — never the global vault."""

    tokens: set[str] = field(default_factory=set)

    def add(self, token: str) -> None:
        self.tokens.add(token)

    def mapping_view(self, lookup) -> dict[str, str]:
        out: dict[str, str] = {}
        for token in self.tokens:
            value = lookup(token)
            if value is not None:
                out[token] = value
        return out


class TokenVaultPort(ABC):
    """Session-scoped opaque token map. Implementations must not write to disk."""

    @abstractmethod
    def mint(self, value: str, *, request_id: str, ttl_seconds: float) -> str:
        """Return a token for value; same request+value reuses the token."""

    @abstractmethod
    def get(self, token: str) -> str | None:
        """Exact-token lookup; expired tokens return None."""

    @abstractmethod
    def delete_request(self, request_id: str) -> int:
        """Drop all mappings for a request. Returns rows removed."""

    @abstractmethod
    def cleanup_expired(self) -> int:
        """Remove expired rows. Returns rows removed."""

    @abstractmethod
    def close(self) -> None:
        """Deterministic shutdown — wipe the in-memory database."""
