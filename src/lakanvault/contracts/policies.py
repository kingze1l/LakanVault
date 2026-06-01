from lakanvault.contracts.dtos import CloudTelemetryDTO
from lakanvault.contracts.events import (
    AuditRecorded,
    IntegrityVerified,
    PIIMasked,
    ThreatFinding,
)
from lakanvault.infrastructure.config_loader import AppConfig

PipelineEvent = IntegrityVerified | ThreatFinding | PIIMasked | AuditRecorded


class AirGapPolicy:
    @staticmethod
    def cloud_allowed(config: AppConfig) -> bool:
        return config.cloud.enabled


class CloudEligibility:
    @staticmethod
    def event_may_forward(event: PipelineEvent) -> bool:
        return isinstance(
            event,
            (IntegrityVerified, ThreatFinding, PIIMasked, AuditRecorded),
        )


def redact_for_cloud(event: PipelineEvent) -> CloudTelemetryDTO:
    if isinstance(event, IntegrityVerified):
        return CloudTelemetryDTO(
            event_type="integrity_verified",
            timestamp=event.timestamp,
            hash_prefix=event.sha256[:16],
            severity="info" if event.verified else "high",
        )
    if isinstance(event, ThreatFinding):
        return CloudTelemetryDTO(
            event_type="threat_finding",
            timestamp=event.timestamp,
            request_id=event.request_id,
            severity=event.severity,
            finding_type=event.finding_type,
        )
    if isinstance(event, PIIMasked):
        return CloudTelemetryDTO(
            event_type="pii_masked",
            timestamp=event.timestamp,
            request_id=event.request_id,
            entity_count=event.entity_count,
        )
    if isinstance(event, AuditRecorded):
        return CloudTelemetryDTO(
            event_type="audit_recorded",
            timestamp=event.timestamp,
            request_id=event.request_id,
            stage=event.stage,
        )
    raise TypeError(f"Unsupported event type: {type(event)!r}")
