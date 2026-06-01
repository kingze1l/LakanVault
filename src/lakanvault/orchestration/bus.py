from lakanvault.contracts.dtos import CloudTelemetryDTO
from lakanvault.contracts.events import (
    AuditRecorded,
    IntegrityVerified,
    PIIMasked,
    ThreatFinding,
)
from lakanvault.contracts.policies import AirGapPolicy, CloudEligibility, redact_for_cloud
from lakanvault.contracts.ports import ICloudAnalytics, ICloudEnrichment
from lakanvault.infrastructure.config_loader import AppConfig

PipelineEvent = IntegrityVerified | ThreatFinding | PIIMasked | AuditRecorded


class EventBus:
    def __init__(
        self,
        config: AppConfig,
        enrichment: ICloudEnrichment | None = None,
        analytics: ICloudAnalytics | None = None,
    ) -> None:
        self._config = config
        self._enrichment = enrichment
        self._analytics = analytics
        self._local_log: list[PipelineEvent] = []

    @property
    def local_events(self) -> list[PipelineEvent]:
        return list(self._local_log)

    def publish_local(self, event: PipelineEvent) -> None:
        self._local_log.append(event)

    def maybe_forward(self, event: PipelineEvent) -> CloudTelemetryDTO | None:
        self.publish_local(event)
        if not AirGapPolicy.cloud_allowed(self._config):
            return None
        if not CloudEligibility.event_may_forward(event):
            return None
        telemetry = redact_for_cloud(event)
        if self._analytics is not None:
            self._analytics.upload_metrics(telemetry)
        if self._enrichment is not None:
            self._enrichment.fetch_artifacts(telemetry)
        return telemetry
