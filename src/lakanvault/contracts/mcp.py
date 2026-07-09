"""MCP (Model Context Protocol) DTOs — read-only classify and audit shapes.

These models define the contract between IDE integrations (Cursor/VS Code)
and LakanVault. No raw PII or secrets in responses.
"""
from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class DataTier(StrEnum):
    """Four-tier classification hierarchy for DLP policy."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    SECRET = "secret"


class PolicyAction(StrEnum):
    """Action matrix outcomes for classified content."""

    ALLOW = "allow"
    WARN = "warn"
    REDACT = "redact"
    BLOCK = "block"
    LOG = "log"


class ClassifyRequest(BaseModel):
    """Input for MCP classify tool — text to evaluate before AI submission."""

    text: str = Field(min_length=1, max_length=100_000)
    source: str = Field(
        default="unknown",
        description="Origin hint: clipboard, chat, mcp, pipeline",
    )


class ClassifyResponse(BaseModel):
    """Classification result — safe for IDE display. No raw span text."""

    tier: DataTier
    action: PolicyAction
    reason: str = ""
    pii_span_count: int = 0
    entity_types: list[str] = Field(default_factory=list)
    injection_blocked: bool = False
    injection_category: str = ""

    model_config = {"extra": "forbid"}


class AuditEntrySummary(BaseModel):
    """Single audit run summary — metadata only."""

    run_id: str
    overall_status: str
    timestamp: str = ""
    model_filename: str = ""
    pii_span_count: int = 0
    tier: DataTier | None = None
    action: PolicyAction | None = None

    model_config = {"extra": "forbid"}


class AuditQueryRequest(BaseModel):
    """Input for MCP audit_recent tool."""

    limit: int = Field(default=10, ge=1, le=100)


class AuditQueryResponse(BaseModel):
    """Recent audit entries — no prompt text or paths."""

    entries: list[AuditEntrySummary] = Field(default_factory=list)
    total_returned: int = 0

    model_config = {"extra": "forbid"}


# Fields that must never appear in MCP responses (enforced in tests).
FORBIDDEN_MCP_RESPONSE_FIELDS = frozenset({
    "prompt_text",
    "raw_bytes",
    "full_path",
    "mapping",
    "sanitized_prompt",
    "api_key",
    "secret",
})
