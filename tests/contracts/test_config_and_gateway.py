from pathlib import Path

from lakanvault.infrastructure.config_loader import load_config
from lakanvault.orchestration.gateway import Gateway


def test_default_config_is_air_gapped() -> None:
    root = Path(__file__).resolve().parents[2]
    config = load_config(root / "config")
    assert config.cloud.enabled is False
    assert config.local.chunk_size_bytes == 1_048_576


def test_gateway_receive_returns_not_implemented_stub() -> None:
    root = Path(__file__).resolve().parents[2]
    config = load_config(root / "config")
    gateway = Gateway(config)
    result = gateway.receive("verify_model", {"request_id": "req-1"})
    assert result.overall_status == "not_implemented"
    assert result.request_id == "req-1"
