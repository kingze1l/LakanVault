from pathlib import Path

from lakanvault.contracts.events import PipelineEvent, StageResult, StageStatus
from lakanvault.infrastructure.config_loader import load_config
from lakanvault.orchestration.bus import EventBus


def test_air_gap_blocks_cloud_forward() -> None:
    root = Path(__file__).resolve().parents[2]
    config = load_config(root / "config")
    bus = EventBus(cloud_enabled=config.cloud.enabled)
    event = PipelineEvent(run_id="r1", target_path="model.bin")
    event.stages.append(
        StageResult(stage="integrity", status=StageStatus.PASS, metadata={"bytes_processed": 100})
    )
    forwarded = bus.publish(event, duration_ms=5.0)
    assert forwarded is False
