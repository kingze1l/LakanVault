"""Gateway protect/restore via Joan process_input / process_output."""
from __future__ import annotations

from pathlib import Path

import pytest

from lakanvault.contracts.mcp import FORBIDDEN_MCP_RESPONSE_FIELDS
from lakanvault.local_core.findings import Finding, Tier
from lakanvault.orchestration.gateway import Gateway

# URI credentials rule in Joan's SecretDetector (no spaCy / Presidio required).
SECRET_PROMPT = "connect with postgres://admin:SuperSecret99@db.example.com/app"
SECRET_VALUE = "SuperSecret99"
EMAIL = "jane.doe@example.com"
PII_PROMPT = f"please email {EMAIL} about the meeting"


def _gateway(tmp_path: Path) -> Gateway:
    src = Path(__file__).resolve().parents[2] / "config" / "default.yaml"
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "default.yaml").write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return Gateway(config_dir=cfg)


@pytest.fixture(autouse=True)
def _pii_without_presidio(monkeypatch: pytest.MonkeyPatch) -> None:
    """Secrets via detector; email via stub Finding so CI needs no spaCy."""

    def fake_pii(text: str, layers=("names",)):
        start = text.find(EMAIL)
        if start < 0:
            return []
        return [
            Finding(
                "EMAIL_ADDRESS",
                EMAIL,
                start,
                start + len(EMAIL),
                0.95,
                Tier.PII_MODERATE,
                "presidio",
            )
        ]

    monkeypatch.setattr("lakanvault.local_core.scan.detect_pii", fake_pii)


def test_protect_blocks_secret_and_omits_raw_values(tmp_path: Path) -> None:
    """SECRET → policy BLOCK: empty sanitized, findings metadata only."""
    gw = _gateway(tmp_path)
    out = gw.protect_prompt(SECRET_PROMPT, session_id="s1", llm="never")
    assert out.session_id == "s1"
    assert out.sanitized == ""
    assert SECRET_VALUE not in out.sanitized
    assert out.finding_count >= 1
    dumped = out.model_dump()
    assert FORBIDDEN_MCP_RESPONSE_FIELDS.isdisjoint(dumped.keys())
    assert SECRET_VALUE not in str(dumped)
    for finding in out.findings:
        assert "text" not in finding.model_dump()
        assert finding.entity_type


def test_protect_restore_round_trip_masks_pii(tmp_path: Path) -> None:
    gw = _gateway(tmp_path)
    protected = gw.protect_prompt(PII_PROMPT, session_id="round", llm="never")
    assert EMAIL not in protected.sanitized
    assert protected.sanitized
    restored = gw.restore_prompt(protected.sanitized, session_id="round")
    assert restored.session_id == "round"
    assert EMAIL in restored.text


def test_restore_unknown_session_raises(tmp_path: Path) -> None:
    gw = _gateway(tmp_path)
    with pytest.raises(KeyError, match="unknown protect session"):
        gw.restore_prompt("hello", session_id="missing")


def test_protect_assigns_session_when_blank(tmp_path: Path) -> None:
    gw = _gateway(tmp_path)
    out = gw.protect_prompt(PII_PROMPT, session_id="", llm="never")
    assert out.session_id
    assert EMAIL not in out.sanitized
    restored = gw.restore_prompt(out.sanitized, session_id=out.session_id)
    assert EMAIL in restored.text
