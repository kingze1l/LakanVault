"""Data Transfer Objects — safe shapes for passing data across layer boundaries."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from lakanvault.shared.constants import FORBIDDEN_CLOUD_DTO_FIELDS


class ScanRequest(BaseModel):
    target_path: str
    prompt_text: str = ""


class ScanResponse(BaseModel):
    run_id: str
    overall_status: str
    stages: list[dict]
    hash_summary: str = ""
    pii_span_count: int = 0
    cloud_forwarded: bool = False


class CloudTelemetryDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    overall_status: str
    pii_span_count: int
    integrity_ok: bool
    duration_ms: float
    bytes_processed: int = 0


def cloud_dto_field_names() -> frozenset[str]:
    return frozenset(CloudTelemetryDTO.model_fields.keys())


def assert_no_forbidden_cloud_fields() -> None:
    overlap = cloud_dto_field_names() & FORBIDDEN_CLOUD_DTO_FIELDS
    if overlap:
        raise RuntimeError(f"CloudTelemetryDTO defines forbidden fields: {sorted(overlap)}")
