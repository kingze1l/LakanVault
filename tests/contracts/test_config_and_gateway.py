from pathlib import Path

from lakanvault.contracts.dtos import ScanRequest
from lakanvault.infrastructure.config_loader import load_config
from lakanvault.orchestration.gateway import Gateway


def test_default_config_is_air_gapped() -> None:
    root = Path(__file__).resolve().parents[2]
    config = load_config(root / "config")
    assert config.cloud.enabled is False
    assert config.local.chunk_size_bytes == 1_048_576


def test_gateway_receive_with_prompt_detects_pii() -> None:
    root = Path(__file__).resolve().parents[2]
    gateway = Gateway(config_dir=root / "config")
    result = gateway.receive(
        ScanRequest(
            target_path=str(root / "requirements.txt"),
            prompt_text="Contact me at user@example.com",
        )
    )
    assert result.run_id
    assert result.pii_span_count >= 1
    assert result.cloud_forwarded is False
