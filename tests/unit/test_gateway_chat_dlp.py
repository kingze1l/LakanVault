"""Gateway chat path uses the same DLP transformer as classify (no secret fail-open)."""
from pathlib import Path

from lakanvault.orchestration.gateway import Gateway


def test_chat_blocks_api_key_without_upstream() -> None:
    config_dir = Path(__file__).resolve().parents[2] / "config"
    gw = Gateway(config_dir=config_dir)
    result = gw.chat("My key is sk-9f8e7d6c5b4a3210fedcba0987654321zz")
    assert result["blocked"] is True
    assert result["sanitized_prompt"] == ""
    assert "sk-" not in result["sanitized_prompt"]
    assert result["mapping"] == {}
