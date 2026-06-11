from lakanvault.contracts.dtos import (
    CloudTelemetryDTO,
    assert_no_forbidden_cloud_fields,
    cloud_dto_field_names,
)
from lakanvault.contracts.events import PipelineEvent, StageResult, StageStatus
from lakanvault.contracts.policies import redact_for_cloud
from lakanvault.shared.constants import FORBIDDEN_CLOUD_DTO_FIELDS


def test_cloud_dto_has_no_forbidden_field_names() -> None:
    assert_no_forbidden_cloud_fields()
    assert cloud_dto_field_names().isdisjoint(FORBIDDEN_CLOUD_DTO_FIELDS)


def test_cloud_dto_rejects_extra_sensitive_fields() -> None:
    try:
        CloudTelemetryDTO(
            run_id="r1",
            overall_status="PASS",
            pii_span_count=0,
            integrity_ok=True,
            duration_ms=1.0,
            raw_prompt="secret",
        )
    except Exception:
        return
    raise AssertionError("CloudTelemetryDTO must forbid extra sensitive fields")


def test_redact_for_cloud_uses_safe_fields_only() -> None:
    event = PipelineEvent(run_id="r1", target_path="model.bin", prompt_text="secret@example.com")
    event.stages.append(
        StageResult(
            stage="privacy",
            status=StageStatus.WARN,
            metadata={"pii_span_count": 2},
        )
    )
    dto = redact_for_cloud(event, duration_ms=12.5)
    payload = dto.model_dump()
    assert "raw_prompt" not in payload
    assert "prompt_text" not in payload
    assert payload["pii_span_count"] == 2
