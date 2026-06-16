"""Data Transfer Objects — safe shapes for passing data across layer boundaries."""
from __future__ import annotations

from pydantic import BaseModel


class ScanRequest(BaseModel):
    """What the UI/gateway sends into the pipeline."""
    target_path: str
    prompt_text: str = ""


class ScanResponse(BaseModel):
    """What the gateway returns to the UI — no raw sensitive data."""
    run_id: str
    overall_status: str
    stages: list[dict]
    hash_summary: str = ""
    pii_span_count: int = 0
    cloud_forwarded: bool = False


class ChatRequest(BaseModel):
    prompt: str
    model: str | None = None
    base_url: str | None = None


class SettingsUpdate(BaseModel):
    local_ai: dict | None = None
    local: dict | None = None
    privacy: dict | None = None
    cloud: dict | None = None


class ChatResponse(BaseModel):
    """Sanitized chat round-trip — mapping values never leave the server."""
    sanitized_prompt: str
    raw_response: str
    restored_response: str
    pii_span_count: int = 0
    placeholders: list[str] = []
    error: str | None = None
    model_used: str = ""
    provider_url: str = ""
    latency_ms: float = 0.0
    sanitize_ms: float = 0.0


class IntegrityEjectRequest(BaseModel):
    model_name: str


class BaselineRequest(BaseModel):
    model_name: str
    sha256_hex: str | None = None


class CloudTelemetryDTO(BaseModel):
    """Only fields allowed to cross the cloud boundary. See data-classification.md."""
    run_id: str
    overall_status: str
    pii_span_count: int          # count only, never the text
    integrity_ok: bool
    duration_ms: float
    bytes_processed: int = 0
    # NO: prompts, model bytes, paths, API keys, raw audit JSON

    model_config = {
        "extra": "forbid",
    }


def cloud_dto_field_names() -> frozenset[str]:
    return frozenset(CloudTelemetryDTO.model_fields)


def assert_no_forbidden_cloud_fields() -> None:
    from lakanvault.shared.constants import FORBIDDEN_CLOUD_DTO_FIELDS

    forbidden = cloud_dto_field_names().intersection(FORBIDDEN_CLOUD_DTO_FIELDS)
    if forbidden:
        raise AssertionError(
            "Forbidden cloud DTO fields present: " + ", ".join(sorted(forbidden))
        )
