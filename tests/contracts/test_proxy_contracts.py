"""Contract tests for proxy / vault / transform public shapes."""
from pydantic import ValidationError

from lakanvault.contracts.mcp import DataTier, PolicyAction
from lakanvault.contracts.proxy import (
    FORBIDDEN_PROXY_LOG_FIELDS,
    ProxyAuditRecord,
    SanitizeTextResponse,
    TransformResult,
    assert_no_forbidden_proxy_fields,
    proxy_audit_field_names,
)


def test_proxy_audit_schema_has_no_forbidden_fields() -> None:
    assert_no_forbidden_proxy_fields()
    assert proxy_audit_field_names().isdisjoint(FORBIDDEN_PROXY_LOG_FIELDS)


def test_proxy_audit_rejects_raw_prompt() -> None:
    try:
        ProxyAuditRecord(request_id="r1", prompt_text="secret")  # type: ignore[call-arg]
    except ValidationError:
        return
    raise AssertionError("ProxyAuditRecord must forbid prompt_text")


def test_proxy_audit_rejects_mapping() -> None:
    try:
        ProxyAuditRecord(request_id="r1", mapping={"[LV_A]": "sk-x"})  # type: ignore[call-arg]
    except ValidationError:
        return
    raise AssertionError("ProxyAuditRecord must forbid mapping")


def test_proxy_audit_rejects_authorization() -> None:
    try:
        ProxyAuditRecord(request_id="r1", authorization="Bearer sk-live")  # type: ignore[call-arg]
    except ValidationError:
        return
    raise AssertionError("ProxyAuditRecord must forbid authorization")


def test_transform_result_forbids_api_key_field() -> None:
    try:
        TransformResult(api_key="sk-live")  # type: ignore[call-arg]
    except ValidationError:
        return
    raise AssertionError("TransformResult must forbid api_key")


def test_sanitize_response_dump_is_safe() -> None:
    resp = SanitizeTextResponse(
        text="hello [LV_AAAAAAAAAAAAAAAAAAAAAAAAAA]",
        blocked=False,
        action=PolicyAction.REDACT,
        tier=DataTier.INTERNAL,
        tokens_minted=["[LV_AAAAAAAAAAAAAAAAAAAAAAAAAA]"],
    )
    dumped = resp.model_dump()
    assert FORBIDDEN_PROXY_LOG_FIELDS.isdisjoint(dumped.keys())
