"""Policies — the single place where we decide what's safe to send to cloud."""
from __future__ import annotations

from lakanvault.contracts.dtos import CloudTelemetryDTO
from lakanvault.contracts.events import PipelineEvent, StageStatus


def redact_for_cloud(event: PipelineEvent, duration_ms: float = 0.0) -> CloudTelemetryDTO:
    """
    Build a cloud-safe DTO from a pipeline event.
    Only fields listed in data-classification.md are included.
    Never called when cloud.enabled is False.
    """
    pii_count = 0
    integrity_ok = True

    for stage in event.stages:
        if stage.stage == "privacy":
            pii_count = stage.metadata.get("pii_span_count", 0)
        if stage.stage == "integrity" and stage.status == StageStatus.FAIL:
            integrity_ok = False

    return CloudTelemetryDTO(
        run_id=event.run_id,
        overall_status=event.overall_status.value,
        pii_span_count=pii_count,
        integrity_ok=integrity_ok,
        duration_ms=round(duration_ms, 2),
        bytes_processed=event.stages[0].metadata.get("bytes_processed", 0)
        if event.stages else 0,
    )
