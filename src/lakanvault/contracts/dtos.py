from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from lakanvault.shared.constants import FORBIDDEN_CLOUD_DTO_FIELDS


class SensitiveContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    request_id: str
    model_path: str | None = None
    prompt_text: str | None = None


class RedactedText(BaseModel):
    model_config = ConfigDict(frozen=True)

    request_id: str
    text: str


class CloudTelemetryDTO(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    event_type: str
    timestamp: datetime
    request_id: str | None = None
    severity: str | None = None
    finding_type: str | None = None
    hash_prefix: str | None = Field(default=None, max_length=16)
    entity_count: int | None = Field(default=None, ge=0)
    stage: str | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    bytes_processed: int | None = Field(default=None, ge=0)


class StatusSummaryDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    request_id: str
    overall_status: Literal["ok", "fail", "pending", "not_implemented"]
    stages_completed: list[str] = Field(default_factory=list)
    message: str | None = None


def cloud_dto_field_names() -> frozenset[str]:
    return frozenset(CloudTelemetryDTO.model_fields.keys())


def assert_no_forbidden_cloud_fields() -> None:
    overlap = cloud_dto_field_names() & FORBIDDEN_CLOUD_DTO_FIELDS
    if overlap:
        raise RuntimeError(f"CloudTelemetryDTO defines forbidden fields: {sorted(overlap)}")
