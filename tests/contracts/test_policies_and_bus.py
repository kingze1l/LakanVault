from datetime import datetime, timezone

from lakanvault.cloud_intelligence.adapters.noop import NoOpCloudAnalytics, NoOpCloudEnrichment
from lakanvault.contracts.events import ThreatFinding
from lakanvault.contracts.policies import AirGapPolicy
from lakanvault.infrastructure.config_loader import load_config
from lakanvault.orchestration.bus import EventBus
from pathlib import Path


def test_air_gap_blocks_cloud_forward() -> None:
    root = Path(__file__).resolve().parents[2]
    config = load_config(root / "config")
    assert AirGapPolicy.cloud_allowed(config) is False
    bus = EventBus(
        config,
        enrichment=NoOpCloudEnrichment(),
        analytics=NoOpCloudAnalytics(),
    )
    event = ThreatFinding(
        request_id="r1",
        severity="low",
        finding_type="env_leak",
        timestamp=datetime.now(timezone.utc),
    )
    forwarded = bus.maybe_forward(event)
    assert forwarded is None
    assert len(bus.local_events) == 1
