"""Tests for MCP contract DTOs."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from lakanvault.contracts.mcp import (
    AuditEntrySummary,
    AuditQueryRequest,
    AuditQueryResponse,
    ClassifyRequest,
    ClassifyResponse,
    DataTier,
    FindingSummary,
    FORBIDDEN_MCP_RESPONSE_FIELDS,
    PolicyAction,
    ProtectRequest,
    ProtectResponse,
    RestoreRequest,
    RestoreResponse,
)


def test_classify_request_requires_non_empty_text() -> None:
    with pytest.raises(ValidationError):
        ClassifyRequest(text="")


def test_classify_request_accepts_source_hint() -> None:
    req = ClassifyRequest(text="hello", source="clipboard")
    assert req.source == "clipboard"


def test_classify_response_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        ClassifyResponse(
            tier=DataTier.PUBLIC,
            action=PolicyAction.ALLOW,
            prompt_text="leak",  # type: ignore[call-arg]
        )


def test_classify_response_safe_shape() -> None:
    resp = ClassifyResponse(
        tier=DataTier.CONFIDENTIAL,
        action=PolicyAction.BLOCK,
        reason="API key pattern",
        pii_span_count=1,
        entity_types=["API_KEY"],
        injection_blocked=False,
    )
    dumped = resp.model_dump()
    assert FORBIDDEN_MCP_RESPONSE_FIELDS.isdisjoint(dumped.keys())
    assert resp.tier == DataTier.CONFIDENTIAL
    assert resp.action == PolicyAction.BLOCK


def test_audit_query_request_limit_bounds() -> None:
    with pytest.raises(ValidationError):
        AuditQueryRequest(limit=0)
    with pytest.raises(ValidationError):
        AuditQueryRequest(limit=101)
    assert AuditQueryRequest(limit=50).limit == 50


def test_audit_query_response_no_forbidden_fields() -> None:
    entry = AuditEntrySummary(
        run_id="abc12345",
        overall_status="PASS",
        timestamp="2026-07-09T12:00:00Z",
        model_filename="demo-trusted.gguf",
        pii_span_count=2,
        tier=DataTier.INTERNAL,
        action=PolicyAction.LOG,
    )
    resp = AuditQueryResponse(entries=[entry], total_returned=1)
    for key in resp.model_dump():
        assert key not in FORBIDDEN_MCP_RESPONSE_FIELDS
    for entry_dump in (e.model_dump() for e in resp.entries):
        assert FORBIDDEN_MCP_RESPONSE_FIELDS.isdisjoint(entry_dump.keys())


def test_data_tier_and_policy_action_values() -> None:
    assert DataTier.SECRET == "secret"
    assert PolicyAction.BLOCK == "block"


def test_finding_summary_forbids_matched_text() -> None:
    with pytest.raises(ValidationError):
        FindingSummary(
            entity_type="EMAIL_ADDRESS",
            tier="PII_MODERATE",
            confidence=0.9,
            start=0,
            end=5,
            text="leak@example.com",  # type: ignore[call-arg]
        )


def test_protect_response_safe_shape() -> None:
    finding = FindingSummary(
        entity_type="EMAIL_ADDRESS",
        tier="PII_MODERATE",
        confidence=0.9,
        start=5,
        end=20,
        source="presidio",
        needs_escalation=False,
    )
    resp = ProtectResponse(
        session_id="abc",
        sanitized="mail [fake] thanks",
        findings=[finding],
        finding_count=1,
    )
    dumped = resp.model_dump()
    assert FORBIDDEN_MCP_RESPONSE_FIELDS.isdisjoint(dumped.keys())
    assert "text" not in finding.model_dump()
    assert finding.entity_type == "EMAIL_ADDRESS"


def test_protect_request_llm_policy() -> None:
    with pytest.raises(ValidationError):
        ProtectRequest(text="hello", llm="maybe")
    assert ProtectRequest(text="hello", llm="never").llm == "never"


def test_restore_request_requires_session() -> None:
    with pytest.raises(ValidationError):
        RestoreRequest(text="hi", session_id="")
    out = RestoreResponse(session_id="s1", text="restored")
    assert out.text == "restored"
