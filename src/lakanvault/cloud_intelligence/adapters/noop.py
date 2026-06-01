from lakanvault.contracts.dtos import CloudTelemetryDTO


class NoOpCloudEnrichment:
    def fetch_artifacts(self, telemetry: CloudTelemetryDTO) -> bytes:
        return b""


class NoOpCloudAnalytics:
    def upload_metrics(self, telemetry: CloudTelemetryDTO) -> None:
        return None
