from datetime import datetime, timezone

from lakanvault.contracts.dtos import (
    CloudTelemetryDTO,
    RedactedText,
    assert_no_forbidden_cloud_fields,
    cloud_dto_field_names,
)
from lakanvault.contracts.events import IntegrityVerified, PIIMasked
from lakanvault.contracts.policies import redact_for_cloud
from lakanvault.shared.constants import FORBIDDEN_CLOUD_DTO_FIELDS


def test_cloud_dto_has_no_forbidden_field_names() -> None:
    assert_no_forbidden_cloud_fields()
    assert cloud_dto_field_names().isdisjoint(FORBIDDEN_CLOUD_DTO_FIELDS)


def test_cloud_dto_rejects_extra_sensitive_fields() -> None:
    try:
        CloudTelemetryDTO(
            event_type="bad",
            timestamp=datetime.now(timezone.utc),
            raw_prompt="secret",
        )
    except Exception:
        return
    raise AssertionError("CloudTelemetryDTO must forbid extra sensitive fields")


def test_redact_for_cloud_does_not_include_raw_prompt() -> None:
    event = PIIMasked(request_id="r1", entity_count=3, timestamp=datetime.now(timezone.utc))
    dto = redact_for_cloud(event)
    payload = dto.model_dump()
    assert "raw_prompt" not in payload
    assert "prompt" not in payload
    assert payload.get("entity_count") == 3


def test_integrity_redaction_uses_hash_prefix_only() -> None:
    digest = "a" * 64
    event = IntegrityVerified(
        model_id="m1",
        sha256=digest,
        verified=True,
        timestamp=datetime.now(timezone.utc),
    )
    dto = redact_for_cloud(event)
    assert dto.hash_prefix == digest[:16]
    assert dto.hash_prefix is not None
    assert len(dto.hash_prefix) == 16


def test_redacted_text_schema_is_minimal() -> None:
    RedactedText(request_id="r1", text="[EMAIL]")
    assert set(RedactedText.model_fields) == {"request_id", "text"}
