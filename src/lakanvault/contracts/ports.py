from typing import Protocol

from lakanvault.contracts.dtos import CloudTelemetryDTO, RedactedText, StatusSummaryDTO
from lakanvault.contracts.events import (
    AuditRecorded,
    IntegrityVerified,
    PIIMasked,
    ThreatFinding,
)


class IIntegrityGuard(Protocol):
    def verify(self, model_id: str, model_path: str) -> IntegrityVerified: ...


class IThreatScanner(Protocol):
    def scan_environment(self, request_id: str) -> list[ThreatFinding]: ...


class IPrivacyShield(Protocol):
    def mask_prompt(self, request_id: str, text: str) -> tuple[PIIMasked, RedactedText]: ...


class IAuditStore(Protocol):
    def record(self, event: AuditRecorded) -> None: ...

    def get_status(self, request_id: str) -> StatusSummaryDTO: ...


class ICloudEnrichment(Protocol):
    def fetch_artifacts(self, telemetry: CloudTelemetryDTO) -> bytes: ...


class ICloudAnalytics(Protocol):
    def upload_metrics(self, telemetry: CloudTelemetryDTO) -> None: ...
