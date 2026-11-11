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


class FindingSummary(BaseModel):
    """Safe finding metadata for IDE display. Never includes matched text."""

    entity_type: str
    tier: str
    confidence: float = Field(ge=0.0, le=1.0)
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    source: str = ""
    needs_escalation: bool = False
    action: str = ""  # Joan allow/warn/mask/block for this finding

    model_config = {"extra": "forbid"}


class ProtectRequest(BaseModel):
    """Input for MCP protect — scan + sanitize before an external LLM."""

    text: str = Field(min_length=1, max_length=100_000)
    session_id: str = Field(default="", max_length=64)
    llm: str = Field(default="unsure", pattern="^(unsure|always|never)$")

    model_config = {"extra": "forbid"}


class ProtectResponse(BaseModel):
    """Sanitized prompt + finding metadata. No raw secret/PII values."""

    session_id: str
    sanitized: str
    findings: list[FindingSummary] = Field(default_factory=list)
    finding_count: int = 0
    final_action: str = "allow"  # Joan whole-prompt verdict
    allow_send: bool = True
    event_id: int | None = None  # tray/Status View link (when warn/mask/block)

    model_config = {"extra": "forbid"}


class ReviewSendRequest(BaseModel):
    """Send an already-reviewed prompt via the local LLM."""

    session_id: str = Field(min_length=1, max_length=64)
    sanitized: str = Field(min_length=0, max_length=100_000)
    model: str | None = None
    base_url: str | None = None
    override: bool = Field(
        default=False,
        description="If true, send original unmasked text once (Prompt Review only).",
    )

    model_config = {"extra": "forbid"}


class ReviewSendResponse(BaseModel):
    """Local LLM reply with FR8 restore. No mapping values."""

    session_id: str
    raw_response: str = ""
    restored_response: str = ""
    model_used: str = ""
    provider_url: str = ""
    latency_ms: float = 0.0
    error: str | None = None
    blocked: bool = False
    block_reason: str = ""
    override_used: bool = False

    model_config = {"extra": "forbid"}


class RestoreRequest(BaseModel):
    """Input for MCP restore — external LLM reply → original values."""

    text: str = Field(min_length=0, max_length=500_000)
    session_id: str = Field(min_length=1, max_length=64)

    model_config = {"extra": "forbid"}


class RestoreResponse(BaseModel):
    """Restored reply for the user."""

    session_id: str
    text: str

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
    "real",
    "preview",
})
